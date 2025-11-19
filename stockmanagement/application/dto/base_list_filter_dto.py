"""Shared DTO definitions for list filters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BaseListFilterDTO:
    """Base DTO capturing normalized list filters."""

    page: int = 1
    page_size: int = 20
    search: str | None = None
    search_fields: list[str] = field(default_factory=list)
    order_by: str = "updated_at"
    filters: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> BaseListFilterDTO:
        """Instantiate DTO from BaseListFilter payload."""
        return cls(
            page=payload.get("page", 1),
            page_size=payload.get("page_size", 20),
            search=payload.get("search"),
            search_fields=list(payload.get("search_fields", []) or []),
            order_by=payload.get("order_by", "updated_at"),
            filters=dict(payload.get("filters", {}) or {}),
        )

    def get_filter(self, key: str, default: Any = None) -> Any:
        """Convenience accessor for custom filters."""
        return self.filters.get(key, default)
