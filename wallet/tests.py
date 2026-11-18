from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

from .models import Wallet, generate_key_pair, generate_wallet_address


class KeyGenerationTests(TestCase):

    def test_generate_key_pair_returns_two_strings(self):
        private_key, public_key = generate_key_pair()
        self.assertIsInstance(private_key, str)
        self.assertIsInstance(public_key, str)

    def test_key_pair_contains_pem_markers(self):
        private_key, public_key = generate_key_pair()
        self.assertIn('BEGIN PRIVATE KEY', private_key)
        self.assertIn('BEGIN PUBLIC KEY', public_key)

    def test_each_key_pair_is_unique(self):
        _, pub1 = generate_key_pair()
        _, pub2 = generate_key_pair()
        self.assertNotEqual(pub1, pub2)


class WalletAddressTests(TestCase):

    def test_address_starts_with_mc(self):
        _, public_key = generate_key_pair()
        address = generate_wallet_address(public_key)
        self.assertTrue(address.startswith('MC'))

    def test_address_length(self):
        # "MC" + 64 hex chars = 66 characters
        _, public_key = generate_key_pair()
        address = generate_wallet_address(public_key)
        self.assertEqual(len(address), 66)

    def test_same_key_produces_same_address(self):
        _, public_key = generate_key_pair()
        addr1 = generate_wallet_address(public_key)
        addr2 = generate_wallet_address(public_key)
        self.assertEqual(addr1, addr2)

    def test_different_keys_produce_different_addresses(self):
        _, pub1 = generate_key_pair()
        _, pub2 = generate_key_pair()
        self.assertNotEqual(
            generate_wallet_address(pub1),
            generate_wallet_address(pub2),
        )


class WalletAutoCreationTests(TestCase):

    def test_wallet_created_on_user_registration(self):
        user = User.objects.create_user('alice', 'alice@example.com', 'SecurePass123!')
        self.assertTrue(hasattr(user, 'wallet'))
        self.assertIsInstance(user.wallet, Wallet)

    def test_wallet_has_keys_and_address(self):
        user = User.objects.create_user('bob', 'bob@example.com', 'SecurePass123!')
        wallet = user.wallet
        self.assertTrue(wallet.public_key.startswith('-----BEGIN PUBLIC KEY-----'))
        self.assertTrue(wallet.private_key.startswith('-----BEGIN PRIVATE KEY-----'))
        self.assertTrue(wallet.address.startswith('MC'))

    def test_wallet_default_balance_is_zero(self):
        user = User.objects.create_user('carol', 'carol@example.com', 'SecurePass123!')
        self.assertEqual(user.wallet.balance, 0)

    def test_multiple_users_get_unique_wallets(self):
        user1 = User.objects.create_user('user1', 'u1@example.com', 'SecurePass123!')
        user2 = User.objects.create_user('user2', 'u2@example.com', 'SecurePass123!')
        user3 = User.objects.create_user('user3', 'u3@example.com', 'SecurePass123!')

        addresses = [user1.wallet.address, user2.wallet.address, user3.wallet.address]
        # All addresses must be unique
        self.assertEqual(len(set(addresses)), 3)

        public_keys = [user1.wallet.public_key, user2.wallet.public_key, user3.wallet.public_key]
        self.assertEqual(len(set(public_keys)), 3)

    def test_wallet_str_representation(self):
        user = User.objects.create_user('dave', 'dave@example.com', 'SecurePass123!')
        self.assertIn('dave', str(user.wallet))


class WalletDashboardTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'SecurePass123!')
        self.client = Client()
        self.client.login(username='testuser', password='SecurePass123!')

    def test_wallet_page_loads(self):
        response = self.client.get(reverse('wallet_detail'))
        self.assertEqual(response.status_code, 200)

    def test_wallet_page_shows_address(self):
        response = self.client.get(reverse('wallet_detail'))
        self.assertContains(response, self.user.wallet.address)

    def test_wallet_page_shows_public_key(self):
        response = self.client.get(reverse('wallet_detail'))
        self.assertContains(response, 'PUBLIC KEY')

    def test_wallet_page_shows_balance(self):
        response = self.client.get(reverse('wallet_detail'))
        self.assertContains(response, 'MYC')

    def test_wallet_page_does_not_show_private_key(self):
        response = self.client.get(reverse('wallet_detail'))
        self.assertNotContains(response, 'PRIVATE KEY')

    def test_wallet_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('wallet_detail'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('wallet_detail')}")

    def test_registration_creates_wallet_via_view(self):
        """Test wallet creation through the actual registration form."""
        self.client.logout()
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'email': 'new@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        })
        new_user = User.objects.get(username='newuser')
        self.assertTrue(hasattr(new_user, 'wallet'))
        self.assertTrue(new_user.wallet.address.startswith('MC'))
