"""Credit domain entities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from django.utils import timezone


class CreditStatus(str, Enum):
    """Credit status enumeration."""

    PENDING = "PENDING"  # Credit created, not yet due
    OVERDUE = "OVERDUE"  # Payment is overdue
    PARTIALLY_PAID = "PARTIALLY_PAID"  # Some payment made
    SETTLED = "SETTLED"  # Fully paid
    CANCELLED = "CANCELLED"  # Credit cancelled


@dataclass
class Credit:
    """Credit entity for customer debts."""

    id: UUID
    business_id: UUID
    customer_id: UUID
    invoice_id: UUID | None  # Related invoice if created from invoice
    amount: Decimal  # Total credit amount
    paid_amount: Decimal  # Amount already paid
    remaining_amount: Decimal  # Amount still owed
    due_date: datetime  # Payment due date
    status: CreditStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime
    created_by: UUID  # User who created the credit

    def __post_init__(self) -> None:
        """Validate credit data."""
        if self.amount <= 0:
            raise ValueError("Credit amount must be greater than zero")
        if self.paid_amount < 0:
            raise ValueError("Paid amount cannot be negative")
        if self.remaining_amount < 0:
            raise ValueError("Remaining amount cannot be negative")

    def is_overdue(self) -> bool:
        """Check if credit is overdue."""
        return (
            self.status != CreditStatus.SETTLED
            and self.status != CreditStatus.CANCELLED
            and timezone.now() > self.due_date
        )

    def update_status(self) -> None:
        """Update credit status based on payment and due date."""

        if self.remaining_amount <= 0:
            self.status = CreditStatus.SETTLED
        elif self.paid_amount > 0:
            self.status = CreditStatus.PARTIALLY_PAID
        elif self.is_overdue():
            self.status = CreditStatus.OVERDUE
        else:
            self.status = CreditStatus.PENDING


@dataclass
class CreditPayment:
    """Credit payment entity."""

    id: UUID
    credit_id: UUID
    amount: Decimal
    payment_date: datetime
    payment_method: str  # cash, card, mobile_money, etc.
    notes: str | None
    created_at: datetime
    created_by: UUID  # User who recorded the payment

    def __post_init__(self) -> None:
        """Validate payment data."""
        if self.amount <= 0:
            raise ValueError("Payment amount must be greater than zero")
