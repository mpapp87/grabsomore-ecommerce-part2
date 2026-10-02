"""Regression tests for checkout, invoice delivery, and purchase verification."""
from decimal import Decimal
from smtplib import SMTPException
from unittest.mock import patch

from django.contrib.auth.models import User, Group
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Invoice, InvoiceItem, Product, Review, Store


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class CheckoutReviewTests(TestCase):
    """Exercise invoice snapshots, email retries, checkout access, and review verification."""
    def setUp(self):
        """Create isolated accounts, role groups, and fixtures for each test."""
        self.buyer = User.objects.create_user('buyer', email='buyer@example.com')
        self.buyer.groups.add(Group.objects.create(name='Buyers'))
        self.vendor = User.objects.create_user('vendor')
        self.vendor.groups.add(Group.objects.create(name='Vendors'))
        self.store = Store.objects.create(owner=self.vendor, name='Shop')
        self.product = Product.objects.create(store=self.store, name='Mug', price='12.50', stock=5)
        self.client.force_login(self.buyer)

    def cart(self, quantity=2):
        """Populate a session cart and retrieve the checkout token from the rendered page."""
        session = self.client.session
        session['cart'] = {str(self.product.pk): quantity}
        session.save()
        response = self.client.get(reverse('eCommerce:main_cart_page'))
        self.assertContains(response, 'Check out and email invoice')
        return response.context['checkout_token']

    def checkout(self, token):
        """Submit the cart using its server-issued checkout token."""
        return self.client.post(reverse('eCommerce:checkout'), {'checkout_token': token})

    def review(self, **kwargs):
        """Submit a product review with optional field overrides for validation tests."""
        data = {'rating': 4, 'comment': 'A useful mug.'}
        data.update(kwargs)
        return self.client.post(reverse('eCommerce:review_create', args=[self.product.pk]), data)

    def test_checkout_snapshots_cart_emails_and_deducts_stock_once(self):
        """Verify that checkout snapshots cart emails and deducts stock once."""
        token = self.cart()
        response = self.checkout(token)
        invoice = Invoice.objects.get()
        self.assertRedirects(response, reverse('eCommerce:invoice_detail', args=[invoice.pk]))
        self.assertEqual(invoice.total, Decimal('25.00'))
        self.assertEqual(self.client.session['cart'], {})
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['buyer@example.com'])
        self.assertIn('Mug: 2 x R12.50 = R25.00', mail.outbox[0].body)
        self.checkout(token)
        self.assertEqual(Invoice.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.product.price = Decimal('50.00')
        self.product.name = 'Renamed'
        self.product.save()
        self.assertEqual(invoice.total, Decimal('25.00'))
        self.product.delete()
        self.assertEqual(invoice.items.get().product_name, 'Mug')
        self.assertIsNone(invoice.items.get().product)

    def test_invalid_stock_rolls_back_entire_order(self):
        """Verify that invalid stock rolls back entire order."""
        other = Product.objects.create(store=self.store, name='Plate', price='5.00', stock=0)
        token = self.cart()
        session = self.client.session
        session['cart'][str(other.pk)] = 1
        session.save()
        self.checkout(token)
        self.assertFalse(Invoice.objects.exists())
        self.assertFalse(InvoiceItem.objects.exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
        self.assertEqual(len(self.client.session['cart']), 2)
        self.assertEqual(len(mail.outbox), 0)

    def test_removed_product_rejects_checkout_without_clearing_cart(self):
        """Verify that removed product rejects checkout without clearing cart."""
        token = self.cart()
        self.product.delete()
        self.checkout(token)
        self.assertFalse(Invoice.objects.exists())
        self.assertTrue(self.client.session['cart'])

    def test_empty_cart_and_invalid_quantity_do_not_create_invoice(self):
        """Verify that empty cart and invalid quantity do not create invoice."""
        token = self.cart(0)
        self.checkout(token)
        self.assertFalse(Invoice.objects.exists())
        session = self.client.session
        session['cart'] = {}
        session.save()
        self.checkout(token)
        self.assertFalse(Invoice.objects.exists())

    def test_email_failure_preserves_order_and_retry_does_not_checkout_again(self):
        """Verify that email failure preserves order and retry does not checkout again."""
        token = self.cart()
        with patch('eCommerce.services.send_mail', side_effect=SMTPException('offline')):
            with self.assertLogs('eCommerce.services', level='ERROR'):
                self.checkout(token)
        invoice = Invoice.objects.get()
        self.assertIsNone(invoice.emailed_at)
        self.assertEqual(self.client.session['cart'], {})
        url = reverse('eCommerce:retry_invoice_email', args=[invoice.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        self.client.post(url)
        invoice.refresh_from_db()
        self.assertIsNotNone(invoice.emailed_at)
        self.assertEqual(len(mail.outbox), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_missing_email_and_stale_token_retain_cart(self):
        """Verify that missing email and stale token retain cart."""
        token = self.cart()
        self.assertEqual(self.checkout('invalid').status_code, 400)
        self.buyer.email = ''
        self.buyer.save()
        self.checkout(token)
        self.assertFalse(Invoice.objects.exists())
        self.assertTrue(self.client.session['cart'])

    def test_checkout_requires_buyer_post_and_csrf(self):
        """Verify that checkout requires buyer post and csrf."""
        token = self.cart()
        self.assertEqual(self.client.get(reverse('eCommerce:checkout')).status_code, 405)
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.buyer)
        self.assertEqual(client.post(reverse('eCommerce:checkout'), {'checkout_token': token}).status_code, 403)
        self.client.force_login(self.vendor)
        self.assertEqual(self.checkout(token).status_code, 403)
        self.client.logout()
        self.assertEqual(self.checkout(token).status_code, 302)
        self.assertFalse(Invoice.objects.exists())

    def test_invoice_access_and_retry_are_owner_only(self):
        """Verify that invoice access and retry are owner only."""
        self.checkout(self.cart())
        invoice = Invoice.objects.get()
        other = User.objects.create_user('other')
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('eCommerce:invoice_detail', args=[invoice.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('eCommerce:retry_invoice_email', args=[invoice.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('eCommerce:invoice_list')), f'Invoice #{invoice.pk}')

    def test_unverified_review_becomes_verified_after_purchase(self):
        """Verify that unverified review becomes verified after purchase."""
        self.review(verified=True, buyer=self.vendor.pk)
        review = Review.objects.get()
        self.assertEqual(review.buyer, self.buyer)
        self.assertFalse(review.verified)
        url = reverse('eCommerce:product_detail', args=[self.product.pk])
        self.assertContains(self.client.get(url), 'Unverified purchase')
        self.checkout(self.cart())
        self.assertTrue(review.verified)
        self.assertContains(self.client.get(url), 'Verified purchase')
        self.review(comment='Updated opinion')
        self.assertEqual(Review.objects.count(), 1)
        review.refresh_from_db()
        self.assertEqual(review.comment, 'Updated opinion')

    def test_someone_elses_purchase_does_not_verify_review(self):
        """Verify that someone elses purchase does not verify review."""
        self.checkout(self.cart())
        other = User.objects.create_user('other')
        other.groups.add(Group.objects.get(name='Buyers'))
        self.client.force_login(other)
        self.review()
        self.assertFalse(Review.objects.get().verified)

    def test_review_validation_and_role_restrictions(self):
        """Verify that review validation and role restrictions."""
        for rating in (0, 6, 'bad'):
            self.assertEqual(self.review(rating=rating).status_code, 200)
        self.review(comment=' ')
        self.assertFalse(Review.objects.exists())
        self.client.force_login(self.vendor)
        self.assertEqual(self.review().status_code, 403)
        self.client.logout()
        self.assertEqual(self.review().status_code, 302)

    def test_catalog_search_and_review_form_links(self):
        """Verify that catalog search and review form links."""
        url = reverse('eCommerce:product_detail', args=[self.product.pk])
        self.assertContains(self.client.get(reverse('eCommerce:products_list')), url)
        self.assertContains(self.client.post(reverse('eCommerce:product_page'), {'product': 'Mug'}), 'Reviews')
        self.assertContains(self.client.get(reverse('eCommerce:review_create', args=[self.product.pk])), 'Save review')
