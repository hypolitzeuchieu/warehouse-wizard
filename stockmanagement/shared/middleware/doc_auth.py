"""Middleware for Swagger/ReDoc authentication."""

import logging

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.utils.deprecation import MiddlewareMixin

from infrastructure.persistence.repositories import DocumentationCredentialRepositoryImpl

logger = logging.getLogger(__name__)


class DocumentationAuthMiddleware(MiddlewareMixin):
    """Middleware to protect Swagger/ReDoc endpoints with session-based authentication."""

    def process_request(self, request: HttpRequest) -> HttpResponse | None:
        """Process request and check authentication for documentation endpoints.

        Args:
            request: HTTP request object

        Returns:
            HttpResponse if authentication fails, None if authenticated
        """
        # Only protect documentation endpoints
        if not (
            request.path.startswith("/api/v1/docs/") or request.path.startswith("/api/v1/redoc/")
        ):
            return None

        # Allow access to login and logout endpoints
        if request.path in ["/api/v1/docs/login/", "/api/v1/docs/logout/"]:
            return None

        # Check session authentication
        if request.session.get("doc_authenticated", False):
            # Verify that the credential still exists and is valid
            repository = DocumentationCredentialRepositoryImpl()
            username = request.session.get("doc_username")
            if username:
                credential = repository.get_by_username(username)
                if credential and credential.is_valid():
                    # Session is valid
                    return None
                else:
                    # Credential expired or invalid, clear session
                    logger.info(f"Documentation credential expired/invalid for {username}")
                    request.session.pop("doc_authenticated", None)
                    request.session.pop("doc_username", None)

        # Not authenticated - redirect to login
        login_url = "/api/v1/docs/login/"
        if request.path not in [login_url]:
            # Preserve the original URL for redirect after login
            next_url = request.path
            if request.GET:
                next_url += "?" + request.GET.urlencode()
            login_url += f"?next={next_url}"

        return HttpResponseRedirect(login_url)
