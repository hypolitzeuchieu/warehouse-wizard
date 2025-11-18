"""Sales use cases."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from django.db import transaction
from django.utils import timezone

from application.dto.sales_dto import (
    InvoiceCreateDTO,
    InvoiceLineResponseDTO,
    InvoiceResponseDTO,
)
from domain.business.services import BusinessDomainService
from domain.inventory.repositories import ProductRepository
from domain.inventory.services import InventoryDomainService
from domain.sales.entities import (
    Invoice,
    InvoiceLine,
    InvoiceStatus,
    PaymentMethod,
)
from domain.sales.repositories import (
    InvoiceLineRepository,
    InvoiceRepository,
)
from shared.exceptions.base import BaseAPIException
from shared.exceptions.specific import (
    ForbiddenError,
    NotFoundError,
)


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
        invoice_number = self.invoice_repository.get_next_invoice_number(self.business_id)

        # Calculate totals
        subtotal = Decimal("0.00")
        lines_data = []

        # Get customer if provided to check for wholesale pricing
        customer = None
        if dto.customer_id:
            from domain.customer.repositories import CustomerRepository
            from infrastructure.persistence.repositories import CustomerRepositoryImpl

            customer_repository: CustomerRepository = CustomerRepositoryImpl()
            customer = customer_repository.get_by_id(dto.customer_id)

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

            # Apply wholesale pricing if customer is a wholesaler
            from domain.sales.services import InvoiceCalculationService, WholesalePricingService

            unit_price = line_dto.unit_price
            if customer and customer.is_wholesaler():
                # Use wholesale price if customer is a wholesaler
                unit_price = WholesalePricingService.get_price_for_customer(
                    regular_price=product.get_current_price(),
                    is_wholesaler=True,
                )
                # Override with provided price if explicitly set
                if line_dto.unit_price:
                    unit_price = line_dto.unit_price

            # Calculate line total using service
            line_total = InvoiceCalculationService.calculate_line_total(
                unit_price=unit_price,
                quantity=line_dto.quantity,
                discount=line_dto.discount,
            )

            lines_data.append(
                {
                    "product": product,
                    "line_dto": line_dto,
                    "line_total": line_total,
                    "calculated_unit_price": unit_price,
                }
            )

        # Calculate final totals using service
        from domain.sales.services import InvoiceCalculationService

        subtotal = InvoiceCalculationService.calculate_subtotal(
            [{"line_total": data["line_total"]} for data in lines_data]
        )
        tax_amount = dto.tax or Decimal("0.00")
        discount_amount = dto.discount or Decimal("0.00")

        final_total = InvoiceCalculationService.calculate_final_total(
            subtotal=subtotal,
            tax=tax_amount,
            discount=discount_amount,
        )

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
            # Use the calculated unit_price (may be wholesale price)
            calculated_unit_price = line_data.get(
                "calculated_unit_price", line_data["line_dto"].unit_price
            )

            invoice_line = InvoiceLine(
                id=uuid4(),
                invoice_id=invoice.id,
                product_id=line_data["product"].id,
                quantity=line_data["line_dto"].quantity,
                unit_price=calculated_unit_price,
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
        self, invoice: Invoice, lines: list[InvoiceLine] | None = None
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
            raise NotFoundError(
                detail="Invoice not found",
                code="INVOICE_NOT_FOUND",
            )

        lines = self.invoice_line_repository.get_by_invoice(self.invoice_id)
        return self._to_dto(invoice, lines)

    def _to_dto(self, invoice: Invoice, lines: list[InvoiceLine]) -> InvoiceResponseDTO:
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


class ListInvoicesUseCase:
    """Use case for listing invoices for a business."""

    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        invoice_line_repository: InvoiceLineRepository,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,
        status: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> None:
        """Initialize use case."""
        self.invoice_repository = invoice_repository
        self.invoice_line_repository = invoice_line_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id
        self.status = InvoiceStatus(status) if status else None
        self.start_date = start_date
        self.end_date = end_date
        self.limit = limit

    def execute(self) -> list[InvoiceResponseDTO]:
        """Execute listing invoices."""
        # Check if user has access to business
        if not self.business_domain_service.user_has_access(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="You don't have access to this business",
                code="PERMISSION_DENIED",
            )

        invoices = self.invoice_repository.get_by_business(
            business_id=self.business_id,
            status=self.status,
            start_date=self.start_date,
            end_date=self.end_date,
            limit=self.limit,
        )

        result = []
        for invoice in invoices:
            lines = self.invoice_line_repository.get_by_invoice(invoice.id)
            result.append(self._to_dto(invoice, lines))

        return result

    def _to_dto(self, invoice: Invoice, lines: list[InvoiceLine]) -> InvoiceResponseDTO:
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
