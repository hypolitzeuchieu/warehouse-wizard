"""Customer DTOs."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass
class CustomerCreateDTO:
    """DTO for creating a customer."""

    name: str
    email: str | None = None
    phone_number: str | None = None
    address: str | None = None
    customer_type: str = "REGULAR"  # REGULAR, WHOLESALER


@dataclass
class CustomerUpdateDTO:
    """DTO for updating a customer."""

    name: str | None = None
    email: str | None = None
    phone_number: str | None = None
    address: str | None = None
    customer_type: str | None = None


@dataclass
class CustomerResponseDTO:
    """DTO for customer response."""

    id: UUID
    business_id: UUID | None
    name: str
    email: str | None
    phone_number: str | None
    address: str | None
    customer_type: str
    loyalty_points: Decimal
    total_purchases: Decimal
    created_at: datetime
    updated_at: datetime


@dataclass
class CustomerPurchaseHistoryResponseDTO:
    """DTO for customer purchase history response."""

    id: UUID
    customer_id: UUID
    business_id: UUID
    invoice_id: UUID
    total_amount: Decimal
    purchase_date: datetime
    created_at: datetime
