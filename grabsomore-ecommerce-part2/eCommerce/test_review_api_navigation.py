"""Review retrieval and shared navigation regression coverage."""
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.template.loader import render_to_string
from django.urls import reverse
from rest_framework.test import APIClient

from .models import Product, Store, Review
from .services import checkout_cart


class ReviewAPITests(TestCase):
    """Check that review retrieval is scoped, private, and purchase verified."""

    def setUp(self):
        """Create two buyers, a vendor, and products in a vendor-owned store."""
        self.buyer = User.objects.create_user('buyer', email='buyer@example.com')
        self.other = User.objects.create_user('other', email='other@example.com')
        self.vendor = User.objects.create_user('vendor')
        buyers = Group.objects.create(name='Buyers')
        self.buyer.groups.add(buyers)
        self.other.groups.add(buyers)
        self.vendor.groups.add(Group.objects.create(name='Vendors'))
        store = Store.objects.create(owner=self.vendor, name='Shop')
        self.product = Product.objects.create(store=store, name='Mug', price='12.50', stock=5)
        self.second = Product.objects.create(store=store, name='Plate', price='8.00', stock=5)
        self.review = Review.objects.create(buyer=self.buyer, product=self.product, rating=5, comment='Great mug')
        Review.objects.create(buyer=self.other, product=self.second, rating=3, comment='Useful plate')
        self.api = APIClient()

    def test_get_reviews_changes_verification_only_after_matching_purchase(self):
        """Return false until the same buyer purchases the reviewed product."""
        self.api.force_authenticate(self.buyer)
        url = reverse('eCommerce:api_product_reviews', args=[self.product.pk])
        response = self.api.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertFalse(response.data[0]['verified'])
        checkout_cart(self.other, {str(self.product.pk): 1}, uuid4())
        self.assertFalse(self.api.get(url).data[0]['verified'])
        checkout_cart(self.buyer, {str(self.product.pk): 1}, uuid4())
        self.assertTrue(self.api.get(url).data[0]['verified'])
        self.assertEqual(set(response.data[0]), {'id','product','buyer','rating','comment','created_at','verified'})
        self.assertNotIn(self.buyer.email, response.content.decode())

    def test_role_access_read_only_and_unknown_product(self):
        """Deny anonymous and roleless users, allow reads, and refuse mutations."""
        url = reverse('eCommerce:api_reviews')
        self.assertIn(self.api.get(url).status_code, (401,403))
        self.api.force_authenticate(User.objects.create_user('roleless'))
        self.assertEqual(self.api.get(url).status_code, 403)
        for user in (self.buyer, self.vendor):
            self.api.force_authenticate(user)
            self.assertEqual(len(self.api.get(url).data), 2)
            self.assertIn(self.api.post(url, {'rating':5}).status_code, (403,405))
            self.assertIn(self.api.delete(url).status_code, (403,405))
        self.assertEqual(self.api.get(reverse('eCommerce:api_product_reviews', args=[999999])).status_code, 404)

    def test_empty_product_has_empty_review_list(self):
        """Return an empty collection for an existing product with no reviews."""
        self.review.delete()
        self.api.force_authenticate(self.buyer)
        response = self.api.get(reverse('eCommerce:api_product_reviews', args=[self.product.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    @patch('eCommerce.views.get_reddit_posts', return_value=[])
    def test_shared_navigation_on_buyer_vendor_and_account_pages(self, feed):
        """Render shared styling and working home/logout controls across HTML routes."""
        for name in ('login','register','request_password_reset'):
            response = self.client.get(reverse('grabsomore:'+name))
            self.assertContains(response, 'site.css')
            self.assertContains(response, 'Main navigation')
            self.assertContains(response, '>Home</a>')
        self.client.force_login(self.buyer)
        paths = [reverse('grabsomore:welcome'), reverse('eCommerce:products_list'),
                 reverse('eCommerce:main_cart_page'), reverse('eCommerce:invoice_list'),
                 reverse('eCommerce:product_detail', args=[self.product.pk]),
                 reverse('eCommerce:review_create', args=[self.product.pk]),
                 reverse('eCommerce:reddit_feed')]
        invoice = checkout_cart(self.buyer, {str(self.product.pk):1}, uuid4())
        paths.append(reverse('eCommerce:invoice_detail',args=[invoice.pk]))
        for path in paths:
            response=self.client.get(path)
            self.assertEqual(response.status_code,200)
            self.assertContains(response,'site.css')
            self.assertContains(response,'Log out')
            self.assertContains(response,'Main navigation')
        self.client.force_login(self.vendor)
        for name in ('stores','store_create','product_create','change_price'):
            response=self.client.get(reverse('eCommerce:'+name))
            self.assertContains(response,'Main navigation')
            self.assertContains(response,'Log out')
        self.assertEqual(self.client.get(reverse('grabsomore:logout')).status_code,405)
        self.assertRedirects(self.client.post(reverse('grabsomore:logout')),reverse('grabsomore:login'))

    def test_reset_status_templates_extend_shared_layout(self):
        """Check that reset success and error pages use the same stylesheet and nav."""
        for name in ('password_reset','password_reset_expired','password_reset_invalid','reset_email_sent'):
            html=render_to_string('grabsomore/'+name+'.html')
            self.assertIn('Main navigation',html)
            self.assertIn('site.css',html)
