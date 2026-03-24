"""Specific exception classes for common HTTP errors."""

from __future__ import annotations

from typing import Any

from shared.exceptions.base import BaseAPIException


class NotFoundError(BaseAPIException):
    """Exception for 404 Not Found errors."""

    def __init__(
        self,
        detail: str = "Resource not found",
        code: str = "NOT_FOUND",
        details: dict[str, Any] | list[str] | str | None = None,
    ) -> None:
        """Initialize NotFoundError."""
        super().__init__(
            detail=detail,
            code=code,
            status_code=404,
            details=details,
        )


class ForbiddenError(BaseAPIException):
    """Exception for 403 Forbidden errors."""

    def __init__(
        self,
        detail: str = "You do not have permission to perform this action",
        code: str = "PERMISSION_DENIED",
        details: dict[str, Any] | list[str] | str | None = None,
    ) -> None:
        """Initialize ForbiddenError."""
        super().__init__(
            detail=detail,
            code=code,
            status_code=403,
            details=details,
        )


class BadRequestError(BaseAPIException):
    """Exception for 400 Bad Request errors."""

    def __init__(
        self,
        detail: str = "Invalid request",
        code: str = "BAD_REQUEST",
        details: dict[str, Any] | list[str] | str | None = None,
    ) -> None:
        """Initialize BadRequestError."""
        super().__init__(
            detail=detail,
            code=code,
            status_code=400,
            details=details,
        )


class UnauthorizedError(BaseAPIException):
    """Exception for 401 Unauthorized errors."""

    def __init__(
        self,
        detail: str = "Authentication required",
        code: str = "UNAUTHORIZED",
        details: dict[str, Any] | list[str] | str | None = None,
    ) -> None:
        """Initialize UnauthorizedError."""
        super().__init__(
            detail=detail,
            code=code,
            status_code=401,
            details=details,
        )


class InternalServerError(BaseAPIException):
    """Exception for 500 Internal Server Error."""

    def __init__(
        self,
        detail: str = "An internal server error occurred",
        code: str = "INTERNAL_ERROR",
        details: dict[str, Any] | list[str] | str | None = None,
    ) -> None:
        """Initialize InternalServerError."""
        super().__init__(
            detail=detail,
            code=code,
            status_code=500,
            details=details,
        )


class RateLimitExceededError(BaseAPIException):
    """Exception for 429 Rate Limit Exceeded errors."""

    def __init__(
        self,
        detail: str = "Rate limit exceeded. Please try again later",
        code: str = "RATE_LIMIT_EXCEEDED",
        details: dict[str, Any] | list[str] | str | None = None,
        retry_after: int | None = None,
    ) -> None:
        """Initialize RateLimitExceededError."""
        if details is None:
            details = {}
        if isinstance(details, dict) and retry_after is not None:
            details["retry_after"] = retry_after
        super().__init__(
            detail=detail,
            code=code,
            status_code=429,
            details=details,
        )
