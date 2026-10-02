"""Compatibility helpers for password-reset emails and links."""

from .views import build_email, generate_reset_url

__all__ = ['build_email', 'generate_reset_url']
