"""Base filtering utilities for list endpoints."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from shared.exceptions.specific import BadRequestError
from shared.filters.security_validators import (
    ensure_allowed_query_params,
    sanitize_search_query,
    validate_field_whitelist,
    validate_ordering_field,
)
from shared.security.query_params_validator import QueryParamsValidator


def _normalize_params(params: Mapping[str, Any] | None) -> dict[str, Any]:
    """Normalize QueryDict-like objects to a standard dict."""
    if params is None:
        return {}

    if hasattr(params, "lists"):
        normalized: dict[str, Any] = {}
        for key, values in params.lists():
            if not values:
                normalized[key] = None
            else:
                normalized[key] = values[-1]
        return normalized

    if hasattr(params, "items"):
        return dict(params.items())

    return dict(params)


@dataclass
class BaseListFilter:
    """Base filtering helper that enforces security and consistency."""

    params: Mapping[str, Any] | None = None
    search_fields: Iterable[str] | None = None
    order_fields: Iterable[str] | None = None
    filter_definitions: dict[str, dict[str, Any]] | None = None
    additional_allowed_params: Iterable[str] | None = None
    default_order_field: str = "updated_at"

    STANDARD_PARAMS: set[str] = field(
        init=False,
        default_factory=lambda: {
            "page",
            "page_size",
            "search",
            "order_by",
            "name",
        },
    )

    def __post_init__(self) -> None:
        self._raw_params = _normalize_params(self.params)
        self.search_fields = validate_field_whitelist(
            self.search_fields,
            param_name="search_fields",
        )
        self.order_fields = validate_field_whitelist(
            self.order_fields or [self.default_order_field],
            param_name="order_fields",
        ) or [self.default_order_field]
        self.filter_definitions = self.filter_definitions or {}
        self.additional_allowed_params = list(self.additional_allowed_params or [])

        self.page: int = 1
        self.page_size: int = QueryParamsValidator.DEFAULT_PAGE_SIZE
        self.order_by: str = self.default_order_field
        self.search: str | None = None
        self.filters: dict[str, Any] = {}
        self._validated: bool = False

    # ----- Public API -------------------------------------------------
    def validate(self) -> BaseListFilter:
        """Validate and sanitize all parameters."""
        self.page = QueryParamsValidator.validate_page(
            self._raw_params.get("page"),
            default=1,
        )
        self.page_size = QueryParamsValidator.validate_page_size(
            self._raw_params.get("page_size"),
            default=QueryParamsValidator.DEFAULT_PAGE_SIZE,
        )
        self.order_by = validate_ordering_field(
            self._raw_params.get("order_by"),
            allowed_fields=self.order_fields,
            default_field=self.default_order_field,
        )
        self.search = sanitize_search_query(self._raw_params.get("search"))

        name_filter = QueryParamsValidator.sanitize_string(
            self._raw_params.get("name"),
            max_length=255,
            allow_empty=False,
        )
        if name_filter:
            self.filters["name"] = name_filter

        # Validate custom filters
        for key, definition in self.filter_definitions.items():
            value = self._raw_params.get(key)
            if value in (None, ""):
                continue
            validated_value = self._apply_filter_definition(
                key,
                value,
                definition,
            )
            self.filters[key] = validated_value

        allowed_keys = self.STANDARD_PARAMS | set(self.filter_definitions.keys())
        allowed_keys |= set(self.additional_allowed_params)
        ensure_allowed_query_params(self._raw_params.keys(), allowed_keys)

        self._validated = True
        return self

    def to_payload(self) -> dict[str, Any]:
        """Return validated payload ready for DTO construction."""
        if not self._validated:
            self.validate()

        return {
            "page": self.page,
            "page_size": self.page_size,
            "order_by": self.order_by,
            "search": self.search,
            "search_fields": list(self.search_fields or []),
            "filters": self.filters.copy(),
        }

    # ----- Internal helpers ------------------------------------------
    def _apply_filter_definition(
        self,
        key: str,
        raw_value: Any,
        definition: dict[str, Any],
    ) -> Any:
        filter_type = (definition.get("type") or "string").lower()

        if validator := definition.get("validator"):
            return validator(raw_value)

        if filter_type == "uuid":
            return QueryParamsValidator.validate_uuid(raw_value, param_name=key)
        if filter_type == "boolean":
            return QueryParamsValidator.validate_boolean(raw_value, param_name=key)
        if filter_type == "enum":
            allowed_values = definition.get("choices") or definition.get("allowed_values")
            if not allowed_values:
                raise BadRequestError(
                    detail=f"Filter '{key}' must define 'choices' for enum validation.",
                    code="INVALID_FILTER_CONFIGURATION",
                )
            return QueryParamsValidator.validate_enum(
                raw_value,
                allowed_values=list(allowed_values),
                param_name=key,
                case_sensitive=definition.get("case_sensitive", False),
            )
        if filter_type == "date":
            return QueryParamsValidator.validate_date(raw_value, param_name=key)
        if filter_type == "int":
            try:
                value = int(raw_value)
            except (TypeError, ValueError) as err:
                raise BadRequestError(
                    detail=f"{key} must be an integer",
                    code="INVALID_INTEGER",
                ) from err
            min_value = definition.get("min")
            max_value = definition.get("max")
            if min_value is not None and value < min_value:
                raise BadRequestError(
                    detail=f"{key} must be greater than or equal to {min_value}",
                    code="INVALID_INTEGER",
                )
            if max_value is not None and value > max_value:
                raise BadRequestError(
                    detail=f"{key} must be less than or equal to {max_value}",
                    code="INVALID_INTEGER",
                )
            return value
        if filter_type == "decimal":
            try:
                return Decimal(str(raw_value))
            except (ValueError, TypeError, ArithmeticError) as err:
                raise BadRequestError(
                    detail=f"{key} must be a valid decimal number",
                    code="INVALID_DECIMAL",
                ) from err
        if filter_type == "datetime":
            parsed = QueryParamsValidator.validate_date(raw_value, param_name=key)
            if parsed is None:
                return None
            return parsed
        if filter_type == "string":
            return QueryParamsValidator.sanitize_string(
                raw_value,
                max_length=definition.get("max_length", 255),
                allow_empty=definition.get("allow_empty", False),
            )

        raise BadRequestError(
            detail=f"Unsupported filter type '{filter_type}' for '{key}'",
            code="UNSUPPORTED_FILTER_TYPE",
        )
