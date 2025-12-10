"""Documentation authentication views."""

from __future__ import annotations

import logging
import re

from django.conf import settings
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from application.use_cases.doc_credential_use_cases import AuthenticateDocCredentialUseCase
from infrastructure.persistence.repositories import DocumentationCredentialRepositoryImpl
from shared.rate_limiting.decorators import get_client_ip, rate_limit

logger = logging.getLogger(__name__)

# Rate limiting settings for documentation login
DOC_LOGIN_RATE_LIMIT_REQUESTS = getattr(settings, "DOC_LOGIN_RATE_LIMIT_REQUESTS", 5)
DOC_LOGIN_RATE_LIMIT_PERIOD = getattr(settings, "DOC_LOGIN_RATE_LIMIT_PERIOD", 900)  # 15 minutes

# Validation constants
USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 150
PASSWORD_MIN_LENGTH = 6
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


@require_http_methods(["GET", "POST"])
@csrf_protect
@rate_limit(
    requests_per_period=DOC_LOGIN_RATE_LIMIT_REQUESTS,
    period_seconds=DOC_LOGIN_RATE_LIMIT_PERIOD,
)
def doc_login_view(request):
    """Documentation login view.

    GET: Display login form
    POST: Process login credentials
    """
    # If already authenticated, redirect to docs
    if request.session.get("doc_authenticated", False):
        return redirect("/api/v1/docs/")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        # Validate username
        if not username:
            return render(
                request,
                "docs/login.html",
                {"error": "Username is required."},
                status=400,
            )

        if len(username) < USERNAME_MIN_LENGTH or len(username) > USERNAME_MAX_LENGTH:
            return render(
                request,
                "docs/login.html",
                {"error": "Invalid credentials. Please try again."},
                status=400,
            )

        # Validate username format (alphanumeric, underscore, hyphen only)
        if not USERNAME_PATTERN.match(username):
            return render(
                request,
                "docs/login.html",
                {"error": "Invalid credentials. Please try again."},
                status=400,
            )

        # Validate password
        if not password:
            return render(
                request,
                "docs/login.html",
                {"error": "Password is required."},
                status=400,
            )

        if len(password) < PASSWORD_MIN_LENGTH:
            return render(
                request,
                "docs/login.html",
                {"error": "Invalid credentials. Please try again."},
                status=400,
            )

        # Sanitize username (prevent XSS and SQL injection patterns)
        username = re.sub(r"[<>\"'%;()&+]", "", username)[:USERNAME_MAX_LENGTH]

        try:
            # Authenticate credentials
            repository = DocumentationCredentialRepositoryImpl()
            use_case = AuthenticateDocCredentialUseCase(repository)
            credential = use_case.execute(username=username, password=password)

            # Set session
            request.session["doc_authenticated"] = True
            request.session["doc_username"] = credential.username
            request.session.set_expiry(7 * 24 * 60 * 60)  # 7 days

            # Log successful login
            ip_address = get_client_ip(request)
            logger.info(
                f"Documentation login successful: {username} from {ip_address}",
                extra={"username": username, "ip_address": ip_address},
            )

            # Validate and sanitize next URL to prevent open redirect
            next_url = request.GET.get("next", "/api/v1/docs/")
            if not next_url.startswith("/api/v1/docs/") and not next_url.startswith(
                "/api/v1/redoc/"
            ):
                next_url = "/api/v1/docs/"

            return redirect(next_url)

        except Exception as e:
            # Log failed login attempt
            ip_address = get_client_ip(request)
            logger.warning(
                f"Documentation login failed: {username} from {ip_address} - {str(e)}",
                extra={"username": username, "ip_address": ip_address, "error": str(e)},
            )

            # Generic error message (don't reveal which field is wrong)
            return render(
                request,
                "docs/login.html",
                {"error": "Invalid credentials. Please try again."},
                status=401,
            )

    # GET request - show login form
    return render(request, "docs/login.html")


@require_http_methods(["GET", "POST"])
@csrf_protect
def doc_logout_view(request):
    """Documentation logout view.

    Clears the documentation session and redirects to login.
    """
    # Clear session
    if "doc_authenticated" in request.session:
        username = request.session.get("doc_username", "unknown")
        del request.session["doc_authenticated"]
        if "doc_username" in request.session:
            del request.session["doc_username"]

        # Log logout
        ip_address = get_client_ip(request)
        logger.info(
            f"Documentation logout: {username} from {ip_address}",
            extra={"username": username, "ip_address": ip_address},
        )

    # Redirect to login
    return redirect("/api/v1/docs/login/")
