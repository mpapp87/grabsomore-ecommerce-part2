"""Regression tests for registration and password recovery."""

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AccountTests(TestCase):
    """Exercise registration roles and password-reset validation."""
    def register(self, role='buyer', password='StrongTestPassword!123',
                 confirmation='StrongTestPassword!123', username='person'):
        """Submit a registration form with the supplied role and credential overrides."""
        return self.client.post(reverse('grabsomore:register'), {
            'username': username, 'email': f'{username}@example.com',
            'password': password, 'password_conf': confirmation,
            'role': role,
        })

    def test_buyer_registration(self):
        """Verify that buyer registration."""
        response = self.register()
        self.assertRedirects(response, reverse('grabsomore:welcome'))
        user = User.objects.get(username='person')
        self.assertTrue(user.groups.filter(name='Buyers').exists())
        self.assertFalse(user.groups.filter(name='Vendors').exists())

    def test_vendor_registration(self):
        """Verify that vendor registration."""
        self.register(role='vendor')
        user = User.objects.get(username='person')
        self.assertTrue(user.groups.filter(name='Vendors').exists())
        self.assertFalse(user.groups.filter(name='Buyers').exists())

    def test_mismatched_passwords_do_not_create_user(self):
        """Verify that mismatched passwords do not create user."""
        response = self.register(confirmation='different')
        self.assertContains(response, 'Passwords do not match.')
        self.assertFalse(User.objects.filter(username='person').exists())

    def test_invalid_role_is_rejected(self):
        """Verify that invalid role is rejected."""
        response = self.register(role='administrator')
        self.assertContains(response, 'Choose a buyer or vendor account.')
        self.assertFalse(User.objects.filter(username='person').exists())

    def test_password_reset_link_and_new_password(self):
        """Verify that password reset link and new password."""
        user = User.objects.create_user(
            username='person', email='person@example.com',
            password='PreviousPassword!123',
        )
        self.client.post(reverse('grabsomore:request_password_reset'), {
            'email': user.email,
        })
        self.assertEqual(len(mail.outbox), 1)
        reset_url = mail.outbox[0].body.split()[-1]
        self.assertIn('/reset/', reset_url)
        response = self.client.get(reset_url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse('grabsomore:reset_password'), {
            'password': 'NewSecurePassword!123',
            'password_conf': 'NewSecurePassword!123',
        })
        self.assertRedirects(response, reverse('grabsomore:login'))
        user.refresh_from_db()
        self.assertTrue(user.check_password('NewSecurePassword!123'))
        self.assertContains(
            self.client.get(reset_url), 'invalid', status_code=200,
            html=False,
        )
