"""Sales use cases."""

from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from django.db import transaction
from django.utils import timezone

from application.dto.sales_dto import (
    InvoiceCreateDTO,
    InvoiceLineResponseDTO,
    InvoiceResponseDTO,
    InvoiceUpdateDTO,
    OrderCreateDTO,
    OrderItemResponseDTO,
    OrderResponseDTO,
    OrderUpdateDTO,
)
from domain.inventory.entities import Product
from domain.inventory.repositories import ProductRepository
from domain.inventory.services import InventoryDomainService
from domain.sales.entities import (
    Invoice,
    InvoiceLine,
    InvoiceStatus,
    Order,
    OrderItem,
    PaymentMethod,
)
from domain.sales.repositories import (
    InvoiceLineRepository,
    InvoiceRepository,
    OrderItemRepository,
    OrderRepository,
)
from shared.exceptions.base import BaseAPIException


class CreateInvoiceUseCase:
    """Use case for creating an invoice (POS)."""

    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        invoice_line_repository: InvoiceLineRepository,
        product_repository: ProductRepository,
        inventory_domain_service: InventoryDomainService,
        business_id: UUID,
        cashier_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.invoice_repository = invoice_repository
        self.invoice_line_repository = invoice_line_repository
        self.product_repository = product_repository
        self.inventory_domain_service = inventory_domain_service
        self.business_id = business_id
        self.cashier_id = cashier_id

    @transaction.atomic
    def execute(self, dto: InvoiceCreateDTO) -> InvoiceResponseDTO:
        """Execute invoice creation."""
        # Get next invoice number
        invoice_number = self.invoice_repository.get_next_invoice_number(
            self.business_id
        )

        # Calculate totals
        subtotal = Decimal("0.00")
        lines_data = []

        for line_dto in dto.lines or []:
            # Get product
            product = self.product_repository.get_by_id(line_dto.product_id)
            if not product or product.business_id != self.business_id:
                raise BaseAPIException(
                    detail=f"Product {line_dto.product_id} not found",
                    code="PRODUCT_NOT_FOUND",
                    status_code=404,
                )

            # Check stock availability
            if product.quantity < line_dto.quantity:
                raise BaseAPIException(
                    detail=f"Insufficient stock for product {product.name}",
                    code="INSUFFICIENT_STOCK",
                    status_code=400,
                )

            # Calculate line total
            line_total = (
                line_dto.unit_price * line_dto.quantity - line_dto.discount
            )
            subtotal += line_total

            lines_data.append(
                {
                    "product": product,
                    "line_dto": line_dto,
                    "line_total": line_total,
                }
            )

        # Calculate final totals
        total = subtotal
        tax_amount = dto.tax
        discount_amount = dto.discount
        final_total = total + tax_amount - discount_amount

        # Determine status
        status = InvoiceStatus.COMPLETED
        if dto.payment_method == "credit":
            status = InvoiceStatus.CREDIT

        # Create invoice
        invoice = Invoice(
            id=uuid4(),
            business_id=self.business_id,
            number=invoice_number,
            customer_name=dto.customer_name,
            customer_id=dto.customer_id,
            cashier_id=self.cashier_id,
            status=status,
            total=final_total,
            tax=tax_amount,
            discount=discount_amount,
            advance_paid=Decimal("0.00"),
            remaining_amount=final_total if status == InvoiceStatus.CREDIT else Decimal("0.00"),
            payment_method=PaymentMethod(dto.payment_method),
            due_date=dto.due_date,
            is_credit_settled=False,
            created_at=timezone.now(),
            updated_at=timezone.now(),
            reason=dto.reason,
        )

        invoice = self.invoice_repository.create(invoice)

        # Create invoice lines and update stock
        invoice_lines = []
        for line_data in lines_data:
            # Create invoice line
            invoice_line = InvoiceLine(
                id=uuid4(),
                invoice_id=invoice.id,
                product_id=line_data["product"].id,
                quantity=line_data["line_dto"].quantity,
                unit_price=line_data["line_dto"].unit_price,
                discount=line_data["line_dto"].discount,
                line_total=line_data["line_total"],
                created_at=timezone.now(),
            )
            invoice_line = self.invoice_line_repository.create(invoice_line)
            invoice_lines.append(invoice_line)

            # Update stock (record exit)
            self.inventory_domain_service.record_stock_exit(
                business_id=self.business_id,
                product_id=line_data["product"].id,
                quantity=line_data["line_dto"].quantity,
                user_id=self.cashier_id,
                reason=f"Invoice {invoice.number}",
            )

        return self._to_dto(invoice, invoice_lines)

    def _to_dto(
        self, invoice: Invoice, lines: Optional[list[InvoiceLine]] = None
    ) -> InvoiceResponseDTO:
        """Convert invoice entity to DTO."""
        return InvoiceResponseDTO(
            id=invoice.id,
            business_id=invoice.business_id,
            number=invoice.number,
            customer_name=invoice.customer_name,
            customer_id=invoice.customer_id,
            cashier_id=invoice.cashier_id,
            status=invoice.status.value,
            total=invoice.total,
            tax=invoice.tax,
            discount=invoice.discount,
            advance_paid=invoice.advance_paid,
            remaining_amount=invoice.get_remaining_amount(),
            payment_method=invoice.payment_method.value,
            due_date=invoice.due_date,
            is_credit_settled=invoice.is_credit_settled,
            reason=invoice.reason,
            lines=[
                InvoiceLineResponseDTO(
                    id=line.id,
                    invoice_id=line.invoice_id,
                    product_id=line.product_id,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    discount=line.discount,
                    line_total=line.line_total,
                    created_at=line.created_at,
                )
                for line in (lines or [])
            ],
            created_at=invoice.created_at,
            updated_at=invoice.updated_at,
        )


class GetInvoiceUseCase:
    """Use case for getting an invoice."""

    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        invoice_line_repository: InvoiceLineRepository,
        invoice_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.invoice_repository = invoice_repository
        self.invoice_line_repository = invoice_line_repository
        self.invoice_id = invoice_id

    def execute(self) -> InvoiceResponseDTO:
        """Execute getting invoice."""
        invoice = self.invoice_repository.get_by_id(self.invoice_id)
        if not invoice:
            raise BaseAPIException(
                detail="Invoice not found",
                code="INVOICE_NOT_FOUND",
                status_code=404,
            )

        lines = self.invoice_line_repository.get_by_invoice(self.invoice_id)
        return self._to_dto(invoice, lines)

    def _to_dto(
        self, invoice: Invoice, lines: list[InvoiceLine]
    ) -> InvoiceResponseDTO:
        """Convert invoice entity to DTO."""
        return InvoiceResponseDTO(
            id=invoice.id,
            business_id=invoice.business_id,
            number=invoice.number,
            customer_name=invoice.customer_name,
            customer_id=invoice.customer_id,
            cashier_id=invoice.cashier_id,
            status=invoice.status.value,
            total=invoice.total,
            tax=invoice.tax,
            discount=invoice.discount,
            advance_paid=invoice.advance_paid,
            remaining_amount=invoice.get_remaining_amount(),
            payment_method=invoice.payment_method.value,
            due_date=invoice.due_date,
            is_credit_settled=invoice.is_credit_settled,
            reason=invoice.reason,
            lines=[
                InvoiceLineResponseDTO(
                    id=line.id,
                    invoice_id=line.invoice_id,
                    product_id=line.product_id,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    discount=line.discount,
                    line_total=line.line_total,
                    created_at=line.created_at,
                )
                for line in lines
            ],
            created_at=invoice.created_at,
            updated_at=invoice.updated_at,
        )

