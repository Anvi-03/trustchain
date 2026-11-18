from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.db import connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from transactions.models import Transaction, calculate_transaction_hash, sign_transaction
from wallet.models import Wallet

from .models import Block, PROOF_PREFIX
from .services import mine_block, validate_chain


def sign_transfer(sender, receiver, amount):
    timestamp = timezone.now()
    tx_hash = calculate_transaction_hash(sender.address, receiver.address, amount, str(timestamp))
    return Transaction.objects.create(
        sender=sender, receiver=receiver, amount=amount, timestamp=timestamp,
        transaction_hash=tx_hash, signature=sign_transaction(sender.private_key, tx_hash),
    )


class BlockchainTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user("alice")
        cls.bob = User.objects.create_user("bob")

    def setUp(self):
        self.client.force_login(self.alice)

    def send(self, amount):
        return self.client.post(reverse("send_transaction"), {
            "receiver_address": self.bob.wallet.address, "amount": amount,
        })

    def test_genesis_created_and_hashed_automatically(self):
        genesis = Block.objects.get(index=0)
        self.assertEqual(genesis.pk, Block.get_or_create_genesis().pk)
        self.assertEqual(genesis.previous_hash, "0")
        self.assertEqual(genesis.nonce, 0)
        self.assertFalse(genesis.transactions.exists())
        self.assertEqual(genesis.current_hash, genesis.recalculate_hash())
        self.assertTrue(Block.is_chain_valid())

    def test_transaction_lifecycle_through_views(self):
        self.assertContains(self.client.get(reverse("mine_block")), "No eligible transfers")
        self.assertEqual(Block.objects.count(), 1)
        self.assertRedirects(self.client.post(reverse("mine_block")), reverse("block_detail", args=[1]))
        self.alice.wallet.refresh_from_db()
        self.assertEqual(self.alice.wallet.balance, settings.MINING_REWARD)

        self.assertEqual(self.send("4").status_code, 302)
        tx = Transaction.objects.get()
        self.assertTrue(tx.is_signed())
        self.assertEqual(tx.status, Transaction.STATUS_PENDING)
        self.alice.wallet.refresh_from_db()
        self.assertEqual(self.alice.wallet.balance, settings.MINING_REWARD)
        self.assertEqual(self.bob.wallet.balance, 0)
        self.assertContains(self.send("7"), "Insufficient balance after pending transfers.")
        self.assertContains(self.client.get(reverse("mine_block")), tx.transaction_hash[:16])

        self.client.force_login(self.bob)
        self.assertRedirects(self.client.post(reverse("mine_block")), reverse("block_detail", args=[2]))
        block = Block.objects.get(index=2)
        self.assertEqual(block.previous_hash, Block.objects.get(index=1).current_hash)
        self.assertEqual(block.current_hash, block.recalculate_hash())
        self.assertTrue(block.current_hash.startswith(PROOF_PREFIX))
        self.assertEqual(block.reward, settings.MINING_REWARD)
        self.assertEqual(block.miner_address, self.bob.wallet.address)
        tx.refresh_from_db()
        self.assertEqual(tx.status, Transaction.STATUS_CONFIRMED)
        self.assertEqual(tx.blocks.get(), block)
        self.alice.wallet.refresh_from_db()
        self.bob.wallet.refresh_from_db()
        self.assertEqual(self.alice.wallet.balance, settings.MINING_REWARD - 4)
        self.assertEqual(self.bob.wallet.balance, settings.MINING_REWARD + 4)
        self.assertContains(self.client.get(reverse("home")), self.bob.wallet.address)
        self.assertContains(self.client.get(reverse("explorer")), block.current_hash)
        self.assertContains(self.client.get(reverse("block_detail", args=[2])), tx.transaction_hash)
        detail = self.client.get(reverse("explorer_transaction", args=[tx.transaction_hash]))
        self.assertContains(detail, "Back to Block #2")
        self.assertNotContains(detail, "PRIVATE KEY")
        self.assertContains(self.client.get(reverse("transaction_history")), "Confirmed")
        self.assertContains(self.client.post(reverse("validate_chain"), follow=True), "Blockchain is valid.")

        mine_block(self.bob.wallet.pk)
        self.assertEqual(tx.blocks.count(), 1)
        self.alice.wallet.refresh_from_db()
        self.bob.wallet.refresh_from_db()
        self.assertEqual(self.alice.wallet.balance, settings.MINING_REWARD - 4)
        self.assertEqual(self.bob.wallet.balance, 2 * settings.MINING_REWARD + 4)

    def test_mines_legacy_signature_with_unpadded_decimal(self):
        mine_block(self.alice.wallet.pk)
        tx = sign_transfer(self.alice.wallet, self.bob.wallet, Decimal("1.50"))
        block = mine_block(self.bob.wallet.pk)
        self.assertEqual(block.transactions.get(), tx)
        self.assertTrue(Block.is_chain_valid())

    def test_skips_invalid_signature_modified_amount_and_overspending(self):
        mine_block(self.alice.wallet.pk)
        sender, receiver = self.alice.wallet, self.bob.wallet
        bad_signature = sign_transfer(sender, receiver, Decimal(1))
        changed_amount = sign_transfer(sender, receiver, Decimal(2))
        acceptable = sign_transfer(sender, receiver, Decimal(6))
        overspending = sign_transfer(sender, receiver, Decimal(6))
        Transaction.objects.filter(pk=bad_signature.pk).update(signature="broken")
        Transaction.objects.filter(pk=changed_amount.pk).update(amount=3)

        block = mine_block(receiver.pk)
        self.assertEqual(list(block.transactions.all()), [acceptable])
        self.assertEqual(Transaction.objects.filter(status=Transaction.STATUS_PENDING).count(), 3)
        sender.refresh_from_db()
        self.assertEqual(sender.balance, settings.MINING_REWARD - 6)

    def test_tampered_genesis_reports_index_and_blocks_mining(self):
        Block.objects.filter(index=0).update(current_hash="f" * 64)
        result = self.client.post(reverse("validate_chain"), follow=True)
        self.assertContains(result, "Blockchain is invalid at block #0.")
        self.assertContains(self.client.post(reverse("mine_block"), follow=True), "Mining stopped.")
        self.assertEqual(Block.objects.get().current_hash, "f" * 64)

    def test_tampered_block_header_and_proof(self):
        block = mine_block(self.alice.wallet.pk)
        previous_hash = block.previous_hash
        stored_hash = block.current_hash
        block.previous_hash = "f" * 64
        block.current_hash = block.recalculate_hash()
        block.save()
        self.assertEqual(validate_chain(), 1)

        block.previous_hash = previous_hash
        block.current_hash = stored_hash
        block.reward += 1
        block.save()
        self.assertEqual(validate_chain(), 1)

        while block.recalculate_hash().startswith(PROOF_PREFIX):
            block.nonce += 1
        block.current_hash = block.recalculate_hash()
        block.save()
        self.assertEqual(validate_chain(), 1)

    def test_tampered_transfer_is_detected_even_if_hash_column_is_unchanged(self):
        mine_block(self.alice.wallet.pk)
        self.send("2")
        block = mine_block(self.bob.wallet.pk)
        tx = block.transactions.get()
        Transaction.objects.filter(pk=tx.pk).update(amount=3)
        block.refresh_from_db()
        self.assertEqual(block.current_hash, block.recalculate_hash())
        self.assertEqual(validate_chain(), 2)

    def test_settlement_failure_rolls_back_block_and_transaction(self):
        mine_block(self.alice.wallet.pk)
        self.send("2")
        with patch.object(Wallet.objects, "bulk_update", side_effect=RuntimeError("write failed")):
            with self.assertRaisesRegex(RuntimeError, "write failed"):
                mine_block(self.bob.wallet.pk)
        self.assertEqual(Block.objects.count(), 2)
        self.assertEqual(Transaction.objects.get().status, Transaction.STATUS_PENDING)
        self.bob.wallet.refresh_from_db()
        self.assertEqual(self.bob.wallet.balance, 0)

    def test_permissions_and_missing_records(self):
        mine_block(self.alice.wallet.pk)
        self.send("2")
        tx_hash = Transaction.objects.get().transaction_hash
        stranger = User.objects.create_user("stranger")
        self.client.force_login(stranger)
        self.assertEqual(self.client.get(reverse("transaction_detail", args=[tx_hash])).status_code, 404)
        self.assertEqual(self.client.get(reverse("explorer_transaction", args=[tx_hash])).status_code, 404)
        self.assertEqual(self.client.get(reverse("block_detail", args=[999])).status_code, 404)
        wallet_page = self.client.get(reverse("wallet_detail"))
        self.assertContains(wallet_page, stranger.wallet.public_key.strip().splitlines()[1])
        self.assertNotContains(wallet_page, self.alice.wallet.address)
        self.assertNotContains(wallet_page, "PRIVATE KEY")
        self.assertEqual(self.client.get(reverse("validate_chain")).status_code, 405)
        self.client.logout()
        for name in ("home", "wallet_detail", "mine_block", "explorer"):
            url = reverse(name)
            self.assertRedirects(self.client.get(url), f"{reverse('login')}?next={url}")


class ConcurrentMiningTests(TransactionTestCase):
    def test_concurrent_miners_only_confirm_transfer_once(self):
        alice = User.objects.create_user("alice").wallet
        bob = User.objects.create_user("bob").wallet
        mine_block(alice.pk)
        tx = sign_transfer(alice, bob, Decimal(4))
        ready = Barrier(2)

        def mine(wallet_id):
            try:
                ready.wait(timeout=10)
                return mine_block(wallet_id).index
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(mine, [alice.pk, bob.pk])), [2, 3])

        tx.refresh_from_db()
        alice.refresh_from_db()
        bob.refresh_from_db()
        self.assertEqual(tx.status, Transaction.STATUS_CONFIRMED)
        self.assertEqual(tx.blocks.count(), 1)
        self.assertEqual(alice.balance, 2 * settings.MINING_REWARD - 4)
        self.assertEqual(bob.balance, settings.MINING_REWARD + 4)
        self.assertIsNone(validate_chain())
