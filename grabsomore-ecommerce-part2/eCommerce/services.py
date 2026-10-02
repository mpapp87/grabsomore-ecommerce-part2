"""Transactional checkout and retryable invoice email delivery."""

import logging
from smtplib import SMTPException

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Invoice, InvoiceItem, Product

logger = logging.getLogger(__name__)


@transaction.atomic
def checkout_cart(buyer, cart, token):
    """Save one invoice and deduct stock atomically, rejecting stale carts."""
    get_user_model().objects.select_for_update().get(pk=buyer.pk)
    # Reuse a completed checkout if the browser repeats its submission.
    existing = Invoice.objects.filter(buyer=buyer, checkout_token=token).first()
    if existing:
        return existing
    if not isinstance(cart, dict) or not cart:
        raise ValueError('Your cart is empty.')
    if any(not isinstance(key, str) or not key.isdigit() or
           type(qty) is not int or qty <= 0 for key, qty in cart.items()):
        raise ValueError('Your cart contains an invalid quantity or product.')
    products = list(Product.objects.select_for_update().filter(pk__in=cart).order_by('pk'))
    if len(products) != len(cart):
        raise ValueError('A product is no longer available. Clear your cart and select products again.')
    # All stock changes and invoice rows roll back together on an invalid line.
    invoice = Invoice.objects.create(buyer=buyer, checkout_token=token, email=buyer.email)
    for product in products:
        quantity = cart[str(product.pk)]
        if product.price < 0 or not Product.objects.filter(
                pk=product.pk, stock__gte=quantity).update(stock=F('stock') - quantity):
            raise ValueError(f'{product.name} is unavailable in the requested quantity.')
        InvoiceItem.objects.create(invoice=invoice, product=product,
                                   product_name=product.name,
                                   unit_price=product.price, quantity=quantity)
    return invoice


def email_invoice(invoice):
    """Send a saved invoice; retain failed deliveries for an explicit retry."""
    with transaction.atomic():
        invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
        if invoice.emailed_at:
            return True
        # Retry only delivery; the purchase and its prices were already saved.
        body = render_to_string('eCommerce/invoice_email.txt', {'invoice': invoice})
        try:
            sent = send_mail(f'Invoice #{invoice.pk}', body, settings.DEFAULT_FROM_EMAIL,
                             [invoice.email], fail_silently=False)
        except (SMTPException, OSError):
            logger.exception('Invoice %s email delivery failed', invoice.pk)
            return False
        if sent != 1:
            return False
        invoice.emailed_at = timezone.now()
        invoice.save(update_fields=['emailed_at'])
        return True
