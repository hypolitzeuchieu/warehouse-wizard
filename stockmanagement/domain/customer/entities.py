"""Customer domain entities."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID


class CustomerType(str, Enum):
    """Customer type enumeration."""

    REGULAR = "REGULAR"
    WHOLESALER = "WHOLESALER"


@dataclass
class Customer:
    """Customer entity."""

    id: UUID
    business_id: UUID | None  # None for platform-wide customers
    name: str
    email: str | None
    phone_number: str | None
    address: str | None
    customer_type: CustomerType
    loyalty_points: Decimal
    total_purchases: Decimal
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        """Validate customer data."""
        if not self.name:
            raise ValueError("Customer name is required")

    def is_wholesaler(self) -> bool:
        """Check if customer is a wholesaler."""
        return self.customer_type == CustomerType.WHOLESALER


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
