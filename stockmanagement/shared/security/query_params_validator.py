"""Query parameters validation and sanitization utilities."""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from shared.exceptions.specific import BadRequestError


class QueryParamsValidator:
    """Validator for query parameters with security checks."""

    # Security limits
    MAX_PAGE_SIZE = 1000
    MAX_LIMIT = 1000
    MAX_PAGE_NUMBER = 10000
    DEFAULT_PAGE_SIZE = 20
    DEFAULT_LIMIT = 100
    MIN_PAGE_SIZE = 1
    MIN_LIMIT = 1

    @staticmethod
    def validate_page_size(page_size: str | int | None, default: int = 20) -> int:
        """
        Validate and sanitize page_size parameter.

        Args:
            page_size: Page size from query params
            default: Default value if not provided

        Returns:
            Validated page size (between MIN_PAGE_SIZE and MAX_PAGE_SIZE)

        Raises:
            BadRequestError: If page_size is invalid
        """
        if page_size is None:
            return default

        try:
            page_size_int = int(page_size)
        except (ValueError, TypeError) as err:
            raise BadRequestError(
                detail=f"Invalid page_size: must be an integer between "
                f"{QueryParamsValidator.MIN_PAGE_SIZE} and {QueryParamsValidator.MAX_PAGE_SIZE}",
                code="INVALID_PAGE_SIZE",
            ) from err

        if page_size_int < QueryParamsValidator.MIN_PAGE_SIZE:
            raise BadRequestError(
                detail=f"page_size must be at least {QueryParamsValidator.MIN_PAGE_SIZE}",
                code="INVALID_PAGE_SIZE",
            )

        if page_size_int > QueryParamsValidator.MAX_PAGE_SIZE:
            raise BadRequestError(
                detail=f"page_size cannot exceed {QueryParamsValidator.MAX_PAGE_SIZE}",
                code="INVALID_PAGE_SIZE",
            )

        return page_size_int

    @staticmethod
    def validate_page(page: str | int | None, default: int = 1) -> int:
        """
        Validate and sanitize page parameter.

        Args:
            page: Page number from query params
            default: Default value if not provided

        Returns:
            Validated page number (between 1 and MAX_PAGE_NUMBER)

        Raises:
            BadRequestError: If page is invalid
        """
        if page is None:
            return default

        try:
            page_int = int(page)
        except (ValueError, TypeError) as err:
            raise BadRequestError(
                detail="Invalid page: must be a positive integer",
                code="INVALID_PAGE",
            ) from err

        if page_int < 1:
            raise BadRequestError(
                detail="page must be at least 1",
                code="INVALID_PAGE",
            )

        if page_int > QueryParamsValidator.MAX_PAGE_NUMBER:
            raise BadRequestError(
                detail=f"page cannot exceed {QueryParamsValidator.MAX_PAGE_NUMBER}",
                code="INVALID_PAGE",
            )

        return page_int

    @staticmethod
    def validate_limit(
        limit: str | int | None, default: int = 100, max_limit: int | None = None
    ) -> int:
        """
        Validate and sanitize limit parameter.

        Args:
            limit: Limit from query params
            default: Default value if not provided
            max_limit: Maximum allowed limit (defaults to MAX_LIMIT)

        Returns:
            Validated limit (between MIN_LIMIT and max_limit)

        Raises:
            BadRequestError: If limit is invalid
        """
        if limit is None:
            return default

        max_allowed = max_limit or QueryParamsValidator.MAX_LIMIT

        try:
            limit_int = int(limit)
        except (ValueError, TypeError) as err:
            raise BadRequestError(
                detail=f"Invalid limit: must be an integer between "
                f"{QueryParamsValidator.MIN_LIMIT} and {max_allowed}",
                code="INVALID_LIMIT",
            ) from err

        if limit_int < QueryParamsValidator.MIN_LIMIT:
            raise BadRequestError(
                detail=f"limit must be at least {QueryParamsValidator.MIN_LIMIT}",
                code="INVALID_LIMIT",
            )

        if limit_int > max_allowed:
            raise BadRequestError(
                detail=f"limit cannot exceed {max_allowed}",
                code="INVALID_LIMIT",
            )

        return limit_int

    @staticmethod
    def validate_date(date_str: str | None, param_name: str = "date") -> datetime | None:
        """
        Validate and parse ISO date string.

        Args:
            date_str: Date string from query params
            param_name: Name of the parameter for error messages

        Returns:
            Parsed datetime or None

        Raises:
            BadRequestError: If date format is invalid
        """
        if not date_str:
            return None

        # Remove any whitespace
        date_str = date_str.strip()

        # Basic sanitization - only allow ISO format characters
        if not re.match(r"^[\d\-\+T:\.Z]+$", date_str):
            raise BadRequestError(
                detail=f"Invalid {param_name} format: only ISO 8601 format is allowed",
                code="INVALID_DATE_FORMAT",
            )

        try:
            # Try parsing ISO format
            if date_str.endswith("Z"):
                date_str = date_str.replace("Z", "+00:00")
            return datetime.fromisoformat(date_str)
        except (ValueError, TypeError) as err:
            raise BadRequestError(
                detail=f"Invalid {param_name} format: {str(err)}. Use ISO 8601 format (e.g., 2024-01-01T00:00:00Z)",
                code="INVALID_DATE_FORMAT",
            ) from err

    @staticmethod
    def validate_enum(
        value: str | None,
        allowed_values: list[str],
        param_name: str = "parameter",
        case_sensitive: bool = False,
    ) -> str | None:
        """
        Validate enum-like parameter against whitelist.

        Args:
            value: Value from query params
            allowed_values: List of allowed values
            param_name: Name of the parameter for error messages
            case_sensitive: Whether comparison should be case-sensitive

        Returns:
            Validated value or None

        Raises:
            BadRequestError: If value is not in allowed list
        """
        if not value:
            return None

        # Sanitize - remove any whitespace
        value = value.strip()

        # Check against whitelist
        if case_sensitive:
            if value not in allowed_values:
                raise BadRequestError(
                    detail=f"Invalid {param_name}: must be one of {', '.join(allowed_values)}",
                    code="INVALID_ENUM_VALUE",
                    details={"allowed_values": allowed_values, "provided": value},
                )
        else:
            value_lower = value.lower()
            allowed_lower = [v.lower() for v in allowed_values]
            if value_lower not in allowed_lower:
                raise BadRequestError(
                    detail=f"Invalid {param_name}: must be one of {', '.join(allowed_values)}",
                    code="INVALID_ENUM_VALUE",
                    details={"allowed_values": allowed_values, "provided": value},
                )
            # Return the original case from allowed_values
            for allowed in allowed_values:
                if allowed.lower() == value_lower:
                    return allowed

        return value

    @staticmethod
    def validate_uuid(uuid_str: str | None, param_name: str = "id") -> UUID | None:
        """
        Validate UUID string.

        Args:
            uuid_str: UUID string from query params
            param_name: Name of the parameter for error messages

        Returns:
            Parsed UUID or None

        Raises:
            BadRequestError: If UUID format is invalid
        """
        if not uuid_str:
            return None

        # Sanitize - remove whitespace
        uuid_str = uuid_str.strip()

        # Basic format check
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
        )
        if not uuid_pattern.match(uuid_str):
            raise BadRequestError(
                detail=f"Invalid {param_name} format: must be a valid UUID",
                code="INVALID_UUID_FORMAT",
            )

        try:
            return UUID(uuid_str)
        except (ValueError, TypeError) as err:
            raise BadRequestError(
                detail=f"Invalid {param_name} format: {str(err)}",
                code="INVALID_UUID_FORMAT",
            ) from err

    @staticmethod
    def validate_boolean(value: str | None, param_name: str = "parameter") -> bool:
        """
        Validate boolean parameter.

        Args:
            value: Boolean string from query params
            param_name: Name of the parameter for error messages

        Returns:
            Parsed boolean value

        Raises:
            BadRequestError: If value is not a valid boolean
        """
        if not value:
            return False

        value_lower = value.strip().lower()
        if value_lower in ("true", "1", "yes", "on"):
            return True
        elif value_lower in ("false", "0", "no", "off", ""):
            return False
        else:
            raise BadRequestError(
                detail=f"Invalid {param_name}: must be 'true' or 'false'",
                code="INVALID_BOOLEAN_VALUE",
            )

    @staticmethod
    def sanitize_string(
        value: str | None, max_length: int = 1000, allow_empty: bool = True
    ) -> str | None:
        """
        Sanitize string parameter to prevent injection attacks.

        Args:
            value: String from query params
            max_length: Maximum allowed length
            allow_empty: Whether empty strings are allowed

        Returns:
            Sanitized string or None

        Raises:
            BadRequestError: If string is invalid
        """
        if not value:
            return None if not allow_empty else ""

        # Remove leading/trailing whitespace
        value = value.strip()

        # Check length
        if len(value) > max_length:
            raise BadRequestError(
                detail=f"String parameter exceeds maximum length of {max_length} characters",
                code="STRING_TOO_LONG",
            )

        # Remove any null bytes and control characters (except newlines and tabs)
        value = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F]", "", value)

        return value if value or allow_empty else None
