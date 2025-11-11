"""Customer domain entities."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID


@dataclass
class Customer:
    """Customer entity."""

    id: UUID
    business_id: Optional[UUID]  # None for platform-wide customers
    name: str
    email: Optional[str]
    phone_number: Optional[str]
    address: Optional[str]
    loyalty_points: Decimal
    total_purchases: Decimal
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        """Validate customer data."""
        if not self.name:
            raise ValueError("Customer name is required")


@dataclass
class CustomerPurchaseHistory:
    """Customer purchase history entity."""

    id: UUID
    customer_id: UUID
    business_id: UUID
    invoice_id: UUID
    total_amount: Decimal
    purchase_date: datetime
    created_at: datetime

