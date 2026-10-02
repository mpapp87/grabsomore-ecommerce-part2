from django.apps import AppConfig


class EcommerceConfig(AppConfig):
    """Register the store, checkout, reviews, and API application."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'eCommerce'
