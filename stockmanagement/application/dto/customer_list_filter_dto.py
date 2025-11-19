"""Customer list filter DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from application.dto.base_list_filter_dto import BaseListFilterDTO


@dataclass
class CustomerListFilterDTO(BaseListFilterDTO):
    """DTO for filtering customers."""

    business_id: UUID | None = None
    customer_type: str | None = None
    name: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> CustomerListFilterDTO:
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
            customer_type=filters.get("customer_type"),
            name=filters.get("name"),
        )
