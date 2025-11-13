"""Middleware for Swagger/ReDoc authentication."""

import base64

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

from shared.response.mixin import ResponseMixin


class DocumentationAuthMiddleware(MiddlewareMixin):
    """Middleware to protect Swagger/ReDoc endpoints with basic authentication."""

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

        # Check if authentication is required
        doc_username = getattr(settings, "DOC_USERNAME", None)
        doc_password = getattr(settings, "DOC_PASSWORD", None)

        if not doc_username or not doc_password:
            # If credentials are not set, allow access (for development)
            return None

        # Check for Authorization header
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")

        if not auth_header.startswith("Basic "):
            return self._unauthorized_response()

        # Decode credentials
        try:
            encoded = auth_header.split(" ")[1]
            decoded = base64.b64decode(encoded).decode("utf-8")
            username, password = decoded.split(":", 1)
        except (ValueError, IndexError):
            return self._unauthorized_response()

        # Authenticate - check credentials directly
        if username != doc_username or password != doc_password:
            return self._unauthorized_response()

        return None

    def _unauthorized_response(self) -> HttpResponse:
        """Return 401 Unauthorized response.

        Returns:
            HttpResponse with 401 status
        """
        response = ResponseMixin.error(
            message="Authentication required to access documentation",
            status_code=401,
            code="UNAUTHORIZED",
        )
        response["WWW-Authenticate"] = 'Basic realm="Documentation"'
        return response
