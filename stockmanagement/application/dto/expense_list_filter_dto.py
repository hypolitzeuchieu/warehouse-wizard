"""Expense list filter DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from application.dto.base_list_filter_dto import BaseListFilterDTO


@dataclass
class ExpenseListFilterDTO(BaseListFilterDTO):
    """DTO for filtering expenses."""

    business_id: UUID | None = None
    expense_type: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    payment_method: str | None = None
    payee_type: str | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    is_approved: bool | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ExpenseListFilterDTO:
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
            expense_type=filters.get("expense_type"),
            start_date=filters.get("start_date"),
            end_date=filters.get("end_date"),
            payment_method=filters.get("payment_method"),
            payee_type=filters.get("payee_type"),
            min_amount=filters.get("min_amount"),
            max_amount=filters.get("max_amount"),
            is_approved=filters.get("is_approved"),
        )
