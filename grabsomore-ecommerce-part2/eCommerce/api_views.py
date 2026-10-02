"""Authenticated REST endpoints and the existing external Reddit feed."""

from django.contrib.auth import get_user_model
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions

from .models import Product, Store, Review, InvoiceItem
from .serializers import ProductSerializer, StoreSerializer, ReviewSerializer, VendorSerializer


class BuyerOrVendorReadVendorWrite(permissions.BasePermission):
    """Allow registered buyers/vendors to read, but only owning vendors to write."""

    def has_permission(self, request, view):
        """Authorize reads for buyer/vendor roles and writes for vendors only."""
        if not request.user.is_authenticated:
            return False
        is_vendor = request.user.groups.filter(name='Vendors').exists()
        is_buyer = request.user.groups.filter(name='Buyers').exists()
        if request.method in permissions.SAFE_METHODS:
            return is_vendor or is_buyer
        return is_vendor

    def has_object_permission(self, request, view, obj):
        """Allow reads but restrict mutations to the store or product owner."""
        if request.method in permissions.SAFE_METHODS:
            return True
        owner_id = obj.owner_id if isinstance(obj, Store) else obj.store.owner_id
        return owner_id == request.user.pk


class StoreListCreateAPI(generics.ListCreateAPIView):
    """GET all stores; POST a store owned by the signed-in vendor."""

    queryset = Store.objects.select_related('owner').all().order_by('id')
    serializer_class = StoreSerializer
    permission_classes = (BuyerOrVendorReadVendorWrite,)

    def perform_create(self, serializer):
        """Assign store ownership from the authenticated account."""
        serializer.save(owner=self.request.user)


class StoreDetailAPI(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve a store; let its authenticated owner update or delete it."""

    queryset = Store.objects.select_related('owner').all()
    serializer_class = StoreSerializer
    permission_classes = (BuyerOrVendorReadVendorWrite,)


class ProductListCreateAPI(generics.ListCreateAPIView):
    """GET products; POST a product in a store owned by the vendor."""

    queryset = Product.objects.select_related('store').all().order_by('id')
    serializer_class = ProductSerializer
    permission_classes = (BuyerOrVendorReadVendorWrite,)


class ProductDetailAPI(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve a product; let its store owner update or delete it."""

    queryset = Product.objects.select_related('store').all()
    serializer_class = ProductSerializer
    permission_classes = (BuyerOrVendorReadVendorWrite,)


class StoreProductsAPI(generics.ListAPIView):
    """GET only products belonging to a particular store."""

    serializer_class = ProductSerializer
    permission_classes = (BuyerOrVendorReadVendorWrite,)

    def get_queryset(self):
        """Return products belonging to the requested existing store."""
        store = get_object_or_404(Store, pk=self.kwargs['store_id'])
        return store.products.all().order_by('id')



class ReviewListAPI(generics.ListAPIView):
    """GET reviews for authenticated buyers/vendors with purchase verification."""

    serializer_class = ReviewSerializer
    permission_classes = (BuyerOrVendorReadVendorWrite,)

    def get_queryset(self):
        """Compute verification in SQL so each review does not issue another query."""
        purchases = InvoiceItem.objects.filter(
            invoice__buyer_id=OuterRef('buyer_id'), product_id=OuterRef('product_id')
        )
        return Review.objects.select_related('buyer').annotate(
            verified_purchase=Exists(purchases)
        )


class ProductReviewsAPI(ReviewListAPI):
    """GET reviews for one product; return 404 when the product does not exist."""

    def get_queryset(self):
        """Scope the same verified review representation to the requested product."""
        product = get_object_or_404(Product, pk=self.kwargs['product_id'])
        return super().get_queryset().filter(product=product)


class VendorListAPI(generics.ListAPIView):
    """List vendor identities without disclosing private account fields."""

    queryset = get_user_model().objects.filter(groups__name='Vendors', is_active=True).distinct().order_by('username')
    serializer_class = VendorSerializer
    permission_classes = (BuyerOrVendorReadVendorWrite,)


class VendorStoresAPI(generics.ListAPIView):
    """Retrieve only the stores belonging to one existing vendor."""

    serializer_class = StoreSerializer
    permission_classes = (BuyerOrVendorReadVendorWrite,)

    def get_queryset(self):
        """Return a vendor's stores or 404 for an unknown vendor account."""
        vendor = get_object_or_404(get_user_model(), pk=self.kwargs['vendor_id'], groups__name='Vendors', is_active=True)
        return Store.objects.filter(owner=vendor).select_related('owner').order_by('id')


class VendorReviewsAPI(ReviewListAPI):
    """Provide one GET endpoint for reviews across the signed-in vendor's stores."""

    def get_queryset(self):
        """Reject buyers and scope all returned reviews to the vendor's products."""
        from rest_framework.exceptions import PermissionDenied
        if not self.request.user.groups.filter(name='Vendors').exists():
            raise PermissionDenied('A vendor account is required.')
        return super().get_queryset().filter(product__store__owner=self.request.user)
