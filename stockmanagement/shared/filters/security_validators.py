"""Security helpers for filtering utilities."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from shared.exceptions.specific import BadRequestError
from shared.security.query_params_validator import QueryParamsValidator

FIELD_PATTERN = re.compile(r"^[a-zA-Z_][\w\.]*$")


def sanitize_search_query(value: str | None, max_length: int = 255) -> str | None:
    """
    Sanitize search query strings to prevent injection attempts.

    Removes dangerous characters and enforces a maximum length.
    """
    if value is None:
        return None

    sanitized = QueryParamsValidator.sanitize_string(
        value,
        max_length=max_length,
        allow_empty=False,
    )
    if sanitized is None:
        return None

    sanitized = re.sub(r'[;"`]+', "", sanitized)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()

    return sanitized or None


def validate_ordering_field(
    field: str | None,
    allowed_fields: Sequence[str] | None,
    default_field: str,
) -> str:
    """Validate order_by parameter against a whitelist."""
    allowed = list(allowed_fields or []) or [default_field]
    normalized_allowed = _validate_field_names(allowed, param_name="orderable fields")

    raw_value = (field or default_field).strip()
    direction = ""
    if raw_value.startswith("-"):
        direction = "-"
        raw_value = raw_value[1:]
    elif raw_value.startswith("+"):
        raw_value = raw_value[1:]

    if raw_value not in normalized_allowed:
        raise BadRequestError(
            detail=f"Invalid order_by field '{raw_value}'. Allowed fields: {', '.join(normalized_allowed)}",
            code="INVALID_ORDER_FIELD",
            details={"allowed_fields": normalized_allowed, "provided": raw_value},
        )

    return f"{direction}{raw_value}"


def ensure_allowed_query_params(
    provided_keys: Iterable[str],
    allowed_keys: Iterable[str],
) -> None:
    """Ensure no unexpected query parameters are provided."""
    provided_set = {key for key in provided_keys if key}
    allowed_set = {key for key in allowed_keys if key}

    unexpected = sorted(provided_set - allowed_set)
    if unexpected:
        raise BadRequestError(
            detail=f"Unexpected query parameters: {', '.join(unexpected)}",
            code="INVALID_QUERY_PARAMETER",
            details={"invalid_params": unexpected},
        )


def _validate_field_names(fields: Iterable[str], param_name: str) -> list[str]:
    """Validate that field names only contain safe characters."""
    valid_fields: list[str] = []
    for field in fields:
        if not field:
            continue
        if not FIELD_PATTERN.match(field):
            raise BadRequestError(
                detail=f"Invalid field '{field}' for {param_name}.",
                code="INVALID_FIELD_NAME",
                details={"field": field, "param_name": param_name},
            )
        valid_fields.append(field)
    return valid_fields


def validate_field_whitelist(
    fields: Iterable[str] | None,
    param_name: str,
) -> list[str]:
    """Public helper to validate field whitelists (search/order/etc.)."""
    if not fields:
        return []
    return _validate_field_names(fields, param_name=param_name)
