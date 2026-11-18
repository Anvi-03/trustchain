from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User


class RegisterTests(TestCase):

    def test_register_page_loads(self):
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Create Account')

    def test_successful_registration(self):
        response = self.client.post(reverse('register'), {
            'username': 'testuser',
            'email': 'test@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        })
        self.assertRedirects(response, reverse('home'))
        self.assertTrue(User.objects.filter(username='testuser').exists())
        user = User.objects.get(username='testuser')
        self.assertEqual(user.email, 'test@example.com')
        # Password must be hashed, not plain text
        self.assertNotEqual(user.password, 'SecurePass123!')

    def test_registration_password_mismatch(self):
        response = self.client.post(reverse('register'), {
            'username': 'testuser',
            'email': 'test@example.com',
            'password1': 'SecurePass123!',
            'password2': 'WrongPass456!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='testuser').exists())

    def test_registration_duplicate_username(self):
        User.objects.create_user('testuser', 'a@b.com', 'pass')
        response = self.client.post(reverse('register'), {
            'username': 'testuser',
            'email': 'test@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(username='testuser').count(), 1)

    def test_registration_email_required(self):
        response = self.client.post(reverse('register'), {
            'username': 'testuser',
            'email': '',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='testuser').exists())


class LoginTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='SecurePass123!'
        )

    def test_login_page_loads(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Login')

    def test_successful_login(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'SecurePass123!',
        })
        self.assertRedirects(response, reverse('home'))

    def test_invalid_login(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, 200)


class LogoutTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='SecurePass123!'
        )
        self.client.login(username='testuser', password='SecurePass123!')

    def test_logout(self):
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('login'))

    def test_home_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('home'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('home')}")
