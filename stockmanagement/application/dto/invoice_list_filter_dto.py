"""Invoice list filter DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from application.dto.base_list_filter_dto import BaseListFilterDTO


@dataclass
class InvoiceListFilterDTO(BaseListFilterDTO):
    """DTO for filtering invoices."""

    business_id: UUID | None = None
    status: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> InvoiceListFilterDTO:
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
            status=filters.get("status"),
            start_date=filters.get("start_date"),
            end_date=filters.get("end_date"),
        )
