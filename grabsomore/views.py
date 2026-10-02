"""Authentication, account registration, and password-recovery views."""

import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth import authenticate, login, logout, password_validation
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.contrib.auth.decorators import login_required

from django.views.decorators.http import require_POST

from .models import ResetToken


ROLE_GROUPS = {'buyer': 'Buyers', 'vendor': 'Vendors'}


def login_user(request):
    """Authenticate a user and start a normal Django session."""
    if request.method == 'POST':
        user = authenticate(
            request,
            username=request.POST.get('username', ''),
            password=request.POST.get('password', ''),
        )
        if user is not None:
            login(request, user)
            return redirect('grabsomore:welcome')
        return render(request, 'grabsomore/login.html', {
            'error': 'Invalid credentials.'
        })
    return render(request, 'grabsomore/login.html')


def register_user(request):
    """Validate credentials and assign only the chosen account role."""
    if request.method != 'POST':
        return render(request, 'grabsomore/register.html')

    username = request.POST.get('username', '').strip()
    email = request.POST.get('email', '').strip()
    password = request.POST.get('password', '')
    confirmation = request.POST.get('password_conf', '')
    role = request.POST.get('role', '')
    context = {'username': username, 'email': email, 'selected_role': role}

    if not username or not email or not password or not confirmation:
        context['error'] = 'Complete every field.'
    elif role not in ROLE_GROUPS:
        context['error'] = 'Choose a buyer or vendor account.'
    elif password != confirmation:
        context['error'] = 'Passwords do not match.'
    elif User.objects.filter(username__iexact=username).exists():
        context['error'] = 'That username is already taken.'
    elif User.objects.filter(email__iexact=email).exists():
        context['error'] = 'That email is already registered.'
    else:
        try:
            password_validation.validate_password(password)
        except ValidationError as exc:
            context['error'] = ' '.join(exc.messages)
        else:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username, email=email, password=password
                )
                group, _ = Group.objects.get_or_create(name=ROLE_GROUPS[role])
                user.groups.add(group)
            login(request, user)
            return redirect('grabsomore:welcome')
    return render(request, 'grabsomore/register.html', context)


def change_user_password(username, new_password):
    """Set an existing user's password using Django's secure hasher."""
    user = User.objects.get(username=username)
    password_validation.validate_password(new_password, user=user)
    user.set_password(new_password)
    user.save(update_fields=['password'])


@require_POST
def logout_user(request):
    """End the session only after a CSRF-protected logout submission."""
    logout(request)
    return redirect('grabsomore:login')


@login_required(login_url=reverse_lazy('grabsomore:login'))
def welcome(request):
    """Display the signed-in user’s home page and role-specific actions."""
    return render(request, 'grabsomore/welcome.html')


def build_email(user, reset_url):
    """Build the password-reset email without embedding credentials."""
    return EmailMessage(
        'Password Reset',
        f'Hi {user.username},\nUse this link to reset your password: {reset_url}',
        to=[user.email],
    )


def generate_reset_url(user, request=None):
    """Create a single-use token and reverse the real reset route."""
    token = secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode()).hexdigest()
    ResetToken.objects.create(
        user=user,
        token=digest,
        expiry_date=timezone.now() + timedelta(minutes=30),
    )
    path = reverse('grabsomore:password_reset_form', kwargs={'token': token})
    return request.build_absolute_uri(path) if request is not None else path


def send_password_reset(request):
    """Email a reset link without disclosing whether the address exists."""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        user = User.objects.filter(email__iexact=email).first()
        if user:
            build_email(user, generate_reset_url(user, request)).send()
        return render(request, 'grabsomore/reset_email_sent.html', {
            'email': email
        })
    return render(request, 'grabsomore/request_password_reset.html')


def reset_user_password(request, token):
    """Validate an unexpired token and present the reset form."""
    digest = hashlib.sha256(token.encode()).hexdigest()
    reset_token = ResetToken.objects.filter(token=digest, used=False).first()
    if not reset_token:
        return render(request, 'grabsomore/password_reset_invalid.html')
    if reset_token.expiry_date <= timezone.now():
        reset_token.delete()
        return render(request, 'grabsomore/password_reset_expired.html')
    request.session['reset_token'] = token
    return render(request, 'grabsomore/password_reset.html', {'token': token})


def reset_password(request):
    """Consume a valid reset token and change the owner's password."""
    if request.method != 'POST':
        return redirect('grabsomore:login')
    token = request.session.get('reset_token')
    if not token:
        return render(request, 'grabsomore/password_reset_invalid.html')
    digest = hashlib.sha256(token.encode()).hexdigest()
    reset_token = ResetToken.objects.select_related('user').filter(
        token=digest, used=False
    ).first()
    if not reset_token:
        return render(request, 'grabsomore/password_reset_invalid.html')
    if reset_token.expiry_date <= timezone.now():
        reset_token.delete()
        return render(request, 'grabsomore/password_reset_expired.html')

    password = request.POST.get('password', '')
    confirmation = request.POST.get('password_conf', '')
    context = {'token': token}
    if not password or password != confirmation:
        context['error'] = 'Enter matching passwords.'
        return render(request, 'grabsomore/password_reset.html', context)
    try:
        password_validation.validate_password(password, user=reset_token.user)
    except ValidationError as exc:
        context['error'] = ' '.join(exc.messages)
        return render(request, 'grabsomore/password_reset.html', context)

    with transaction.atomic():
        reset_token.used = True
        reset_token.save(update_fields=['used'])
        reset_token.user.set_password(password)
        reset_token.user.save(update_fields=['password'])
    request.session.pop('reset_token', None)
    return HttpResponseRedirect(reverse('grabsomore:login'))
