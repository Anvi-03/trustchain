from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User

from blockchain.models import Block, calculate_block_hash
from transactions.models import (
    Transaction,
    calculate_transaction_hash,
    sign_transaction,
)


class BlockchainTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', 'alice@test.com', 'Pass123!')
        self.bob = User.objects.create_user('bob', 'bob@test.com', 'Pass123!')
        self.alice.wallet.balance = Decimal('100.0')
        self.alice.wallet.save()

    def test_genesis_block_creation(self):
        genesis = Block.get_or_create_genesis()
        self.assertEqual(genesis.index, 0)
        self.assertEqual(genesis.previous_hash, "0")
        self.assertEqual(len(genesis.current_hash), 64)
        self.assertEqual(genesis.nonce, 0)

        # Calling again returns the exact same genesis block
        genesis_second = Block.get_or_create_genesis()
        self.assertEqual(genesis.id, genesis_second.id)
        self.assertEqual(Block.objects.count(), 1)

    def test_add_block_linkage_and_hash(self):
        genesis = Block.get_or_create_genesis()
        block1 = Block.add_block()

        self.assertEqual(block1.index, 1)
        self.assertEqual(block1.previous_hash, genesis.current_hash)
        self.assertEqual(len(block1.current_hash), 64)
        self.assertNotEqual(block1.current_hash, genesis.current_hash)

        block2 = Block.add_block()
        self.assertEqual(block2.index, 2)
        self.assertEqual(block2.previous_hash, block1.current_hash)

        # Ordering check
        blocks = list(Block.objects.all())
        self.assertEqual([b.index for b in blocks], [0, 1, 2])

    def test_add_block_with_transactions(self):
        # Create a pending transaction
        tx_hash = calculate_transaction_hash(
            self.alice.wallet.address,
            self.bob.wallet.address,
            Decimal('20.0'),
            '2026-01-01'
        )
        sig = sign_transaction(self.alice.wallet.private_key, tx_hash)
        tx = Transaction.objects.create(
            sender=self.alice.wallet,
            receiver=self.bob.wallet,
            amount=Decimal('20.0'),
            transaction_hash=tx_hash,
            signature=sig,
            status='Pending'
        )

        block = Block.add_block(transactions=[tx])
        self.assertIn(tx, block.transactions.all())

        tx.refresh_from_db()
        self.assertEqual(tx.status, 'Confirmed')

    def test_is_chain_valid_success(self):
        Block.get_or_create_genesis()
        Block.add_block()
        Block.add_block()
        self.assertTrue(Block.is_chain_valid())

    def test_is_chain_valid_tampered_hash_fails(self):
        Block.get_or_create_genesis()
        block1 = Block.add_block()
        Block.add_block()

        # Tamper with block1's current_hash
        block1.current_hash = "tampered" + block1.current_hash[8:]
        block1.save()

        self.assertFalse(Block.is_chain_valid())

    def test_is_chain_valid_broken_previous_hash_link_fails(self):
        Block.get_or_create_genesis()
        Block.add_block()
        block2 = Block.add_block()

        # Break the previous_hash link
        block2.previous_hash = "0" * 64
        block2.save()

        self.assertFalse(Block.is_chain_valid())
