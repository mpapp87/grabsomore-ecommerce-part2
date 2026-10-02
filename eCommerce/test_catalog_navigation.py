"""Test directory navigation, vendor review filtering and CRUD ownership."""

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from .models import Product, Review, Store


class CatalogNavigationTests(TestCase):
    """Exercise each role's menu, hierarchy and unauthorized write boundaries."""

    def setUp(self):
        """Create two vendors with isolated stores, products and buyer reviews."""
        vendors = Group.objects.create(name='Vendors')
        buyers = Group.objects.create(name='Buyers')
        self.vendor = User.objects.create_user('vendor_one')
        self.other = User.objects.create_user('vendor_two')
        self.buyer = User.objects.create_user('buyer_one')
        self.second_buyer = User.objects.create_user('buyer_two')
        self.vendor.groups.add(vendors)
        self.other.groups.add(vendors)
        self.buyer.groups.add(buyers)
        self.second_buyer.groups.add(buyers)
        self.store = Store.objects.create(owner=self.vendor, name='First store')
        self.second_store = Store.objects.create(owner=self.vendor, name='Second store')
        self.foreign = Store.objects.create(owner=self.other, name='Other store')
        self.product = Product.objects.create(store=self.store, name='First product', price=10, stock=3)
        self.second_product = Product.objects.create(store=self.second_store, name='Second product', price=20, stock=3)
        self.foreign_product = Product.objects.create(store=self.foreign, name='Other product', price=30, stock=3)
        self.review = Review.objects.create(buyer=self.buyer, product=self.product, rating=5, comment='First feedback')
        Review.objects.create(buyer=self.buyer, product=self.second_product, rating=4, comment='Second feedback')
        Review.objects.create(buyer=self.buyer, product=self.foreign_product, rating=3, comment='Other feedback')
        self.api = APIClient()

    def test_buyer_menu_and_hierarchical_browsing(self):
        """Expose independent directories and correctly scope each drill-down."""
        self.client.force_login(self.buyer)
        home = self.client.get(reverse('eCommerce:products_list'))
        for label in ('>Vendors</a>', '>Stores</a>', '>Products</a>'):
            self.assertContains(home, label)
        self.assertNotContains(home, '>My Products</a>')
        vendors = self.client.get(reverse('eCommerce:vendors'))
        self.assertContains(vendors, self.vendor.username)
        self.assertContains(vendors, self.other.username)
        stores = self.client.get(reverse('eCommerce:vendor_stores', args=[self.vendor.pk]))
        self.assertContains(stores, self.store.name)
        self.assertContains(stores, self.second_store.name)
        self.assertNotContains(stores, self.foreign.name)
        all_stores = self.client.get(reverse('eCommerce:all_stores'))
        self.assertContains(all_stores, self.foreign.name)
        products = self.client.get(reverse('eCommerce:store_products', args=[self.store.pk]))
        self.assertContains(products, self.product.name)
        self.assertNotContains(products, self.second_product.name)
        self.assertNotContains(products, self.foreign_product.name)
        self.assertContains(products, 'Add to cart')

    def test_vendor_menu_and_owned_products(self):
        """Show management entry points without requiring vendors to shop."""
        self.client.force_login(self.vendor)
        response = self.client.get(reverse('eCommerce:my_products'))
        for label in ('My Products', 'My stores', 'My Reviews', 'Web API'):
            self.assertContains(response, label)
        self.assertContains(response, self.product.name)
        self.assertContains(response, self.second_product.name)
        self.assertNotContains(response, self.foreign_product.name)
        self.assertNotContains(response, 'Add to cart')
        self.assertNotContains(response, '>Shop</a>')
        stores = self.client.get(reverse('eCommerce:stores'))
        self.assertContains(stores, reverse('eCommerce:store_products', args=[self.store.pk]))
        self.assertNotContains(stores, self.product.name)

    def test_vendor_reviews_are_scoped_searchable_and_paginated(self):
        """Filter own reviews by store or text while excluding another vendor."""
        self.client.force_login(self.vendor)
        url = reverse('eCommerce:vendor_reviews')
        response = self.client.get(url)
        self.assertContains(response, 'First feedback')
        self.assertContains(response, 'Second feedback')
        self.assertNotContains(response, 'Other feedback')
        self.assertContains(response, 'Unverified purchase')
        filtered = self.client.get(url, {'store': self.store.pk})
        self.assertContains(filtered, 'First feedback')
        self.assertNotContains(filtered, 'Second feedback')
        searched = self.client.get(url, {'q': 'Second product'})
        self.assertContains(searched, 'Second feedback')
        self.assertNotContains(searched, 'First feedback')
        self.assertEqual(self.client.get(url, {'store': self.foreign.pk}).status_code, 404)
        self.assertEqual(self.client.get(url, {'store': 'invalid'}).status_code, 404)
        self.assertLessEqual(len(response.context['reviews']), 20)

    def test_directories_reject_anonymous_and_roleless_users(self):
        """Apply authentication and role checks to each new catalogue entry point."""
        urls = [reverse('eCommerce:'+name) for name in ('vendors', 'all_stores', 'api_directory')]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(User.objects.create_user('no_role'))
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.buyer)
        for name in ('my_products', 'vendor_reviews'):
            self.assertEqual(self.client.get(reverse('eCommerce:'+name)).status_code, 403)
        self.assertEqual(self.client.get(reverse('eCommerce:vendor_stores', args=[999999])).status_code, 404)
        self.assertEqual(self.client.get(reverse('eCommerce:store_products', args=[999999])).status_code, 404)

    def test_api_vendor_hierarchy_and_scoped_reviews(self):
        """Allow catalogue reads for both roles and own-review retrieval for vendors."""
        for user in (self.buyer, self.vendor):
            self.api.force_authenticate(user)
            vendors = self.api.get(reverse('eCommerce:api_vendors'))
            self.assertEqual({v['id'] for v in vendors.data}, {self.vendor.pk, self.other.pk})
            self.assertEqual(set(vendors.data[0]), {'id', 'username'})
            stores = self.api.get(reverse('eCommerce:api_vendor_stores', args=[self.vendor.pk]))
            self.assertEqual({s['id'] for s in stores.data}, {self.store.pk, self.second_store.pk})
        reviews = self.api.get(reverse('eCommerce:api_vendor_reviews'))
        self.assertEqual({r['product'] for r in reviews.data}, {self.product.pk, self.second_product.pk})
        self.api.force_authenticate(self.buyer)
        self.assertEqual(self.api.get(reverse('eCommerce:api_vendor_reviews')).status_code, 403)

    def test_api_updates_and_deletes_require_current_ownership(self):
        """Reject buyer and other-vendor writes before permitting owner updates."""
        store_url = reverse('eCommerce:api_store_detail', args=[self.store.pk])
        product_url = reverse('eCommerce:api_product_detail', args=[self.product.pk])
        for user in (self.buyer, self.other):
            self.api.force_authenticate(user)
            for url in (store_url, product_url):
                self.assertEqual(self.api.patch(url, {'name': 'Hijack'}).status_code, 403)
                self.assertEqual(self.api.delete(url).status_code, 403)
        self.api.force_authenticate(self.vendor)
        self.assertEqual(self.api.patch(store_url, {'name': 'Updated store', 'owner': self.other.pk}).status_code, 200)
        self.store.refresh_from_db()
        self.assertEqual(self.store.owner, self.vendor)
        self.assertEqual(self.api.patch(product_url, {'name': 'Updated product'}).status_code, 200)
        self.assertEqual(self.api.patch(product_url, {'store': self.foreign.pk}).status_code, 400)
        self.assertEqual(self.api.delete(product_url).status_code, 204)
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())
        self.assertEqual(self.api.delete(store_url).status_code, 204)

    def test_duplicate_store_api_name_returns_validation_error(self):
        """Report duplicate names cleanly while allowing another vendor's name."""
        self.api.force_authenticate(self.vendor)
        self.assertEqual(self.api.post(reverse('eCommerce:api_stores'), {'name': self.store.name}).status_code, 400)
        self.api.force_authenticate(self.other)
        self.assertEqual(self.api.post(reverse('eCommerce:api_stores'), {'name': self.store.name}).status_code, 201)

    def test_review_crud_keeps_buyer_ownership(self):
        """Update and delete only the logged-in buyer's review through HTML forms."""
        self.client.force_login(self.second_buyer)
        self.assertEqual(self.client.post(reverse('eCommerce:review_delete', args=[self.review.pk])).status_code, 404)
        self.client.force_login(self.vendor)
        self.assertEqual(self.client.post(reverse('eCommerce:review_delete', args=[self.review.pk])).status_code, 403)
        self.client.force_login(self.buyer)
        edit = reverse('eCommerce:review_create', args=[self.product.pk])
        self.client.post(edit, {'rating': 2, 'comment': 'Updated feedback', 'buyer': self.second_buyer.pk, 'verified': True})
        self.review.refresh_from_db()
        self.assertEqual(self.review.buyer, self.buyer)
        self.assertEqual(self.review.comment, 'Updated feedback')
        self.assertFalse(self.review.verified)
        delete = reverse('eCommerce:review_delete', args=[self.review.pk])
        self.assertEqual(self.client.get(delete).status_code, 405)
        self.assertEqual(self.client.post(delete).status_code, 302)
        self.assertFalse(Review.objects.filter(pk=self.review.pk).exists())
