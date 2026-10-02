"""Stores and products for the eCommerce application."""

from django.conf import settings
from django.db import models


class Store(models.Model):
    """A storefront managed by one registered vendor."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='stores',
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        """Define database constraints, ordering, or model permissions."""
        constraints = [
            models.UniqueConstraint(
                fields=['owner', 'name'], name='unique_vendor_store_name'
            ),
        ]

    def __str__(self):
        """Return a readable label for this record in the admin and debugging output."""
        return self.name


class Product(models.Model):
    """A product listed within exactly one vendor-owned store."""

    store = models.ForeignKey(
        Store, on_delete=models.CASCADE, related_name='products'
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField()

    def __str__(self):
        """Return a readable label for this record in the admin and debugging output."""
        return self.name

    class Meta:
        """Define database constraints, ordering, or model permissions."""
        permissions = [
            ('add_products', 'Can add products'),
            ('change_products', 'Can change products'),
            ('delete_products', 'Can delete products'),
            ('view_products', 'Can view products'),
        ]


class Invoice(models.Model):
    """A completed checkout with a stable recipient and duplicate-submit key."""

    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    checkout_token = models.UUIDField(unique=True)
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    emailed_at = models.DateTimeField(null=True, blank=True)

    @property
    def total(self):
        """Sum the saved line prices, never the current catalog prices."""
        from decimal import Decimal
        return sum((item.subtotal for item in self.items.all()), Decimal('0.00'))


class InvoiceItem(models.Model):
    """Preserve purchase details even after a vendor removes a product."""

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, null=True, on_delete=models.SET_NULL)
    product_name = models.CharField(max_length=100)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()

    @property
    def subtotal(self):
        """Calculate this line's total using its purchase-time price."""
        return self.unit_price * self.quantity


class Review(models.Model):
    """One buyer's review of a product; purchase status is derived from invoices."""

    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField(choices=[(i, str(i)) for i in range(1, 6)])
    comment = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Define database constraints, ordering, or model permissions."""
        ordering = ['-created_at', '-pk']
        constraints = [
            models.UniqueConstraint(fields=['buyer', 'product'], name='one_buyer_product_review'),
            models.CheckConstraint(condition=models.Q(rating__gte=1, rating__lte=5), name='review_rating_1_to_5'),
        ]

    @property
    def verified(self):
        """Verify against this buyer's completed purchases, including later purchases."""
        return InvoiceItem.objects.filter(invoice__buyer_id=self.buyer_id, product_id=self.product_id).exists()
