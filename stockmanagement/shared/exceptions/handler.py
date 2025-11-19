"""Custom exception handler for Django REST Framework."""

from __future__ import annotations

import logging
from typing import Any

from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    MethodNotAllowed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    Throttled,
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

        # Special handling for refresh token expiration
        user_message = exc.detail
        if exc.code == "INVALID_REFRESH_TOKEN":
            error_detail_lower = exc.detail.lower()
            if "expired" in error_detail_lower:
                user_message = (
                    "Your refresh token has expired. " "Please login again to get new tokens."
                )
                logger.info(
                    "Refresh token expired - user needs to login again",
                    extra={"context": context},
                )
            elif "blacklisted" in error_detail_lower:
                user_message = (
                    "Your refresh token has been revoked (logged out). " "Please login again."
                )
                logger.info(
                    "Refresh token blacklisted - user needs to login again",
                    extra={"context": context},
                )

        response_data: dict[str, Any] = {
            "success": False,
            "error": {
                "code": exc.code,
                "message": user_message,
                "details": details,
            },
            "status_code": exc.status_code,
        }
        return Response(response_data, status=exc.status_code)

    # Handle InvalidToken (JWT blacklist) - expected behavior, no need for traceback
    if isinstance(exc, InvalidToken):
        error_detail = str(exc)
        error_detail_lower = error_detail.lower()

        # Determine user-friendly message based on error type
        if "blacklisted" in error_detail_lower:
            # Token blacklisted - this is expected behavior after logout
            user_message = "Token has been blacklisted (logged out)"
            logger.info(
                f"Token blacklisted attempt - {error_detail}",
                extra={"context": context},
            )
        elif "wrong type" in error_detail_lower or "token_not_valid" in error_detail_lower:
            # Token has wrong type (e.g., using refresh token as access token)
            user_message = (
                "Invalid token type. Please use an access token for this request. "
                "If you're using a refresh token, use the /auth/refresh-token/ endpoint instead."
            )
            logger.info(
                f"Wrong token type used - {error_detail}",
                extra={"context": context},
            )
        elif "expired" in error_detail_lower:
            # Token expired
            user_message = "Token has expired. Please refresh your token or login again."
            logger.info(
                f"Expired token attempt - {error_detail}",
                extra={"context": context},
            )
        elif "not valid" in error_detail_lower:
            # Generic invalid token
            user_message = "Invalid token. Please check your token and try again."
            logger.info(
                f"Invalid token attempt - {error_detail}",
                extra={"context": context},
            )
        else:
            # Other InvalidToken errors - use original message but log as info
            user_message = "Invalid token. Please check your token and try again."
            logger.info(
                f"Invalid token: {error_detail}",
                extra={"context": context},
            )

        token_response: dict[str, Any] = {
            "success": False,
            "error": {
                "code": "TOKEN_INVALID",
                "message": user_message,
                "details": {},
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
        # Extract meaningful message from exception if available
        error_message = (
            str(exc.detail)
            if hasattr(exc, "detail")
            else "You do not have permission to perform this action."
        )
        permission_response: dict[str, Any] = {
            "success": False,
            "error": {
                "code": "PERMISSION_DENIED",
                "message": error_message,
                "details": {"detail": str(exc)},
            },
            "status_code": status.HTTP_403_FORBIDDEN,
        }
        return Response(permission_response, status=status.HTTP_403_FORBIDDEN)

    if isinstance(exc, NotFound):
        # Not found is expected - log without traceback
        logger.info(
            f"Resource not found: {str(exc)}",
            extra={"context": context},
        )
        # Extract meaningful message from exception if available
        error_message = (
            str(exc.detail) if hasattr(exc, "detail") else "The requested resource was not found."
        )
        not_found_response: dict[str, Any] = {
            "success": False,
            "error": {
                "code": "NOT_FOUND",
                "message": error_message,
                "details": {"detail": str(exc)},
            },
            "status_code": status.HTTP_404_NOT_FOUND,
        }
        return Response(not_found_response, status=status.HTTP_404_NOT_FOUND)

    if isinstance(exc, MethodNotAllowed):
        logger.info(
            f"Method not allowed: {str(exc)}",
            extra={"context": context},
        )
        error_message = (
            str(exc.detail)
            if hasattr(exc, "detail")
            else f"Method '{getattr(exc, 'method', 'UNKNOWN')}' not allowed."
        )
        method_not_allowed_response: dict[str, Any] = {
            "success": False,
            "error": {
                "code": "METHOD_NOT_ALLOWED",
                "message": error_message,
                "details": {
                    "detail": str(exc),
                    "allowed_methods": getattr(exc, "allowed_methods", []),
                },
            },
            "status_code": status.HTTP_405_METHOD_NOT_ALLOWED,
        }
        return Response(method_not_allowed_response, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    if isinstance(exc, Throttled):
        # Rate limit exceeded - log without traceback
        logger.info(
            f"Rate limit exceeded: {str(exc)}",
            extra={"context": context},
        )
        # Extract retry_after from exception if available
        retry_after = None
        if hasattr(exc, "wait"):
            retry_after = int(exc.wait) if exc.wait else None

        error_message = (
            str(exc.detail)
            if hasattr(exc, "detail")
            else "Rate limit exceeded. Please try again later."
        )
        throttled_response: dict[str, Any] = {
            "success": False,
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": error_message,
                "details": {
                    "detail": str(exc),
                    "retry_after": retry_after,
                },
            },
            "status_code": status.HTTP_429_TOO_MANY_REQUESTS,
        }
        return Response(throttled_response, status=status.HTTP_429_TOO_MANY_REQUESTS)

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

        # Create a meaningful error message from validation details
        error_messages = []
        if isinstance(validation_details, dict):
            for field, error_list in validation_details.items():
                if isinstance(error_list, list):
                    for error in error_list:
                        if isinstance(error, dict):
                            error_messages.append(f"{field}: {str(error)}")
                        else:
                            field_name = field.replace("_", " ").title()
                            error_messages.append(f"{field_name}: {str(error)}")
                else:
                    field_name = field.replace("_", " ").title()
                    error_messages.append(f"{field_name}: {str(error_list)}")

        meaningful_message = (
            ". ".join(error_messages)
            if error_messages
            else "Validation error. Please check your input."
        )

        logger.info(
            f"Validation error: {meaningful_message}",
            extra={"context": context, "details": validation_details},
        )
        validation_response: dict[str, Any] = {
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": meaningful_message,
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
        errors = (
            response.data if isinstance(response.data, dict) else {"detail": str(response.data)}
        )

        # Check if this is a token error that needs special handling
        error_str = str(detail).lower()
        error_messages = errors.get("messages", [])

        # Detect token-related errors from DRF response
        if (
            "token" in error_str
            or "token_not_valid" in str(errors).lower()
            or "wrong type" in error_str
            or any("token" in str(msg).lower() for msg in error_messages if isinstance(msg, dict))
        ):
            # Extract token error message
            if isinstance(error_messages, list) and error_messages:
                # Try to extract message from messages array
                for msg in error_messages:
                    if isinstance(msg, dict):
                        msg_text = str(msg.get("message", "")).lower()
                        if "wrong type" in msg_text:
                            user_message = (
                                "Invalid token type. Please use an access token for this request. "
                                "If you're using a refresh token, use the /auth/refresh-token/ "
                                "endpoint instead."
                            )
                            logger.info(
                                f"Wrong token type used - {detail}",
                                extra={"context": context},
                            )
                            api_error_response = {
                                "success": False,
                                "error": {
                                    "code": "TOKEN_INVALID",
                                    "message": user_message,
                                    "details": {},
                                },
                                "status_code": status.HTTP_401_UNAUTHORIZED,
                            }
                            return Response(api_error_response, status=status.HTTP_401_UNAUTHORIZED)

            # Generic token error
            user_message = "Invalid token. Please check your token and try again."
            logger.info(
                f"Token error from DRF handler - {detail}",
                extra={"context": context},
            )
            api_error_response = {
                "success": False,
                "error": {
                    "code": "TOKEN_INVALID",
                    "message": user_message,
                    "details": {},
                },
                "status_code": status.HTTP_401_UNAUTHORIZED,
            }
            return Response(api_error_response, status=status.HTTP_401_UNAUTHORIZED)

        # Handle other DRF errors
        if isinstance(detail, list):
            detail = detail[0] if detail else "An error occurred"
        elif isinstance(detail, dict):
            detail = str(detail)

        api_error_response = {
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
