"""Sales DTOs."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass
class InvoiceLineCreateDTO:
    """DTO for creating an invoice line."""

    product_id: UUID
    quantity: int
    discount: Decimal = Decimal("0.00")


@dataclass
class InvoiceCreateDTO:
    """DTO for creating an invoice."""

    customer_name: str | None = None
    customer_id: UUID | None = None
    # Fields for creating a new customer during sale
    customer_email: str | None = None
    customer_phone: str | None = None
    customer_address: str | None = None
    customer_type: str = "REGULAR"
    lines: list[InvoiceLineCreateDTO] = None
    tax: Decimal = Decimal("0.00")
    advance_paid: Decimal = Decimal("0.00")
    payment_method: str = "cash"
    due_date: datetime | None = None
    reason: str | None = None


@dataclass
class InvoiceUpdateDTO:
    """DTO for updating an invoice."""

    status: str | None = None
    tax: Decimal | None = None
    discount: Decimal | None = None
    advance_paid: Decimal | None = None
    payment_method: str | None = None
    due_date: datetime | None = None
    is_credit_settled: bool | None = None
    reason: str | None = None


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
    product_name: str | None = None


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
    customer_name: str | None = None
    customer_id: UUID | None = None
    cashier_name: str | None = None
    due_date: datetime | None = None
    reason: str | None = None
    lines: list[InvoiceLineResponseDTO] | None = None


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
    payment_method: str | None = None
    shipping_address: str | None = None
    notes: str | None = None


@dataclass
class OrderUpdateDTO:
    """DTO for updating an order."""

    status: str | None = None
    payment_method: str | None = None
    shipping_address: str | None = None
    notes: str | None = None


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
    product_name: str | None = None


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
    customer_name: str | None = None
    payment_method: str | None = None
    shipping_address: str | None = None
    notes: str | None = None
    items: list[OrderItemResponseDTO] | None = None
    delivered_at: datetime | None = None


@dataclass
class PaymentCreateDTO:
    """DTO for creating a payment."""

    amount: Decimal
    payment_method: str = "cash"
    payment_date: datetime | None = None
    notes: str | None = None
    idempotency_key: UUID | None = None  # Prevents double-spending


@dataclass
class PaymentResponseDTO:
    """DTO for payment response."""

    id: UUID
    invoice_id: UUID
    amount: Decimal
    payment_method: str
    change_amount: Decimal
    refund_amount: Decimal
    payment_date: datetime
    created_at: datetime
    updated_at: datetime
    notes: str | None = None
    created_by: UUID | None = None


@dataclass
class RefundCreateDTO:
    """DTO for creating a refund."""

    amount: Decimal
    reason: str | None = None
    restore_stock: bool = True


@dataclass
class RefundResponseDTO:
    """DTO for refund response."""

    id: UUID
    invoice_id: UUID
    refund_amount: Decimal
    new_paid_amount: Decimal
    new_remaining_amount: Decimal
    created_at: datetime


@dataclass
class ProductSearchDTO:
    """DTO for product search request."""

    query: str
    limit: int = 20


@dataclass
class ProductSearchResponseDTO:
    """DTO for product search response."""

    id: UUID
    name: str
    barcode: str | None
    unit_price: Decimal
    promo_price: Decimal | None
    quantity: int
    category_name: str | None = None
    subcategory_name: str | None = None


@dataclass
class BarcodeScanDTO:
    """DTO for barcode scan request."""

    barcode: str


@dataclass
class BarcodeScanResponseDTO:
    """DTO for barcode scan response."""

    id: UUID
    name: str
    barcode: str
    unit_price: Decimal
    promo_price: Decimal | None
    quantity: int
    category_name: str | None = None
    subcategory_name: str | None = None
    is_available: bool = True


@dataclass
class CreditApplicationDTO:
    """DTO for applying credit to invoice."""

    credit_id: UUID
    amount: Decimal | None = None  # If None, apply full credit amount
