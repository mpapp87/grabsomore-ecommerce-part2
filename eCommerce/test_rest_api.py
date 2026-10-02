"""Regression tests for the buyer/vendor REST API."""

from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import Product, Store


class CommerceAPITests(TestCase):
    """Exercise role checks, ownership, validation, and catalog retrieval."""

    def setUp(self):
        """Create isolated accounts, role groups, and fixtures for each test."""
        vendors, _ = Group.objects.get_or_create(name='Vendors')
        buyers, _ = Group.objects.get_or_create(name='Buyers')
        self.vendor = User.objects.create_user(
            username='api_vendor', password='TestPassword!123'
        )
        self.other_vendor = User.objects.create_user(
            username='api_other', password='TestPassword!123'
        )
        self.buyer = User.objects.create_user(
            username='api_buyer', password='TestPassword!123'
        )
        self.vendor.groups.add(vendors)
        self.other_vendor.groups.add(vendors)
        self.buyer.groups.add(buyers)
        self.store = Store.objects.create(owner=self.vendor, name='Vendor store')
        self.product = Product.objects.create(
            store=self.store, name='Headphones',
            price=Decimal('99.99'), stock=5,
        )
        self.client = APIClient()

    def test_anonymous_users_cannot_access_catalog(self):
        """Verify that anonymous users cannot access catalog."""
        response = self.client.get(reverse('eCommerce:api_stores'))
        self.assertIn(response.status_code, (401, 403))

    def test_buyer_can_read_stores_and_products_but_cannot_create(self):
        """Verify that buyer can read stores and products but cannot create."""
        self.client.force_authenticate(user=self.buyer)
        stores = self.client.get(reverse('eCommerce:api_stores'))
        products = self.client.get(reverse('eCommerce:api_products'))
        scoped = self.client.get(reverse(
            'eCommerce:api_store_products', args=[self.store.pk]
        ))
        self.assertEqual(stores.status_code, 200)
        self.assertEqual(stores.data[0]['owner'], self.vendor.username)
        self.assertEqual(products.status_code, 200)
        self.assertEqual(products.data[0]['store'], self.store.pk)
        self.assertEqual(scoped.status_code, 200)
        self.assertEqual(len(scoped.data), 1)
        self.assertEqual(self.client.post(reverse('eCommerce:api_stores'), {
            'name': 'Forbidden store',
        }).status_code, 403)
        self.assertEqual(self.client.post(reverse('eCommerce:api_products'), {
            'store': self.store.pk, 'name': 'Forbidden item',
            'price': '1.00', 'stock': 1,
        }).status_code, 403)

    def test_vendor_creates_store_with_server_assigned_owner_and_product(self):
        """Verify that vendor creates store with server assigned owner and product."""
        self.client.force_authenticate(user=self.vendor)
        response = self.client.post(reverse('eCommerce:api_stores'), {
            'name': 'New store', 'description': 'Audio gear',
            'owner': self.buyer.pk,
        })
        self.assertEqual(response.status_code, 201)
        store = Store.objects.get(pk=response.data['id'])
        self.assertEqual(store.owner, self.vendor)
        product = self.client.post(reverse('eCommerce:api_products'), {
            'store': store.pk, 'name': 'DAC',
            'price': '49.95', 'stock': 2,
        })
        self.assertEqual(product.status_code, 201)
        self.assertEqual(Product.objects.get(pk=product.data['id']).store, store)

    def test_vendor_cannot_add_product_to_another_vendors_store(self):
        """Verify that vendor cannot add product to another vendors store."""
        self.client.force_authenticate(user=self.other_vendor)
        response = self.client.post(reverse('eCommerce:api_products'), {
            'store': self.store.pk, 'name': 'Not mine',
            'price': '2.00', 'stock': 1,
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Product.objects.filter(name='Not mine').exists())

    def test_invalid_product_fields_do_not_create_records(self):
        """Verify that invalid product fields do not create records."""
        self.client.force_authenticate(user=self.vendor)
        response = self.client.post(reverse('eCommerce:api_products'), {
            'store': self.store.pk, 'name': 'Invalid stock',
            'price': '-1.00', 'stock': -2,
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Product.objects.filter(name='Invalid stock').exists())

    def test_product_detail_and_unknown_store(self):
        """Verify that product detail and unknown store."""
        self.client.force_authenticate(user=self.buyer)
        detail = self.client.get(reverse(
            'eCommerce:api_product_detail', args=[self.product.pk]
        ))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data['name'], 'Headphones')
        self.assertEqual(self.client.get(reverse(
            'eCommerce:api_store_products', args=[999999]
        )).status_code, 404)


    def test_negative_price_with_valid_stock_is_rejected(self):
        """Reject negative API prices independently of stock validation."""
        self.client.force_authenticate(user=self.vendor)
        response = self.client.post(reverse('eCommerce:api_products'), {
            'store': self.store.pk, 'name': 'Negative price',
            'price': '-1.00', 'stock': 2,
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Product.objects.filter(name='Negative price').exists())
