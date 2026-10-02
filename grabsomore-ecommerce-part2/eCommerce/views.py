"""Buyer catalog/cart and owner-restricted vendor management views."""

from decimal import Decimal, InvalidOperation

from uuid import UUID, uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef, Q
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ProductForm, StoreForm, ReviewForm
from .models import Product, Store, Invoice, Review, InvoiceItem
from .services import checkout_cart, email_invoice
from .functions.reddit import get_reddit_posts


def is_vendor(user):
    """Check a user's assigned role, not a browser-provided field."""
    return user.is_authenticated and user.groups.filter(name='Vendors').exists()


def require_vendor(user):
    """Reject requests from accounts without the vendor role."""
    if not is_vendor(user):
        raise PermissionDenied('A vendor account is required.')


def is_buyer(user):
    """Check the authenticated account for the buyer role."""
    return user.is_authenticated and user.groups.filter(name='Buyers').exists()


@login_required
def list_products(request):
    """Display the catalog with role-appropriate shopping controls."""
    require_catalog_role(request.user)
    products = Product.objects.select_related('store', 'store__owner').order_by('name', 'pk')
    return render(request, 'eCommerce/products_list.html', {
        'products': Paginator(products, 24).get_page(request.GET.get('page')),
        'heading': 'All products', 'is_vendor': is_vendor(request.user),
        'is_buyer': is_buyer(request.user),
    })


@login_required
def view_product_page(request):
    """Find a product by name and display its details and reviews."""
    product = None
    error = None
    if request.method == 'POST':
        search = request.POST.get('product', '').strip()
        if not search:
            error = 'Enter a product name.'
        else:
            product = Product.objects.filter(name__iexact=search).first()
            if product is None:
                error = 'Product not found.'
    return render(request, 'eCommerce/product_page.html', {
        'product': product, 'error': error, 'is_buyer': is_buyer(request.user),
    })


@login_required
def stores(request):
    """Show only the current vendor's stores."""
    require_vendor(request.user)
    return render(request, 'eCommerce/stores.html', {
        'stores': Paginator(Store.objects.filter(owner=request.user).order_by('name', 'pk'), 24).get_page(request.GET.get('page')),
        'heading': 'My Stores', 'manage_stores': True,
    })


@login_required
def store_create(request):
    """Create a store owned by the current vendor."""
    require_vendor(request.user)
    form = StoreForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        store = form.save(commit=False)
        store.owner = request.user
        store.save()
        return redirect('eCommerce:stores')
    return render(request, 'eCommerce/vendor_form.html', {
        'form': form, 'heading': 'Create store',
    })


@login_required
def store_edit(request, pk):
    """Edit a store only when it belongs to the current vendor."""
    require_vendor(request.user)
    store = get_object_or_404(Store, pk=pk, owner=request.user)
    form = StoreForm(request.POST or None, instance=store)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('eCommerce:stores')
    return render(request, 'eCommerce/vendor_form.html', {
        'form': form, 'heading': 'Edit store',
    })


@login_required
@require_POST
def store_delete(request, pk):
    """Delete a store belonging to the current vendor on POST."""
    require_vendor(request.user)
    get_object_or_404(Store, pk=pk, owner=request.user).delete()
    return redirect('eCommerce:stores')


