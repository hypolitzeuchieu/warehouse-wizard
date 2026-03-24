"""Credit DTOs."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass
class CreditCreateDTO:
    """DTO for creating a credit."""

    customer_id: UUID
    amount: Decimal
    due_date: datetime
    invoice_id: UUID | None = None
    notes: str | None = None


@dataclass
class CreditUpdateDTO:
    """DTO for updating a credit."""

    amount: Decimal | None = None
    due_date: datetime | None = None
    notes: str | None = None
    status: str | None = None


@dataclass
class CreditResponseDTO:
    """DTO for credit response."""

    id: UUID
    business_id: UUID
    customer_id: UUID
    invoice_id: UUID | None
    amount: Decimal
    paid_amount: Decimal
    remaining_amount: Decimal
    due_date: datetime
    status: str
    notes: str | None
    is_overdue: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class CreditPaymentCreateDTO:
    """DTO for creating a credit payment."""

    amount: Decimal
    payment_method: str = "cash"
    notes: str | None = None
    payment_date: datetime | None = None


@dataclass
class CreditPaymentResponseDTO:
    """DTO for credit payment response."""

    id: UUID
    credit_id: UUID
    amount: Decimal
    payment_date: datetime
    payment_method: str
    notes: str | None
    created_at: datetime
