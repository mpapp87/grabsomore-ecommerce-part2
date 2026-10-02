"""Admin views for vendor-owned stores and their products."""

from django.contrib import admin

from .models import Product, Store


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    """Allow administrators to find stores by name and vendor."""
    list_display = ('name', 'owner')
    search_fields = ('name', 'owner__username')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Show product stock and prices with store filtering in the admin."""
    list_display = ('name', 'store', 'price', 'stock')
    list_filter = ('store',)
    search_fields = ('name', 'store__name')
