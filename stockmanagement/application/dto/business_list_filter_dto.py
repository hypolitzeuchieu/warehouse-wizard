"""Business list filter DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from application.dto.base_list_filter_dto import BaseListFilterDTO


@dataclass
class BusinessListFilterDTO(BaseListFilterDTO):
    """DTO for filtering businesses."""

    owner_id: UUID | None = None
    is_active: bool | None = None
    name: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> BusinessListFilterDTO:
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
            owner_id=filters.get("owner_id"),
            is_active=filters.get("is_active"),
            name=filters.get("name"),
        )