@login_required
def product_create(request):
    """Create a product in one of the current vendor’s stores."""
    require_vendor(request.user)
    form = ProductForm(request.POST or None, owner=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('eCommerce:stores')
    return render(request, 'eCommerce/vendor_form.html', {
        'form': form, 'heading': 'Create product',
    })


@login_required
def product_edit(request, pk):
    """Edit a product owned by the current vendor."""
    require_vendor(request.user)
    product = get_object_or_404(Product, pk=pk, store__owner=request.user)
    form = ProductForm(request.POST or None, instance=product,
                       owner=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('eCommerce:stores')
    return render(request, 'eCommerce/vendor_form.html', {
        'form': form, 'heading': 'Edit product',
    })


@login_required
@require_POST
def product_delete(request, pk):
    """Delete an owned product on POST."""
    require_vendor(request.user)
    get_object_or_404(Product, pk=pk, store__owner=request.user).delete()
    return redirect('eCommerce:stores')


@login_required
def change_product_price(request):
    """Legacy price form, restricted to the vendor's own products."""
    require_vendor(request.user)
    if request.method == 'POST':
        name = request.POST.get('product', '').strip()
        try:
            price = Decimal(request.POST.get('new_price', ''))
            if not price.is_finite() or price < 0 or price > Decimal('99999999.99'):
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            return render(request, 'eCommerce/change_price.html', {
                'error': 'Enter a valid nonnegative price.'
            })
        product = Product.objects.filter(
            name=name, store__owner=request.user
        ).first()
        if product is None:
            return render(request, 'eCommerce/change_price.html', {
                'error': 'Product not found in your stores.'
            })
        product.price = price
        product.full_clean()
        product.save(update_fields=['price'])
        return redirect('eCommerce:stores')
    return render(request, 'eCommerce/change_price.html')


@login_required
@require_POST
def add_item_to_cart(request):
    """Add a positive quantity to a buyer’s session cart within stock limits."""
    if not is_buyer(request.user):
        raise PermissionDenied('A buyer account is required.')
    try:
        product_id = int(request.POST.get('item', ''))
        quantity = int(request.POST.get('quantity', ''))
    except (ValueError, TypeError):
        return HttpResponseBadRequest('Choose a valid product and quantity.')
    if quantity <= 0:
        return HttpResponseBadRequest('Quantity must be positive.')
    product = get_object_or_404(Product, pk=product_id)
    cart = request.session.get('cart', {})
    key = str(product.pk)
    new_quantity = cart.get(key, 0) + quantity
    if new_quantity > product.stock:
        return HttpResponseBadRequest('Requested quantity exceeds stock.')
    cart[key] = new_quantity
    request.session.pop('checkout_token', None)
    request.session['cart'] = cart
    return redirect('eCommerce:main_cart_page')


def retrieve_products(request):
    """Resolve session cart IDs and ignore removed products."""
    cart = request.session.get('cart', {})
    products = Product.objects.filter(pk__in=cart.keys()).select_related('store')
    return [
        {'product': product, 'quantity': cart[str(product.pk)]}
        for product in products
    ]


@login_required
def show_user_cart(request):
    """Display the buyer’s cart and calculate its current total."""
    if not is_buyer(request.user):
        raise PermissionDenied('A buyer account is required.')
    items = retrieve_products(request)
    total = Decimal('0.00')
    for item in items:
        item['subtotal'] = item['product'].price * item['quantity']
        total += item['subtotal']
    token = request.session.setdefault('checkout_token', str(uuid4()))
    return render(request, 'eCommerce/main_cart_page.html', {
        'cart': items, 'total_price': total, 'checkout_token': token,
    })


@login_required
@require_POST
def clear_cart(request):
    """Clear the authenticated buyer’s session cart on POST."""
    if not is_buyer(request.user):
        raise PermissionDenied('A buyer account is required.')
    request.session.pop('checkout_token', None)
    request.session['cart'] = {}
    return redirect('eCommerce:main_cart_page')


@login_required
@require_POST
def checkout(request):
    """Complete a buyer checkout, clear the cart, and attempt invoice delivery."""
    if not is_buyer(request.user):
        raise PermissionDenied('A buyer account is required.')
    try:
        token = UUID(request.POST.get('checkout_token', ''))
    except (ValueError, TypeError, AttributeError):
        return HttpResponseBadRequest('Reload your cart before checking out.')
    existing = Invoice.objects.filter(buyer=request.user, checkout_token=token).first()
    if existing:
        return redirect('eCommerce:invoice_detail', pk=existing.pk)
    if str(token) != request.session.get('checkout_token'):
        return HttpResponseBadRequest('Your cart changed. Reload it before checking out.')
    try:
        validate_email(request.user.email)
    except ValidationError:
        messages.error(request, 'A valid account email address is required for checkout.')
        return redirect('eCommerce:main_cart_page')
    try:
        invoice = checkout_cart(request.user, request.session.get('cart', {}), token)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('eCommerce:main_cart_page')
    # Clear only after the purchase transaction succeeds; SMTP may be retried.
    request.session['cart'] = {}
    request.session.pop('checkout_token', None)
    if email_invoice(invoice):
        messages.success(request, 'Checkout complete. Your invoice was sent to the email backend.')
    else:
        messages.warning(request, 'Checkout complete, but email delivery failed. Retry from this invoice.')
    return redirect('eCommerce:invoice_detail', pk=invoice.pk)


@login_required
def invoice_detail(request, pk):
    """Display an invoice only to the buyer who placed the order."""
    invoice = get_object_or_404(Invoice, pk=pk, buyer=request.user)
    return render(request, 'eCommerce/invoice.html', {'invoice': invoice})


@login_required
def invoice_list(request):
    """List the current user's invoices, including failed email deliveries."""
    return render(request, 'eCommerce/invoices.html', {
        'invoices': Invoice.objects.filter(buyer=request.user).order_by('-pk'),
    })


@login_required
@require_POST
def retry_invoice_email(request, pk):
    """Retry an unsent invoice email without repeating checkout or stock changes."""
    invoice = get_object_or_404(Invoice, pk=pk, buyer=request.user)
    if email_invoice(invoice):
        messages.success(request, 'Invoice sent to the email backend.')
    else:
        messages.error(request, 'Email delivery failed. Please try again later.')
    return redirect('eCommerce:invoice_detail', pk=invoice.pk)


@login_required
def product_detail(request, pk):
    """Display an exact product and its reviews using its stable primary key."""
    return render(request, 'eCommerce/product_page.html', {
        'product': get_object_or_404(Product, pk=pk),
        'is_buyer': is_buyer(request.user),
    })


@login_required
def review_create(request, pk):
    """Let a buyer create or update their own review; never accept a verified flag."""
    if not is_buyer(request.user):
        raise PermissionDenied('A buyer account is required.')
    product = get_object_or_404(Product, pk=pk)
    review = Review.objects.filter(buyer=request.user, product=product).first()
    form = ReviewForm(request.POST if request.method == 'POST' else None, instance=review)
    if request.method == 'POST' and form.is_valid():
        # Ignore submitted buyer IDs and verification flags.
        Review.objects.update_or_create(buyer=request.user, product=product,
                                        defaults=form.cleaned_data)
        return redirect('eCommerce:product_detail', pk=pk)
    return render(request, 'eCommerce/review_form.html', {'form': form, 'product': product})


def require_catalog_role(user):
    """Allow catalogue browsing only for authenticated buyers or vendors."""
    if not (is_buyer(user) or is_vendor(user)):
        raise PermissionDenied('A buyer or vendor account is required.')


@login_required
def vendors(request):
    """List vendor accounts with links to each vendor's stores."""
    require_catalog_role(request.user)
    users = get_user_model().objects.filter(groups__name='Vendors', is_active=True).annotate(store_count=Count('stores', distinct=True)).order_by('username', 'pk')
    return render(request, 'eCommerce/vendors.html', {'vendors': Paginator(users, 24).get_page(request.GET.get('page'))})


@login_required
def vendor_stores(request, vendor_id):
    """Show only the selected vendor's stores to either catalogue role."""
    require_catalog_role(request.user)
    vendor = get_object_or_404(get_user_model(), pk=vendor_id, groups__name='Vendors', is_active=True)
    stores = Store.objects.filter(owner=vendor).select_related('owner').order_by('name', 'pk')
    return render(request, 'eCommerce/stores.html', {
        'stores': Paginator(stores, 24).get_page(request.GET.get('page')),
        'heading': f'Stores by {vendor.username}', 'vendor': vendor,
        'manage_stores': is_vendor(request.user) and vendor.pk == request.user.pk,
    })


@login_required
def all_stores(request):
    """Provide a direct directory of all stores without visiting the vendor list."""
    require_catalog_role(request.user)
    stores = Store.objects.select_related('owner').order_by('name', 'pk')
    return render(request, 'eCommerce/stores.html', {
        'stores': Paginator(stores, 24).get_page(request.GET.get('page')), 'heading': 'All stores',
    })


@login_required
def store_products(request, pk):
    """List only the selected store's products with owner-only management links."""
    require_catalog_role(request.user)
    store = get_object_or_404(Store.objects.select_related('owner'), pk=pk)
    products = store.products.select_related('store', 'store__owner').order_by('name', 'pk')
    return render(request, 'eCommerce/products_list.html', {
        'products': Paginator(products, 24).get_page(request.GET.get('page')),
        'store': store, 'heading': f'Products in {store.name}',
        'is_buyer': is_buyer(request.user), 'manage_products': is_vendor(request.user) and store.owner_id == request.user.pk,
    })


@login_required
def my_products(request):
    """Give a vendor a direct product-management entry point across owned stores."""
    require_vendor(request.user)
    products = Product.objects.filter(store__owner=request.user).select_related('store').order_by('name', 'pk')
    return render(request, 'eCommerce/products_list.html', {
        'products': Paginator(products, 24).get_page(request.GET.get('page')),
        'heading': 'My Products', 'manage_products': True,
    })


@login_required
def vendor_reviews(request):
    """Show only reviews of the vendor's products, with search and store filters."""
    require_vendor(request.user)
    purchases = InvoiceItem.objects.filter(invoice__buyer_id=OuterRef('buyer_id'), product_id=OuterRef('product_id'))
    reviews = Review.objects.filter(product__store__owner=request.user).select_related('buyer', 'product', 'product__store').annotate(verified_purchase=Exists(purchases))
    query = request.GET.get('q', '').strip()
    selected_store = request.GET.get('store', '')
    if selected_store:
        store = get_object_or_404(Store, pk=selected_store if selected_store.isdecimal() else 0, owner=request.user)
        reviews = reviews.filter(product__store=store)
    if query:
        reviews = reviews.filter(Q(product__name__icontains=query) | Q(comment__icontains=query) | Q(buyer__username__icontains=query))
    return render(request, 'eCommerce/vendor_reviews.html', {
        'reviews': Paginator(reviews, 20).get_page(request.GET.get('page')),
        'stores': Store.objects.filter(owner=request.user).order_by('name'),
        'query': query, 'selected_store': selected_store,
    })


@login_required
@require_POST
def review_delete(request, pk):
    """Delete only the requesting buyer's review; verification remains derived."""
    if not is_buyer(request.user):
        raise PermissionDenied('A buyer account is required.')
    review = get_object_or_404(Review, pk=pk, buyer=request.user)
    product_id = review.product_id
    review.delete()
    return redirect('eCommerce:product_detail', pk=product_id)


@login_required
def api_directory(request):
    """Expose the browsable API entry points and vendor creation instructions."""
    require_catalog_role(request.user)
    return render(request, 'eCommerce/api_directory.html')


def reddit_feed(request):
    """Render original Reddit discussions using the task's external API helper."""
    posts = get_reddit_posts('BuyItForLife', limit=10)
    return render(request, 'eCommerce/reddit_feed.html', {'posts': posts})
