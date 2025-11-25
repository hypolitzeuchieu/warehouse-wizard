"""Sales domain repositories (interfaces)."""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from domain.sales.entities import (
    Invoice,
    InvoiceLine,
    InvoiceLog,
    InvoicePayment,
    InvoiceStatus,
    Order,
    OrderItem,
)


class InvoiceRepository(ABC):
    """Invoice repository interface."""

    @abstractmethod
    def get_by_id(self, invoice_id: UUID) -> Invoice | None:
        """Get invoice by ID."""
        pass

    @abstractmethod
    def get_by_id_for_update(self, invoice_id: UUID) -> Invoice | None:
        """Get invoice by ID with row lock for update (prevents race conditions)."""
        pass

    @abstractmethod
    def get_by_number(self, business_id: UUID, number: int) -> Invoice | None:
        """Get invoice by number."""
        pass

    @abstractmethod
    def get_by_business(
        self,
        business_id: UUID,
        status: InvoiceStatus | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> list[Invoice]:
        """Get invoices for a business with optional filters."""
        pass

    @abstractmethod
    def create(self, invoice: Invoice) -> Invoice:
        """Create a new invoice."""
        pass

    @abstractmethod
    def update(self, invoice: Invoice) -> Invoice:
        """Update an existing invoice."""
        pass

    @abstractmethod
    def get_next_invoice_number(self, business_id: UUID) -> int:
        """Get next invoice number for a business."""
        pass


class InvoiceLineRepository(ABC):
    """Invoice line repository interface."""

    @abstractmethod
    def get_by_id(self, line_id: UUID) -> InvoiceLine | None:
        """Get invoice line by ID."""
        pass

    @abstractmethod
    def get_by_invoice(self, invoice_id: UUID) -> list[InvoiceLine]:
        """Get all lines for an invoice."""
        pass

    @abstractmethod
    def create(self, line: InvoiceLine) -> InvoiceLine:
        """Create a new invoice line."""
        pass

    @abstractmethod
    def delete(self, line_id: UUID) -> None:
        """Delete an invoice line."""
        pass


class OrderRepository(ABC):
    """Order repository interface."""

    @abstractmethod
    def get_by_id(self, order_id: UUID) -> Order | None:
        """Get order by ID."""
        pass

    @abstractmethod
    def get_by_customer(self, customer_id: UUID, limit: int = 100) -> list[Order]:
        """Get orders for a customer."""
        pass

    @abstractmethod
    def get_by_business(
        self,
        business_id: UUID,
        status: str | None = None,
        limit: int = 100,
    ) -> list[Order]:
        """Get orders for a business."""
        pass

    @abstractmethod
    def create(self, order: Order) -> Order:
        """Create a new order."""
        pass

    @abstractmethod
    def update(self, order: Order) -> Order:
        """Update an existing order."""
        pass


class OrderItemRepository(ABC):
    """Order item repository interface."""

    @abstractmethod
    def get_by_order(self, order_id: UUID) -> list[OrderItem]:
        """Get all items for an order."""
        pass

    @abstractmethod
    def create(self, item: OrderItem) -> OrderItem:
        """Create a new order item."""
        pass


class InvoicePaymentRepository(ABC):
    """Invoice payment repository interface."""

    @abstractmethod
    def get_by_id(self, payment_id: UUID) -> InvoicePayment | None:
        """Get payment by ID."""
        pass

    @abstractmethod
    def get_by_invoice(self, invoice_id: UUID, limit: int = 100) -> list[InvoicePayment]:
        """Get all payments for an invoice."""
        pass

    @abstractmethod
    def get_by_business(
        self,
        business_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> list[InvoicePayment]:
        """Get all payments for a business."""
        pass

    @abstractmethod
    def get_by_idempotency_key(
        self, invoice_id: UUID, idempotency_key: UUID
    ) -> InvoicePayment | None:
        """Get payment by idempotency key for an invoice (prevents double-spending)."""
        pass

    @abstractmethod
    def create(self, payment: InvoicePayment) -> InvoicePayment:
        """Create a new payment."""
        pass


class InvoiceLogRepository(ABC):
    """Invoice log repository interface."""

    @abstractmethod
    def get_by_id(self, log_id: UUID) -> InvoiceLog | None:
        """Get log by ID."""
        pass

    @abstractmethod
    def get_by_invoice(self, invoice_id: UUID, limit: int = 100) -> list[InvoiceLog]:
        """Get all logs for an invoice."""
        pass

    @abstractmethod
    def create(self, log: InvoiceLog) -> InvoiceLog:
        """Create a new log entry."""
        pass
