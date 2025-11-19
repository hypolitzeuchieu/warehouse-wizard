"""Notification list filter DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from application.dto.base_list_filter_dto import BaseListFilterDTO


@dataclass
class NotificationListFilterDTO(BaseListFilterDTO):
    """DTO for filtering notifications."""

    status: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> NotificationListFilterDTO:
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
            status=filters.get("status"),
        )
