"""Sales DTOs."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID


@dataclass
class InvoiceLineCreateDTO:
    """DTO for creating an invoice line."""

    product_id: UUID
    quantity: int
    unit_price: Decimal
    discount: Decimal = Decimal("0.00")


@dataclass
class InvoiceCreateDTO:
    """DTO for creating an invoice."""

    customer_name: Optional[str] = None
    customer_id: Optional[UUID] = None
    lines: list[InvoiceLineCreateDTO] = None
    tax: Decimal = Decimal("0.00")
    discount: Decimal = Decimal("0.00")
    payment_method: str = "cash"
    due_date: Optional[datetime] = None
    reason: Optional[str] = None


@dataclass
class InvoiceUpdateDTO:
    """DTO for updating an invoice."""

    status: Optional[str] = None
    tax: Optional[Decimal] = None
    discount: Optional[Decimal] = None
    advance_paid: Optional[Decimal] = None
    payment_method: Optional[str] = None
    due_date: Optional[datetime] = None
    is_credit_settled: Optional[bool] = None
    reason: Optional[str] = None


@dataclass
class InvoiceLineResponseDTO:
    """DTO for invoice line response."""

    id: UUID
    invoice_id: UUID
    product_id: UUID
    quantity: int
    unit_price: Decimal
    discount: Decimal
    line_total: Decimal
    created_at: datetime
    product_name: Optional[str] = None


@dataclass
class InvoiceResponseDTO:
    """DTO for invoice response."""

    id: UUID
    business_id: UUID
    number: int
    cashier_id: UUID
    status: str
    total: Decimal
    tax: Decimal
    discount: Decimal
    advance_paid: Decimal
    remaining_amount: Decimal
    payment_method: str
    is_credit_settled: bool
    created_at: datetime
    updated_at: datetime
    customer_name: Optional[str] = None
    customer_id: Optional[UUID] = None
    cashier_name: Optional[str] = None
    due_date: Optional[datetime] = None
    reason: Optional[str] = None
    lines: Optional[list[InvoiceLineResponseDTO]] = None


@dataclass
class OrderItemCreateDTO:
    """DTO for creating an order item."""

    product_id: UUID
    quantity: int
    unit_price: Decimal


@dataclass
class OrderCreateDTO:
    """DTO for creating an order."""

    customer_id: UUID
    items: list[OrderItemCreateDTO]
    payment_method: Optional[str] = None
    shipping_address: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class OrderUpdateDTO:
    """DTO for updating an order."""

    status: Optional[str] = None
    payment_method: Optional[str] = None
    shipping_address: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class OrderItemResponseDTO:
    """DTO for order item response."""

    id: UUID
    order_id: UUID
    product_id: UUID
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    created_at: datetime
    product_name: Optional[str] = None


@dataclass
class OrderResponseDTO:
    """DTO for order response."""

    id: UUID
    business_id: UUID
    customer_id: UUID
    order_number: str
    status: str
    total: Decimal
    created_at: datetime
    updated_at: datetime
    customer_name: Optional[str] = None
    payment_method: Optional[str] = None
    shipping_address: Optional[str] = None
    notes: Optional[str] = None
    items: Optional[list[OrderItemResponseDTO]] = None
    delivered_at: Optional[datetime] = None

