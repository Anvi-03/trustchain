from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone

from wallet.models import Wallet
from transactions.models import (
    Transaction,
    calculate_transaction_hash,
    sign_transaction,
    verify_transaction_signature,
)
from transactions.forms import TransactionForm


class TransactionSignatureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice', 'alice@test.com', 'Pass123!')
        self.wallet = self.user.wallet

    def test_calculate_transaction_hash(self):
        tx_hash = calculate_transaction_hash("MC111", "MC222", Decimal('5.0'), "2026-01-01 00:00:00")
        self.assertEqual(len(tx_hash), 64)
        # Consistent hash for same input
        tx_hash2 = calculate_transaction_hash("MC111", "MC222", Decimal('5.0'), "2026-01-01 00:00:00")
        self.assertEqual(tx_hash, tx_hash2)

    def test_sign_and_verify_signature(self):
        message = "sample_transaction_hash"
        signature_hex = sign_transaction(self.wallet.private_key, message)
        self.assertIsInstance(signature_hex, str)
        self.assertTrue(len(signature_hex) > 0)

        # Verification with valid public key succeeds
        self.assertTrue(verify_transaction_signature(self.wallet.public_key, message, signature_hex))

        # Verification with tampered message fails
        self.assertFalse(verify_transaction_signature(self.wallet.public_key, "tampered_message", signature_hex))

        # Verification with different user's public key fails
        bob = User.objects.create_user('bob', 'bob@test.com', 'Pass123!')
        self.assertFalse(verify_transaction_signature(bob.wallet.public_key, message, signature_hex))


class TransactionFormValidationTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', 'alice@test.com', 'Pass123!')
        self.bob = User.objects.create_user('bob', 'bob@test.com', 'Pass123!')
        self.alice_wallet = self.alice.wallet
        self.alice_wallet.balance = Decimal('50.00000000')
        self.alice_wallet.save()

    def test_valid_form(self):
        form = TransactionForm(
            data={
                'receiver_address': self.bob.wallet.address,
                'amount': '10.50000000',
            },
            sender_wallet=self.alice_wallet
        )
        self.assertTrue(form.is_valid())

    def test_non_existent_receiver_address(self):
        form = TransactionForm(
            data={
                'receiver_address': 'MC' + '0' * 64,
                'amount': '5.0',
            },
            sender_wallet=self.alice_wallet
        )
        self.assertFalse(form.is_valid())
        self.assertIn("Receiver wallet address does not exist.", form.errors['receiver_address'])

    def test_send_to_self_prohibited(self):
        form = TransactionForm(
            data={
                'receiver_address': self.alice_wallet.address,
                'amount': '5.0',
            },
            sender_wallet=self.alice_wallet
        )
        self.assertFalse(form.is_valid())
        self.assertIn("Sender and receiver wallets must be different.", form.errors['receiver_address'])

    def test_zero_or_negative_amount_prohibited(self):
        form = TransactionForm(
            data={
                'receiver_address': self.bob.wallet.address,
                'amount': '0',
            },
            sender_wallet=self.alice_wallet
        )
        self.assertFalse(form.is_valid())
        self.assertIn('amount', form.errors)

    def test_insufficient_balance(self):
        form = TransactionForm(
            data={
                'receiver_address': self.bob.wallet.address,
                'amount': '100.00000000',  # Alice only has 50
            },
            sender_wallet=self.alice_wallet
        )
        self.assertFalse(form.is_valid())
        self.assertTrue(any("Insufficient balance" in e for e in form.errors.get('amount', [])))


class TransactionViewTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', 'alice@test.com', 'Pass123!')
        self.bob = User.objects.create_user('bob', 'bob@test.com', 'Pass123!')
        self.alice_wallet = self.alice.wallet
        self.alice_wallet.balance = Decimal('100.00000000')
        self.alice_wallet.save()

        self.client = Client()
        self.client.login(username='alice', password='Pass123!')

    def test_send_transaction_flow(self):
        response = self.client.post(reverse('send_transaction'), {
            'receiver_address': self.bob.wallet.address,
            'amount': '25.00000000',
        })
        self.assertEqual(Transaction.objects.count(), 1)
        tx = Transaction.objects.first()

        self.assertRedirects(response, reverse('transaction_detail', kwargs={'tx_hash': tx.transaction_hash}))
        self.assertEqual(tx.sender, self.alice_wallet)
        self.assertEqual(tx.receiver, self.bob.wallet)
        self.assertEqual(tx.amount, Decimal('25.00000000'))
        self.assertEqual(tx.status, 'Pending')
        self.assertEqual(len(tx.transaction_hash), 64)

        # Signature must be valid
        self.assertTrue(verify_transaction_signature(
            self.alice_wallet.public_key,
            tx.transaction_hash,
            tx.signature
        ))

        # Important rule: Balances are NOT changed upon transaction creation (only after mining)
        self.alice_wallet.refresh_from_db()
        self.bob.wallet.refresh_from_db()
        self.assertEqual(self.alice_wallet.balance, Decimal('100.00000000'))
        self.assertEqual(self.bob.wallet.balance, Decimal('0.00000000'))

    def test_history_view(self):
        # Create a transaction
        tx_hash = calculate_transaction_hash(self.alice_wallet.address, self.bob.wallet.address, Decimal('10'), 't')
        sig = sign_transaction(self.alice_wallet.private_key, tx_hash)
        Transaction.objects.create(
            sender=self.alice_wallet,
            receiver=self.bob.wallet,
            amount=Decimal('10.00000000'),
            transaction_hash=tx_hash,
            signature=sig,
            status='Pending'
        )

        response = self.client.get(reverse('transaction_history'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pending')
        self.assertContains(response, '10.00000000 MYC')

    def test_detail_view(self):
        tx_hash = calculate_transaction_hash(self.alice_wallet.address, self.bob.wallet.address, Decimal('15'), 't')
        sig = sign_transaction(self.alice_wallet.private_key, tx_hash)
        tx = Transaction.objects.create(
            sender=self.alice_wallet,
            receiver=self.bob.wallet,
            amount=Decimal('15.00000000'),
            transaction_hash=tx_hash,
            signature=sig,
            status='Pending'
        )

        response = self.client.get(reverse('transaction_detail', kwargs={'tx_hash': tx.transaction_hash}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, tx.transaction_hash)
        self.assertContains(response, self.alice_wallet.address)
        self.assertContains(response, self.bob.wallet.address)
        self.assertContains(response, '15.00000000 MYC')
        self.assertContains(response, 'Pending')
        self.assertContains(response, sig)
        # Verify private key is NEVER exposed
        self.assertNotContains(response, 'PRIVATE KEY')

    def test_unauthenticated_access_redirects_to_login(self):
        self.client.logout()
        res1 = self.client.get(reverse('send_transaction'))
        self.assertRedirects(res1, f"{reverse('login')}?next={reverse('send_transaction')}")

        res2 = self.client.get(reverse('transaction_history'))
        self.assertRedirects(res2, f"{reverse('login')}?next={reverse('transaction_history')}")
