"""REST Framework serializers for vendor-owned stores and products."""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Product, Store, Review


class StoreSerializer(serializers.ModelSerializer):
    """Expose a store and its owner without permitting owner spoofing."""

    owner = serializers.ReadOnlyField(source='owner.username')

    def validate(self, attrs):
        """Report duplicate store names for the same owner as validation errors."""
        owner = self.context['request'].user
        matches = Store.objects.filter(owner=owner, name=attrs.get('name', self.instance.name if self.instance else ''))
        if self.instance:
            matches = matches.exclude(pk=self.instance.pk)
        if matches.exists():
            raise serializers.ValidationError({'name': 'You already have a store with this name.'})
        return attrs

    class Meta:
        """Declare API fields and protect server-owned values."""
        model = Store
        fields = ('id', 'name', 'description', 'owner')
        read_only_fields = ('id', 'owner')


class ProductSerializer(serializers.ModelSerializer):
    """Validate that a vendor can only list products in their stores."""

    store = serializers.PrimaryKeyRelatedField(queryset=Store.objects.all())

    class Meta:
        """Declare API fields and protect server-owned values."""
        model = Product
        fields = ('id', 'store', 'name', 'description', 'price', 'stock')
        read_only_fields = ('id',)

    def validate(self, attrs):
        """Recheck store ownership even when PATCH omits the store field."""
        store = attrs.get('store', self.instance.store if self.instance else None)
        if store is not None:
            self.validate_store(store)
        return attrs

    def validate_price(self, price):
        """Apply the same nonnegative price rule as the vendor HTML form."""
        if price < 0:
            raise serializers.ValidationError('Price must not be negative.')
        return price

    def validate_store(self, store):
        """Reject creation in a store that the current vendor does not own."""
        request = self.context.get('request')
        if request is None or store.owner_id != request.user.pk:
            raise serializers.ValidationError(
                'You may only add products to a store you own.'
            )
        return store


class ReviewSerializer(serializers.ModelSerializer):
    """Expose review content and computed purchase status without private buyer data."""

    buyer = serializers.ReadOnlyField(source='buyer.username')
    verified = serializers.BooleanField(source='verified_purchase', read_only=True)

    class Meta:
        """Make the review retrieval representation entirely read-only."""

        model = Review
        fields = ('id', 'product', 'buyer', 'rating', 'comment', 'created_at', 'verified')
        read_only_fields = fields


class VendorSerializer(serializers.ModelSerializer):
    """Expose stable vendor identifiers and usernames for directory navigation."""

    class Meta:
        """Exclude private emails, passwords and account permission fields."""

        model = get_user_model()
        fields = ('id', 'username')
        read_only_fields = fields
