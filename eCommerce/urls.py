"""HTML routes, community feed and vendor/buyer REST endpoints."""

from django.urls import path

from . import api_views, views

app_name = 'eCommerce'
urlpatterns = [
    path('vendors/', views.vendors, name='vendors'),
    path('vendors/<int:vendor_id>/stores/', views.vendor_stores, name='vendor_stores'),
    path('browse/stores/', views.all_stores, name='all_stores'),
    path('stores/<int:pk>/products/', views.store_products, name='store_products'),
    path('my/products/', views.my_products, name='my_products'),
    path('my/reviews/', views.vendor_reviews, name='vendor_reviews'),
    path('reviews/<int:pk>/delete/', views.review_delete, name='review_delete'),
    path('api/', views.api_directory, name='api_directory'),
    path('api/vendors/', api_views.VendorListAPI.as_view(), name='api_vendors'),
    path('api/vendors/<int:vendor_id>/stores/', api_views.VendorStoresAPI.as_view(), name='api_vendor_stores'),
    path('api/my/reviews/', api_views.VendorReviewsAPI.as_view(), name='api_vendor_reviews'),
    path('checkout/', views.checkout, name='checkout'),
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('invoices/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('invoices/<int:pk>/email/', views.retry_invoice_email, name='retry_invoice_email'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('products/<int:pk>/review/', views.review_create, name='review_create'),
    path('api/reviews/', api_views.ReviewListAPI.as_view(), name='api_reviews'),
    path('api/products/<int:product_id>/reviews/', api_views.ProductReviewsAPI.as_view(), name='api_product_reviews'),

    path('', views.list_products, name='products_list'),
    path('product/', views.view_product_page, name='product_page'),
    path('change-price/', views.change_product_price, name='change_price'),
    path('add-to-cart/', views.add_item_to_cart, name='add_to_cart'),
    path('cart/', views.show_user_cart, name='main_cart_page'),
    path('clear-cart/', views.clear_cart, name='clear_cart'),
    path('stores/', views.stores, name='stores'),
    path('stores/new/', views.store_create, name='store_create'),
    path('stores/<int:pk>/edit/', views.store_edit, name='store_edit'),
    path('stores/<int:pk>/delete/', views.store_delete, name='store_delete'),
    path('products/new/', views.product_create, name='product_create'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('products/<int:pk>/delete/', views.product_delete, name='product_delete'),
    path('community/', views.reddit_feed, name='reddit_feed'),
    path('api/stores/', api_views.StoreListCreateAPI.as_view(), name='api_stores'),
    path('api/stores/<int:pk>/', api_views.StoreDetailAPI.as_view(), name='api_store_detail'),
    path('api/stores/<int:store_id>/products/', api_views.StoreProductsAPI.as_view(), name='api_store_products'),
    path('api/products/', api_views.ProductListCreateAPI.as_view(), name='api_products'),
    path('api/products/<int:pk>/', api_views.ProductDetailAPI.as_view(), name='api_product_detail'),
]
