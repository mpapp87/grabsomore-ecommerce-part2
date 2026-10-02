"""Shared role flags used by the site-wide navigation bar."""


def navigation(request):
    """Load role names once per rendered page without trusting client input."""
    roles = set(request.user.groups.values_list('name', flat=True)) if request.user.is_authenticated else set()
    return {'nav_buyer': 'Buyers' in roles, 'nav_vendor': 'Vendors' in roles}
