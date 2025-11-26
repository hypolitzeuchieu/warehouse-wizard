"""Sales domain entities."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID


class InvoiceStatus(str, Enum):
    """Invoice status enumeration."""

    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    CREDIT = "CREDIT"


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
    customer_name: str | None
    customer_id: UUID | None
    cashier_id: UUID
    status: InvoiceStatus
    total: Decimal
    tax: Decimal
    total_discount: Decimal
    advance_paid: Decimal
    remaining_amount: Decimal
    payment_method: PaymentMethod
    due_date: datetime | date | None
    is_credit_settled: bool
    created_at: datetime
    updated_at: datetime
    reason: str | None = None
    is_archived: bool = False

    def calculate_total(self) -> Decimal:
        """Calculate total amount."""
        return self.total + self.tax - self.total_discount

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
    status: str
    total: Decimal
    payment_method: PaymentMethod | None
    shipping_address: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    delivered_at: datetime | None = None


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


class InvoiceLogAction(str, Enum):
    """Invoice log action enumeration."""

    CREATED = "CREATED"
    UPDATED = "UPDATED"
    PAYMENT_RECEIVED = "PAYMENT_RECEIVED"
    REFUNDED = "REFUNDED"
    CANCELLED = "CANCELLED"
    LINE_ADDED = "LINE_ADDED"
    LINE_REMOVED = "LINE_REMOVED"
    LINE_UPDATED = "LINE_UPDATED"
    CREDIT_APPLIED = "CREDIT_APPLIED"
    STATUS_CHANGED = "STATUS_CHANGED"
    ARCHIVED = "ARCHIVED"


@dataclass
class InvoicePayment:
    """Invoice payment entity."""

    id: UUID
    invoice_id: UUID
    amount: Decimal
    payment_method: PaymentMethod
    change_amount: Decimal
    refund_amount: Decimal
    payment_date: datetime
    notes: str | None
    created_at: datetime
    updated_at: datetime
    created_by: UUID
    idempotency_key: UUID | None = None

    def __post_init__(self) -> None:
        """Validate payment data."""
        if self.amount <= 0:
            raise ValueError("Payment amount must be greater than zero")
        if self.change_amount < 0:
            raise ValueError("Change amount cannot be negative")
        if self.refund_amount < 0:
            raise ValueError("Refund amount cannot be negative")


@dataclass
class InvoiceLog:
    """Invoice log entity."""

    id: UUID
    invoice_id: UUID
    action: InvoiceLogAction
    old_value: str | None
    new_value: str | None
    description: str | None
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None
