"""Sales domain entities."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID


class InvoiceStatus(str, Enum):
    """Invoice status enumeration."""

    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    CREDIT = "CREDIT"
    PENDING = "PENDING"


class PaymentMethod(str, Enum):
    """Payment method enumeration."""

    CASH = "cash"
    CARD = "card"
    MOBILE_MONEY = "mobile_money"
    STRIPE = "stripe"
    PAYPAL = "paypal"
    CREDIT = "credit"


@dataclass
class Invoice:
    """Invoice entity."""

    id: UUID
    business_id: UUID
    number: int
    customer_name: Optional[str]
    customer_id: Optional[UUID]
    cashier_id: UUID
    status: InvoiceStatus
    total: Decimal
    tax: Decimal
    discount: Decimal
    advance_paid: Decimal
    remaining_amount: Decimal
    payment_method: PaymentMethod
    due_date: Optional[datetime]
    is_credit_settled: bool
    created_at: datetime
    updated_at: datetime
    reason: Optional[str] = None

    def calculate_total(self) -> Decimal:
        """Calculate total amount."""
        return self.total + self.tax - self.discount

    def get_remaining_amount(self) -> Decimal:
        """Get remaining amount to be paid."""
        if self.status == InvoiceStatus.CREDIT:
            return max(self.total - self.advance_paid, Decimal("0.00"))
        return Decimal("0.00")


@dataclass
class InvoiceLine:
    """Invoice line item entity."""

    id: UUID
    invoice_id: UUID
    product_id: UUID
    quantity: int
    unit_price: Decimal
    discount: Decimal
    line_total: Decimal
    created_at: datetime

    def calculate_line_total(self) -> Decimal:
        """Calculate line total."""
        return (self.unit_price * self.quantity) - self.discount


@dataclass
class Order:
    """Order entity for customer orders."""

    id: UUID
    business_id: UUID
    customer_id: UUID
    order_number: str
    status: str  # pending, confirmed, processing, shipped, delivered, cancelled
    total: Decimal
    payment_method: Optional[PaymentMethod]
    shipping_address: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    delivered_at: Optional[datetime] = None


@dataclass
class OrderItem:
    """Order item entity."""

    id: UUID
    order_id: UUID
    product_id: UUID
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    created_at: datetime

