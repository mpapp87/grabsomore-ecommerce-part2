"""Tests covering vendor CRUD, store ownership and buyer shopping."""

from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from .models import Product, Store


class CommerceRoleTests(TestCase):
    """Exercise buyer permissions and vendor store/product ownership."""
    def setUp(self):
        """Create isolated accounts, role groups, and fixtures for each test."""
        vendors, _ = Group.objects.get_or_create(name='Vendors')
        buyers, _ = Group.objects.get_or_create(name='Buyers')
        self.vendor = User.objects.create_user(
            username='vendor1', password='TestPassword!123'
        )
        self.other_vendor = User.objects.create_user(
            username='vendor2', password='TestPassword!123'
        )
        self.buyer = User.objects.create_user(
            username='buyer', password='TestPassword!123'
        )
        self.vendor.groups.add(vendors)
        self.other_vendor.groups.add(vendors)
        self.buyer.groups.add(buyers)
        self.store = Store.objects.create(owner=self.vendor, name='A store')
        self.product = Product.objects.create(
            store=self.store, name='Mug', price=Decimal('12.50'), stock=4
        )

    def test_buyer_cannot_manage_stores(self):
        """Verify that buyer cannot manage stores."""
        self.client.force_login(self.buyer)
        response = self.client.post(reverse('eCommerce:store_create'), {
            'name': 'Not allowed', 'description': '',
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Store.objects.filter(name='Not allowed').exists())

    def test_vendor_can_create_store_and_product(self):
        """Verify that vendor can create store and product."""
        self.client.force_login(self.vendor)
        self.assertRedirects(self.client.post(
            reverse('eCommerce:store_create'), {'name': 'Second store'}
        ), reverse('eCommerce:stores'))
        new_store = Store.objects.get(name='Second store')
        self.assertEqual(new_store.owner, self.vendor)
        self.assertRedirects(self.client.post(
            reverse('eCommerce:product_create'), {
                'store': new_store.pk, 'name': 'Notebook',
                'description': '', 'price': '8.00', 'stock': 2,
            }
        ), reverse('eCommerce:stores'))
        self.assertEqual(Product.objects.get(name='Notebook').store, new_store)

    def test_vendor_cannot_edit_someone_elses_product(self):
        """Verify that vendor cannot edit someone elses product."""
        self.client.force_login(self.other_vendor)
        response = self.client.post(reverse('eCommerce:product_edit',
                                            args=[self.product.pk]), {
            'store': self.store.pk, 'name': 'Stolen',
            'price': '1.00', 'stock': 1,
        })
        self.assertEqual(response.status_code, 404)
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, 'Mug')
        self.assertEqual(self.client.post(reverse('eCommerce:store_delete',
                                                  args=[self.store.pk])).status_code, 404)

    def test_buyer_can_add_product_by_id(self):
        """Verify that buyer can add product by id."""
        self.client.force_login(self.buyer)
        self.assertRedirects(self.client.post(reverse('eCommerce:add_to_cart'), {
            'item': self.product.pk, 'quantity': 2,
        }), reverse('eCommerce:main_cart_page'))
        self.assertEqual(self.client.session['cart'][str(self.product.pk)], 2)

    def test_vendor_cannot_use_buyer_cart(self):
        """Verify that vendor cannot use buyer cart."""
        self.client.force_login(self.vendor)
        self.assertEqual(self.client.post(reverse('eCommerce:add_to_cart'), {
            'item': self.product.pk, 'quantity': 1,
        }).status_code, 403)
