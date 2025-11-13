"""Base API exception class."""

from typing import Any


class BaseAPIException(Exception):
    """Base exception class for API errors."""

    def __init__(
        self,
        detail: str | None = None,
        message: str | None = None,
        status_code: int = 400,
        code: str | None = None,
        error_code: str | None = None,
        details: dict[str, Any] | list[str] | str | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            detail: Error message (alias for message, preferred)
            message: Error message (legacy, use detail instead)
            status_code: HTTP status code
            code: Error code (alias for error_code, preferred)
            error_code: Error code for client handling (legacy, use code instead)
            details: Additional error details
        """
        # Support both 'detail' and 'message' for backward compatibility
        self.detail = detail or message or "An error occurred"
        self.message = self.detail  # Keep for backward compatibility

        # Support both 'code' and 'error_code' for backward compatibility
        self.code = code or error_code or "BAD_REQUEST"
        self.error_code = self.code  # Keep for backward compatibility

        self.status_code = status_code
        self.details = details
        super().__init__(self.detail)
