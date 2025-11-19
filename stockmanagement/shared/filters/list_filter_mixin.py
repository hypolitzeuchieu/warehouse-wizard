"""Mixin to simplify parsing of list filters in ViewSets."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from shared.filters import result_filters
from shared.filters.base_list_filter import BaseListFilter


class ListFilterMixin:
    """Mixin providing a consistent way to parse and validate query filters."""

    default_order_field: str = "updated_at"

    def get_default_order_field(self) -> str:
        """Return the default order_by field for the ViewSet."""
        return getattr(self, "default_order_field", "updated_at")

    def build_list_filter(
        self,
        request: Any,
        *,
        search_fields: Iterable[str] | None = None,
        order_fields: Iterable[str] | None = None,
        filter_definitions: dict[str, dict[str, Any]] | None = None,
        additional_allowed_params: Iterable[str] | None = None,
        default_order_field: str | None = None,
    ) -> BaseListFilter:
        """Create and validate a BaseListFilter instance."""
        query_params = getattr(request, "query_params", None)
        effective_default = default_order_field or self.get_default_order_field()
        base_filter = BaseListFilter(
            params=query_params,
            search_fields=search_fields,
            order_fields=order_fields or [effective_default],
            filter_definitions=filter_definitions,
            additional_allowed_params=additional_allowed_params,
            default_order_field=effective_default,
        )
        return base_filter.validate()

    def parse_list_filters(
        self,
        request: Any,
        *,
        search_fields: Iterable[str] | None = None,
        order_fields: Iterable[str] | None = None,
        filter_definitions: dict[str, dict[str, Any]] | None = None,
        additional_allowed_params: Iterable[str] | None = None,
        default_order_field: str | None = None,
    ) -> dict[str, Any]:
        """
        Parse and return validated filters ready to construct DTOs.

        Returns:
            Dict with keys: page, page_size, search, search_fields, order_by, filters
        """
        effective_default = default_order_field or self.get_default_order_field()

        if order_fields and effective_default not in order_fields:
            order_fields_list = list(order_fields)
            if order_fields_list:
                effective_default = order_fields_list[0]

        base_filter = self.build_list_filter(
            request,
            search_fields=search_fields,
            order_fields=order_fields,
            filter_definitions=filter_definitions,
            additional_allowed_params=additional_allowed_params,
            default_order_field=effective_default,
        )
        return base_filter.to_payload()

    def apply_filtering_to_items(
        self,
        items: Iterable[Any],
        filter_payload: dict[str, Any],
        *,
        name_fields: list[str] | None = None,
    ) -> list[Any]:
        """Apply name/search/order filtering to an iterable of DTOs."""
        filters = filter_payload.get("filters", {})
        filtered = result_filters.filter_by_name(
            items,
            filters.get("name"),
            name_fields or ["name"],
        )
        filtered = result_filters.filter_by_search(
            filtered,
            filter_payload.get("search"),
            filter_payload.get("search_fields"),
        )
        return result_filters.sort_items(filtered, filter_payload.get("order_by"))
