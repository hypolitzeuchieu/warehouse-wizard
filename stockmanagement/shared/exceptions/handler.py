"""Custom exception handler for Django REST Framework."""

from __future__ import annotations

import logging
from typing import Any

from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler
from rest_framework_simplejwt.exceptions import InvalidToken

from shared.exceptions.base import BaseAPIException

logger = logging.getLogger(__name__)


def custom_exception_handler(exc: Exception, context: dict) -> Response | None:
    """
    Custom exception handler that uses ResponseMixin for standardized error responses.

    Args:
        exc: Exception instance
        context: Request context

    Returns:
        Response with standardized error format or None to use default handler
    """
    # Handle BaseAPIException first
    if isinstance(exc, BaseAPIException):
        # Only log with traceback for server errors (500+), not for business logic errors
        if exc.status_code >= 500:
            logger.error(
                f"[{exc.code}] {exc.detail}",
                exc_info=True,
                extra={
                    "error_code": exc.code,
                    "status_code": exc.status_code,
                    "details": exc.details,
                    "context": context,
                },
            )
        else:
            # Business logic errors: log without traceback, just structured info
            logger.warning(
                f"[{exc.code}] {exc.detail}",
                extra={
                    "error_code": exc.code,
                    "status_code": exc.status_code,
                    "details": exc.details,
                    "context": context,
                },
            )
        details: dict[str, Any] = {}
        if exc.details:
            if isinstance(exc.details, str):
                details = {"message": exc.details}
            elif isinstance(exc.details, list):
                details = {"messages": exc.details}
            elif isinstance(exc.details, dict):
                details = exc.details

        response_data: dict[str, Any] = {
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.detail,
                "details": details,
            },
            "status_code": exc.status_code,
        }
        return Response(response_data, status=exc.status_code)

    # Handle InvalidToken (JWT blacklist) - expected behavior, no need for traceback
    if isinstance(exc, InvalidToken):
        error_detail = str(exc)
        if "blacklisted" in error_detail.lower():
            # Token blacklisted - this is expected behavior after logout
            logger.info(
                f"Token blacklisted attempt - {error_detail}",
                extra={"context": context},
            )
        else:
            # Other InvalidToken errors - log as warning without traceback
            logger.warning(
                f"Invalid token: {error_detail}",
                extra={"context": context},
            )

        token_response: dict[str, Any] = {
            "success": False,
            "error": {
                "code": "TOKEN_INVALID",
                "message": (
                    error_detail
                    if "blacklisted" not in error_detail.lower()
                    else "Token has been blacklisted (logged out)"
                ),
                "details": {"detail": error_detail},
            },
            "status_code": status.HTTP_401_UNAUTHORIZED,
        }
        return Response(token_response, status=status.HTTP_401_UNAUTHORIZED)

    # Log other exceptions for debugging (these are unexpected)
    logger.error(
        f"Exception occurred: {type(exc).__name__} - {str(exc)}",
        exc_info=True,
        extra={"context": context},
    )

    # Handle DRF built-in exceptions with proper status codes
    if isinstance(exc, NotAuthenticated):
        # Missing authentication is expected - log without traceback
        logger.info(
            "Authentication credentials not provided",
            extra={"context": context},
        )
        not_auth_response: dict[str, Any] = {
            "success": False,
            "error": {
                "code": "NOT_AUTHENTICATED",
                "message": "Authentication credentials were not provided.",
                "details": {},
            },
            "status_code": status.HTTP_401_UNAUTHORIZED,
        }
        return Response(not_auth_response, status=status.HTTP_401_UNAUTHORIZED)

    if isinstance(exc, AuthenticationFailed):
        # Authentication failures are expected - log without traceback
        logger.info(
            f"Authentication failed: {str(exc)}",
            extra={"context": context},
        )
        auth_failed_response: dict[str, Any] = {
            "success": False,
            "error": {
                "code": "AUTHENTICATION_FAILED",
                "message": "Invalid authentication credentials.",
                "details": {"detail": str(exc)},
            },
            "status_code": status.HTTP_401_UNAUTHORIZED,
        }
        return Response(auth_failed_response, status=status.HTTP_401_UNAUTHORIZED)

    if isinstance(exc, PermissionDenied):
        # Permission denied is expected - log without traceback
        logger.info(
            f"Permission denied: {str(exc)}",
            extra={"context": context},
        )
        permission_response: dict[str, Any] = {
            "success": False,
            "error": {
                "code": "PERMISSION_DENIED",
                "message": "You do not have permission to perform this action.",
                "details": {"detail": str(exc)},
            },
            "status_code": status.HTTP_403_FORBIDDEN,
        }
        return Response(permission_response, status=status.HTTP_403_FORBIDDEN)

    if isinstance(exc, ValidationError):
        # Validation errors are expected - log without traceback
        validation_details: dict[str, Any] = {}
        if hasattr(exc, "detail"):
            if isinstance(exc.detail, dict):
                validation_details = exc.detail
            elif isinstance(exc.detail, list):
                validation_details = {"messages": exc.detail}
            else:
                validation_details = {"message": str(exc.detail)}
        else:
            validation_details = {"detail": str(exc)}

        logger.info(
            f"Validation error: {str(exc)}",
            extra={"context": context, "details": validation_details},
        )
        validation_response: dict[str, Any] = {
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Validation error",
                "details": validation_details,
            },
            "status_code": status.HTTP_400_BAD_REQUEST,
        }
        return Response(validation_response, status=status.HTTP_400_BAD_REQUEST)

    # Use default DRF exception handler for other exceptions
    response = exception_handler(exc, context)

    if response is not None:
        # Convert DRF response to our standardized format
        detail = response.data.get("detail", "An error occurred")
        if isinstance(detail, list):
            detail = detail[0] if detail else "An error occurred"
        elif isinstance(detail, dict):
            detail = str(detail)

        errors = (
            response.data if isinstance(response.data, dict) else {"detail": str(response.data)}
        )

        api_error_response: dict[str, Any] = {
            "success": False,
            "error": {
                "code": "API_ERROR",
                "message": str(detail),
                "details": errors,
            },
            "status_code": response.status_code,
        }
        return Response(api_error_response, status=response.status_code)

    # For unhandled exceptions, return 500
    logger.exception("Unhandled exception occurred")
    internal_error_response: dict[str, Any] = {
        "success": False,
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An internal server error occurred.",
            "details": {},
        },
        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
    }
    return Response(internal_error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
