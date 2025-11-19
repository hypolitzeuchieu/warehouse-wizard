"""Product list filter DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from application.dto.base_list_filter_dto import BaseListFilterDTO


@dataclass
class ProductListFilterDTO(BaseListFilterDTO):
    """DTO for filtering products."""

    business_id: UUID | None = None
    category_id: UUID | None = None
    subcategory_id: UUID | None = None
    low_stock_only: bool = False
    expired_only: bool = False
    name: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ProductListFilterDTO:
        base = super().from_payload(payload)
        filters = base.filters
        base_kwargs = {
            "page": base.page,
            "page_size": base.page_size,
            "search": base.search,
            "search_fields": base.search_fields,
            "order_by": base.order_by,
            "filters": filters,
        }
        return cls(
            **base_kwargs,
            business_id=filters.get("business_id"),
            category_id=filters.get("category_id"),
            subcategory_id=filters.get("subcategory_id"),
            low_stock_only=bool(filters.get("low_stock_only", False)),
            expired_only=bool(filters.get("expired_only", False)),
            name=filters.get("name"),
        )
