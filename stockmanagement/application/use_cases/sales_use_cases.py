"""Sales use cases."""

import logging
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID, uuid4

from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from application.dto.sales_dto import (
    BarcodeScanResponseDTO,
    CreditApplicationDTO,
    InvoiceCreateDTO,
    InvoiceLineCreateDTO,
    InvoiceLineResponseDTO,
    InvoiceResponseDTO,
    InvoiceUpdateDTO,
    PaymentCreateDTO,
    PaymentResponseDTO,
    ProductSearchResponseDTO,
    ReceiptResponseDTO,
    RefundCreateDTO,
    RefundResponseDTO,
    SalesByPaymentMethodDTO,
    SalesByStatusDTO,
    SalesReportDTO,
    TopCustomerReportDTO,
    TopProductReportDTO,
)
from domain.business.repositories import BusinessRepository
from domain.business.services import BusinessDomainService
from domain.credit.entities import Credit, CreditStatus
from domain.credit.repositories import CreditRepository
from domain.customer.entities import Customer, CustomerType
from domain.customer.repositories import CustomerRepository
from domain.inventory.repositories import ProductRepository
from domain.inventory.services import InventoryDomainService
from domain.notifications.services import NotificationDomainService
from domain.sales.entities import (
    Invoice,
    InvoiceLine,
    InvoiceLog,
    InvoiceLogAction,
    InvoicePayment,
    InvoiceStatus,
    PaymentMethod,
)
from domain.sales.repositories import (
    InvoiceLineRepository,
    InvoiceLogRepository,
    InvoicePaymentRepository,
    InvoiceRepository,
)
from domain.sales.services import (
    DateRangeValidationService,
    InvoiceCalculationService,
    InvoiceIntegrityService,
    InvoiceLoggingService,
    PaymentProcessingService,
    ReceiptGenerationService,
    WholesalePricingService,
)
from domain.users.repositories import UserRepository
from shared.exceptions.base import BaseAPIException
from shared.exceptions.specific import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
)
from shared.services.s3_service import S3Service
from shared.utils.validation import (
    validate_business_access,
    validate_entity_belongs_to_business,
)

logger = logging.getLogger(__name__)


def _get_cashier_name(
    user_repository: UserRepository | None, cashier_id: UUID | None
) -> str | None:
    """Helper to get cashier name from user repository."""
    if not user_repository or not cashier_id:
        return None
    cashier = user_repository.get_by_id(cashier_id)
    if cashier:
        return cashier.name or cashier.email
    return None


def _get_product_name(product_repository: ProductRepository | None, product_id: UUID) -> str | None:
    """Helper to get product name from product repository."""
    if not product_repository:
        return None
    product = product_repository.get_by_id(product_id)
    return product.name if product else None


def _invoice_to_dto(
    invoice: Invoice,
    lines: list[InvoiceLine],
    user_repository: UserRepository | None = None,
    product_repository: ProductRepository | None = None,
) -> InvoiceResponseDTO:
    """
    Convert invoice entity to DTO.

    Shared utility function to avoid code duplication across use cases.

    Args:
        invoice: Invoice entity to convert
        lines: List of invoice lines
        user_repository: Optional user repository for fetching cashier name
        product_repository: Optional product repository for fetching product names

    Returns:
        InvoiceResponseDTO instance
    """
    cashier_name = _get_cashier_name(user_repository, invoice.cashier_id)

    invoice_lines = []
    for line in lines:
        product_name = _get_product_name(product_repository, line.product_id)
        invoice_lines.append(
            InvoiceLineResponseDTO(
                id=line.id,
                invoice_id=line.invoice_id,
                product_id=line.product_id,
                quantity=line.quantity,
                unit_price=line.unit_price,
                discount=line.discount,
                line_total=line.line_total,
                created_at=line.created_at,
                product_name=product_name,
            )
        )

    refund_amount = _calculate_refund_amount(invoice.advance_paid, invoice.total)

    return InvoiceResponseDTO(
        id=invoice.id,
        business_id=invoice.business_id,
        number=invoice.number,
        customer_name=invoice.customer_name,
        customer_id=invoice.customer_id,
        cashier_id=invoice.cashier_id,
        cashier_name=cashier_name,
        status=invoice.status.value,
        total=invoice.total,
        tax=invoice.tax,
        total_discount=invoice.total_discount,
        advance_paid=invoice.advance_paid,
        remaining_amount=invoice.get_remaining_amount(),
        payment_method=invoice.payment_method.value,
        due_date=invoice.due_date,
        is_credit_settled=invoice.is_credit_settled,
        reason=invoice.reason,
        lines=invoice_lines,
        is_archived=invoice.is_archived,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
        refund_amount=refund_amount,
    )


def _calculate_refund_amount(advance_paid: Decimal, total: Decimal) -> Decimal | None:
    """
    Calculate refund amount from invoice data.

    Refund amount = advance_paid - total (if advance_paid > total)
    This is the amount to be returned to the customer after deducting what is owed.

    Args:
        advance_paid: Amount paid by customer
        total: Total amount due

    Returns:
        Refund amount if overpaid, None otherwise
    """
    if advance_paid > total:
        refund = advance_paid - total
        return refund.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return None


def _payment_to_response_dto(
    payment: InvoicePayment,
    user_repository: UserRepository | None = None,
) -> PaymentResponseDTO:
    """Helper to convert payment entity to response DTO."""
    created_by_name = _get_cashier_name(user_repository, payment.created_by)

    return PaymentResponseDTO(
        id=payment.id,
        invoice_id=payment.invoice_id,
        amount=payment.amount,
        payment_method=payment.payment_method.value,
        change_amount=payment.change_amount,
        refund_amount=payment.refund_amount,
        payment_date=payment.payment_date,
        notes=payment.notes,
        created_at=payment.created_at,
        updated_at=payment.updated_at,
        created_by=payment.created_by,
        created_by_name=created_by_name,
    )


def _create_and_save_invoice_log(
    log_data: dict,
    invoice_id: UUID,
    invoice_log_repository: InvoiceLogRepository,
) -> InvoiceLog:
    """
    Create and save invoice log (shared utility function).

    Args:
        log_data: Dictionary with log data from InvoiceLoggingService.create_log()
        invoice_id: ID of the invoice
        invoice_log_repository: Repository for saving the log

    Returns:
        Created InvoiceLog entity
    """
    invoice_log = InvoiceLog(
        id=uuid4(),
        invoice_id=invoice_id,
        action=log_data["action"],
        old_value=log_data["old_value"],
        new_value=log_data["new_value"],
        description=log_data["description"],
        created_at=timezone.now(),
        updated_at=timezone.now(),
        created_by=log_data["user_id"],
    )
    return invoice_log_repository.create(invoice_log)


class CreateInvoiceUseCase:
    """Use case for creating an invoice (POS)."""

    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        invoice_line_repository: InvoiceLineRepository,
        invoice_log_repository: InvoiceLogRepository,
        invoice_payment_repository: InvoicePaymentRepository,
        product_repository: ProductRepository,
        user_repository: UserRepository,
        inventory_domain_service: InventoryDomainService,
        credit_repository: CreditRepository,
        customer_repository: CustomerRepository,
        notification_domain_service: NotificationDomainService,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        cashier_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.invoice_repository = invoice_repository
        self.invoice_line_repository = invoice_line_repository
        self.invoice_log_repository = invoice_log_repository
        self.invoice_payment_repository = invoice_payment_repository
        self.product_repository = product_repository
        self.user_repository = user_repository
        self.inventory_domain_service = inventory_domain_service
        self.credit_repository = credit_repository
        self.customer_repository = customer_repository
        self.notification_domain_service = notification_domain_service
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.cashier_id = cashier_id

    @transaction.atomic
    def execute(self, dto: InvoiceCreateDTO) -> InvoiceResponseDTO:
        """Execute invoice creation."""
        # Check if user can access sales
        if not self.business_domain_service.can_access_sales(self.business_id, self.cashier_id):
            raise ForbiddenError(
                detail="You don't have permission to create invoices for this business",
                code="PERMISSION_DENIED",
            )
        try:
            customer, customer_id, customer_name = self._resolve_customer(dto)

            lines_data = self._process_invoice_lines(dto.lines or [], customer)

            final_total, tax_amount, advance_paid, total_discount = self._calculate_totals(
                lines_data, dto.tax or Decimal("0.00"), dto.advance_paid or Decimal("0.00")
            )

            is_credit, dto_due_date, dto_reason = self._validate_invoice_requirements(
                dto, final_total, advance_paid
            )

            status, remaining_amount = self._determine_invoice_status(
                is_credit, advance_paid, final_total
            )

            due_date, reason = self._prepare_credit_fields(
                is_credit, status, dto_due_date, dto_reason
            )

            invoice = self._create_invoice(
                dto,
                customer_id,
                customer_name,
                status,
                final_total,
                tax_amount,
                advance_paid,
                remaining_amount,
                total_discount,
                due_date,
                reason,
            )

            invoice_lines = self._create_invoice_lines_and_update_stock(invoice, lines_data)

            if status == InvoiceStatus.CREDIT and invoice.customer_id:
                self._create_credit(invoice, final_total, due_date, advance_paid)

            if advance_paid > Decimal("0.00"):
                self._create_initial_payment(invoice, advance_paid, final_total, dto.payment_method)

            self._log_invoice_creation(invoice)

            return self._to_dto(invoice, invoice_lines)
        except Exception as e:
            logger.error(
                f"Error creating invoice for business {self.business_id}: {e}",
                exc_info=True,
            )
            raise

    def _resolve_customer(self, dto: InvoiceCreateDTO) -> tuple[Customer | None, UUID | None, str]:
        """Resolve customer: get existing or create new one."""
        customer = None
        customer_id = dto.customer_id
        resolved_customer_name = dto.customer_name

        if customer_id:
            customer = self.customer_repository.get_by_id(customer_id)
            if not customer or customer.business_id != self.business_id:
                raise BaseAPIException(
                    detail=f"Customer {customer_id} not found",
                    code="CUSTOMER_NOT_FOUND",
                    status_code=404,
                )
            resolved_customer_name = customer.name
        elif dto.customer_name:
            existing_customer = None
            if dto.customer_email:
                existing_customer = self.customer_repository.get_by_email(
                    dto.customer_email, self.business_id
                )
            if not existing_customer and dto.customer_phone:
                existing_customer = self.customer_repository.get_by_phone(
                    dto.customer_phone, self.business_id
                )

            if existing_customer:
                customer = existing_customer
                customer_id = customer.id
                resolved_customer_name = customer.name
            else:
                customer = Customer(
                    id=uuid4(),
                    business_id=self.business_id,
                    name=dto.customer_name,
                    email=dto.customer_email,
                    phone_number=dto.customer_phone,
                    address=dto.customer_address,
                    customer_type=CustomerType(dto.customer_type),
                    loyalty_points=Decimal("0.00"),
                    total_purchases=Decimal("0.00"),
                    created_at=timezone.now(),
                    updated_at=timezone.now(),
                )
                customer = self.customer_repository.create(customer)
                customer_id = customer.id
                resolved_customer_name = customer.name

        if not resolved_customer_name:
            resolved_customer_name = "unknown"

        return customer, customer_id, resolved_customer_name

    def _process_invoice_lines(
        self, line_dtos: list[InvoiceLineCreateDTO], customer: Customer | None
    ) -> list[dict]:
        """Process invoice lines: validate products, calculate prices and totals."""
        lines_data = []

        for line_dto in line_dtos:
            product = self.product_repository.get_by_id_for_update(line_dto.product_id)
            if not product:
                raise BaseAPIException(
                    detail=f"Product {line_dto.product_id} not found",
                    code="PRODUCT_NOT_FOUND",
                    status_code=404,
                )
            validate_entity_belongs_to_business(
                entity=product,
                business_id=self.business_id,
                entity_name="Product",
            )

            if product.quantity < line_dto.quantity:
                raise BaseAPIException(
                    detail=f"Insufficient stock for product {product.name}",
                    code="INSUFFICIENT_STOCK",
                    status_code=400,
                )

            unit_price = product.get_current_price()
            if customer and customer.is_wholesaler():
                unit_price = WholesalePricingService.get_price_for_customer(
                    regular_price=product.get_current_price(),
                    is_wholesaler=True,
                )

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

        return lines_data

    def _calculate_totals(
        self, lines_data: list[dict], tax_amount: Decimal, advance_paid: Decimal
    ) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        """Calculate invoice totals including total discount from all lines."""
        subtotal = InvoiceCalculationService.calculate_subtotal(
            [{"line_total": data["line_total"]} for data in lines_data]
        )

        total_discount = sum(line_data["line_dto"].discount for line_data in lines_data)

        final_total = subtotal + tax_amount
        if final_total < Decimal("0.00"):
            final_total = Decimal("0.00")

        return final_total, tax_amount, advance_paid, total_discount

    def _validate_invoice_requirements(
        self, dto: InvoiceCreateDTO, final_total: Decimal, advance_paid: Decimal
    ) -> tuple[bool, datetime | None, str | None]:
        """
        Validate invoice requirements and return is_credit flag, due_date, and reason.
        Auto-populates due_date and reason for regular invoices with partial payment.
        """
        is_credit = dto.is_credit
        due_date = dto.due_date
        reason = dto.reason

        if is_credit:
            if not dto.due_date:
                raise BaseAPIException(
                    detail="due_date is required for credit invoices",
                    code="MISSING_DUE_DATE",
                    status_code=400,
                )
            if not dto.reason or not dto.reason.strip():
                raise BaseAPIException(
                    detail="reason is required for credit invoices",
                    code="MISSING_REASON",
                    status_code=400,
                )

        return is_credit, due_date, reason

    def _determine_invoice_status(
        self, is_credit: bool, advance_paid: Decimal, final_total: Decimal
    ) -> tuple[InvoiceStatus, Decimal]:
        """
        Determine invoice status and calculate remaining amount.
        """
        if is_credit:
            if advance_paid > final_total:
                status = InvoiceStatus.COMPLETED
                remaining_amount = Decimal("0.00")
            else:
                status = InvoiceStatus.CREDIT
                remaining_amount = final_total - advance_paid
        elif advance_paid < final_total:
            status = InvoiceStatus.CREDIT
            remaining_amount = final_total - advance_paid
        else:
            status = InvoiceStatus.COMPLETED
            remaining_amount = Decimal("0.00")

        if remaining_amount < Decimal("0.00"):
            remaining_amount = Decimal("0.00")

        return status, remaining_amount

    def _prepare_credit_fields(
        self,
        is_credit: bool,
        status: InvoiceStatus,
        dto_due_date: datetime | None,
        dto_reason: str | None,
    ) -> tuple[datetime | None, str | None]:
        """
        Prepare due_date and reason for invoices with CREDIT status.
        """
        if status == InvoiceStatus.CREDIT:
            if not dto_due_date:
                due_date = (timezone.now() + timedelta(days=15)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
            else:
                due_date = dto_due_date

            if not dto_reason or not dto_reason.strip():
                if is_credit:
                    reason = dto_reason or "Credit invoice"
                else:
                    reason = "Partial payment - balance due"
            else:
                reason = dto_reason

            return due_date, reason

        return dto_due_date, dto_reason

    def _create_invoice(
        self,
        dto: InvoiceCreateDTO,
        customer_id: UUID | None,
        customer_name: str,
        status: InvoiceStatus,
        final_total: Decimal,
        tax_amount: Decimal,
        advance_paid: Decimal,
        remaining_amount: Decimal,
        total_discount: Decimal,
        due_date: datetime | None,
        reason: str | None,
    ) -> Invoice:
        """Create and persist invoice entity."""
        invoice_number = self.invoice_repository.get_next_invoice_number(self.business_id)

        invoice = Invoice(
            id=uuid4(),
            business_id=self.business_id,
            number=invoice_number,
            customer_name=customer_name,
            customer_id=customer_id,
            cashier_id=self.cashier_id,
            status=status,
            total=final_total,
            tax=tax_amount,
            total_discount=total_discount,
            advance_paid=advance_paid,
            remaining_amount=(
                remaining_amount if status == InvoiceStatus.CREDIT else Decimal("0.00")
            ),
            payment_method=PaymentMethod(dto.payment_method),
            due_date=due_date,
            is_credit_settled=False,
            created_at=timezone.now(),
            updated_at=timezone.now(),
            reason=reason,
            is_archived=False,
        )

        invoice = self.invoice_repository.create(invoice)
        InvoiceIntegrityService.validate_invoice_integrity(invoice)

        return invoice

    def _create_invoice_lines_and_update_stock(
        self, invoice: Invoice, lines_data: list[dict]
    ) -> list[InvoiceLine]:
        """Create invoice lines, update stock, and send low stock notifications."""
        invoice_lines = []

        for line_data in lines_data:
            calculated_unit_price = line_data["calculated_unit_price"]

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

            self.inventory_domain_service.record_stock_exit(
                business_id=self.business_id,
                product_id=line_data["product"].id,
                quantity=line_data["line_dto"].quantity,
                user_id=self.cashier_id,
                reason=f"Invoice {invoice.number}",
            )

            self._check_and_notify_low_stock(line_data["product"].id, invoice.number)

        return invoice_lines

    def _check_and_notify_low_stock(self, product_id: UUID, invoice_number: int) -> None:
        """Check if product is low stock and send notification."""
        updated_product = self.product_repository.get_by_id(product_id)
        if updated_product and updated_product.is_low_stock():
            try:
                self.notification_domain_service.notify_low_stock(
                    product_id=updated_product.id,
                    product_name=updated_product.name,
                    business_id=self.business_id,
                    current_quantity=updated_product.quantity,
                    min_quantity=updated_product.min_quantity,
                )
                logger.info(
                    f"Low stock notification sent for product {updated_product.id} "
                    f"after invoice {invoice_number}"
                )
            except Exception as notif_error:
                logger.warning(
                    f"Failed to send low stock notification for product {product_id}: {notif_error}",
                    exc_info=True,
                )

    def _create_credit(
        self,
        invoice: Invoice,
        final_total: Decimal,
        due_date: datetime | None,
        advance_paid: Decimal = Decimal("0.00"),
    ) -> None:
        """Create credit record for credit invoice."""
        if due_date is None:
            credit_due_date = timezone.now() + timedelta(days=15)
        else:
            credit_due_date = due_date

        remaining_amount = final_total - advance_paid
        if remaining_amount < Decimal("0.00"):
            remaining_amount = Decimal("0.00")

        credit = Credit(
            id=uuid4(),
            business_id=self.business_id,
            customer_id=invoice.customer_id,
            invoice_id=invoice.id,
            amount=final_total,
            paid_amount=advance_paid,
            remaining_amount=remaining_amount,
            due_date=credit_due_date,
            status=CreditStatus.PENDING,
            notes=f"Credit created for Invoice {invoice.number}",
            created_at=timezone.now(),
            updated_at=timezone.now(),
            created_by=self.cashier_id,
        )
        credit.update_status()
        self.credit_repository.create(credit)

    def _create_initial_payment(
        self,
        invoice: Invoice,
        advance_paid: Decimal,
        final_total: Decimal,
        payment_method: str,
    ) -> None:
        """Create initial payment record with automatic refund if overpaid."""
        change_amount = Decimal("0.00")
        refund_amount = Decimal("0.00")

        if advance_paid > final_total:
            refund_amount = advance_paid - final_total
            refund_amount = refund_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            change_amount = refund_amount
            logger.info(
                f"Automatic refund created for invoice {invoice.number}: "
                f"overpayment of {refund_amount} (advance_paid={advance_paid}, total={final_total})"
            )

        payment = InvoicePayment(
            id=uuid4(),
            invoice_id=invoice.id,
            amount=advance_paid,
            payment_method=PaymentMethod(payment_method),
            change_amount=change_amount,
            refund_amount=refund_amount,
            payment_date=timezone.now(),
            notes=(
                f"Initial payment for invoice {invoice.number}"
                + (
                    f". Automatic refund: {refund_amount}"
                    if refund_amount > Decimal("0.00")
                    else ""
                )
            ),
            idempotency_key=None,
            created_at=timezone.now(),
            updated_at=timezone.now(),
            created_by=self.cashier_id,
        )
        self.invoice_payment_repository.create(payment)

    def _log_invoice_creation(self, invoice: Invoice) -> None:
        """Log invoice creation."""
        log_data = InvoiceLoggingService.create_log(
            invoice_id=invoice.id,
            action=InvoiceLogAction.CREATED,
            old_value=None,
            new_value=f"status={invoice.status.value}, total={invoice.total}, customer_id={invoice.customer_id}",
            description=f"Invoice {invoice.number} created",
            user_id=self.cashier_id,
        )
        _create_and_save_invoice_log(
            log_data=log_data,
            invoice_id=invoice.id,
            invoice_log_repository=self.invoice_log_repository,
        )

    def _to_dto(
        self, invoice: Invoice, lines: list[InvoiceLine] | None = None
    ) -> InvoiceResponseDTO:
        """Convert invoice entity to DTO."""
        return _invoice_to_dto(
            invoice=invoice,
            lines=lines or [],
            user_repository=self.user_repository,
            product_repository=self.product_repository,
        )


class GetInvoiceUseCase:
    """Use case for getting an invoice."""

    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        invoice_line_repository: InvoiceLineRepository,
        invoice_payment_repository: InvoicePaymentRepository,
        product_repository: ProductRepository,
        user_repository: UserRepository,
        invoice_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.invoice_repository = invoice_repository
        self.invoice_line_repository = invoice_line_repository
        self.invoice_payment_repository = invoice_payment_repository
        self.product_repository = product_repository
        self.user_repository = user_repository
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
        return _invoice_to_dto(
            invoice=invoice,
            lines=lines,
            user_repository=self.user_repository,
            product_repository=self.product_repository,
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
        archived_only: bool = False,
        product_repository: ProductRepository | None = None,
        user_repository: UserRepository | None = None,
    ) -> None:
        """Initialize use case."""
        self.invoice_repository = invoice_repository
        self.invoice_line_repository = invoice_line_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id
        self.product_repository = product_repository
        self.user_repository = user_repository
        self.status = None
        if status:
            status_upper = status.upper()
            status_mapping = {
                "PAID": InvoiceStatus.COMPLETED.value,
                "PARTIAL": InvoiceStatus.CREDIT.value,
                "REFUNDED": InvoiceStatus.CANCELLED.value,
            }
            mapped_status = status_mapping.get(status_upper, status_upper)
            try:
                self.status = InvoiceStatus(mapped_status)
            except ValueError as err:
                raise BadRequestError(
                    detail=f"Invalid status filter: {status}",
                    code="INVALID_INVOICE_STATUS",
                ) from err
        self.start_date = start_date
        self.end_date = end_date
        self.limit = limit
        self.archived_only = archived_only

    def execute(self) -> list[InvoiceResponseDTO]:
        """Execute listing invoices."""
        if not self.business_domain_service.can_access_sales(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="You don't have permission to access sales for this business",
                code="PERMISSION_DENIED",
            )

        invoices = self.invoice_repository.get_by_business(
            business_id=self.business_id,
            status=self.status,
            start_date=self.start_date,
            end_date=self.end_date,
            limit=self.limit,
            archived_only=self.archived_only,
        )

        result = []
        for invoice in invoices:
            lines = self.invoice_line_repository.get_by_invoice(invoice.id)
            result.append(self._to_dto(invoice, lines))

        return result

    def _to_dto(self, invoice: Invoice, lines: list[InvoiceLine]) -> InvoiceResponseDTO:
        """Convert invoice entity to DTO."""
        return _invoice_to_dto(
            invoice=invoice,
            lines=lines,
            user_repository=self.user_repository,
            product_repository=self.product_repository,
        )


class UpdateInvoiceUseCase:
    """Use case for updating an invoice."""

    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        invoice_line_repository: InvoiceLineRepository,
        invoice_log_repository: InvoiceLogRepository,
        product_repository: ProductRepository,
        user_repository: UserRepository,
        inventory_domain_service: InventoryDomainService,
        business_domain_service: BusinessDomainService,
        invoice_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.invoice_repository = invoice_repository
        self.invoice_line_repository = invoice_line_repository
        self.invoice_log_repository = invoice_log_repository
        self.product_repository = product_repository
        self.user_repository = user_repository
        self.inventory_domain_service = inventory_domain_service
        self.business_domain_service = business_domain_service
        self.invoice_id = invoice_id
        self.user_id = user_id

    @transaction.atomic
    def execute(self, dto: InvoiceUpdateDTO) -> InvoiceResponseDTO:
        """Execute invoice update."""
        invoice = self.invoice_repository.get_by_id(self.invoice_id)
        if not invoice:
            raise NotFoundError(
                detail="Invoice not found",
                code="INVOICE_NOT_FOUND",
            )

        # Check if user can access sales
        if not self.business_domain_service.can_access_sales(invoice.business_id, self.user_id):
            raise ForbiddenError(
                detail="You don't have permission to update invoices for this business",
                code="PERMISSION_DENIED",
            )

        if invoice.status == InvoiceStatus.COMPLETED and dto.status != "CANCELLED":
            raise BaseAPIException(
                detail="Cannot update a completed invoice",
                code="INVOICE_ALREADY_COMPLETED",
                status_code=400,
            )

        old_status = invoice.status.value
        old_total = invoice.total
        old_discount = invoice.total_discount
        old_tax = invoice.tax

        if dto.status is not None:
            invoice.status = InvoiceStatus(dto.status)

        if dto.tax is not None:
            invoice.tax = dto.tax

        if dto.total_discount is not None:
            invoice.total_discount = dto.total_discount

        if dto.advance_paid is not None:
            invoice.advance_paid = dto.advance_paid

        if dto.payment_method is not None:
            invoice.payment_method = PaymentMethod(dto.payment_method)

        if dto.due_date is not None:
            invoice.due_date = dto.due_date

        if dto.is_credit_settled is not None:
            invoice.is_credit_settled = dto.is_credit_settled

        if dto.reason is not None:
            invoice.reason = dto.reason

        if dto.is_archived is not None:
            invoice.is_archived = dto.is_archived

        if dto.tax is not None or dto.total_discount is not None:
            lines = self.invoice_line_repository.get_by_invoice(self.invoice_id)
            subtotal = InvoiceCalculationService.calculate_subtotal(lines)
            invoice.total = InvoiceCalculationService.calculate_final_total(
                subtotal=subtotal,
                tax=invoice.tax,
                discount=invoice.total_discount,
            )

        if invoice.status == InvoiceStatus.CREDIT:
            invoice.remaining_amount = invoice.get_remaining_amount()
        else:
            invoice.remaining_amount = Decimal("0.00")

        invoice.updated_at = timezone.now()
        invoice = self.invoice_repository.update(invoice)

        log_data = InvoiceLoggingService.create_log(
            invoice_id=invoice.id,
            action=InvoiceLogAction.UPDATED,
            old_value=f"status={old_status}, total={old_total}, discount={old_discount}, tax={old_tax}",
            new_value=f"status={invoice.status.value}, total={invoice.total}, discount={invoice.total_discount}, tax={invoice.tax}",
            description=f"Invoice updated by user {self.user_id}",
            user_id=self.user_id,
        )
        _create_and_save_invoice_log(
            log_data=log_data,
            invoice_id=invoice.id,
            invoice_log_repository=self.invoice_log_repository,
        )

        lines = self.invoice_line_repository.get_by_invoice(self.invoice_id)
        return self._to_dto(invoice, lines)

    def _to_dto(self, invoice: Invoice, lines: list[InvoiceLine]) -> InvoiceResponseDTO:
        """Convert invoice entity to DTO."""
        return _invoice_to_dto(
            invoice=invoice,
            lines=lines,
            user_repository=self.user_repository,
            product_repository=self.product_repository,
        )


class PayInvoiceUseCase:
    """Use case for processing a payment on an invoice."""

    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        invoice_line_repository: InvoiceLineRepository,
        invoice_payment_repository: InvoicePaymentRepository,
        invoice_log_repository: InvoiceLogRepository,
        product_repository: ProductRepository,
        user_repository: UserRepository,
        credit_repository: CreditRepository,
        business_domain_service: BusinessDomainService,
        invoice_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.invoice_repository = invoice_repository
        self.invoice_line_repository = invoice_line_repository
        self.invoice_payment_repository = invoice_payment_repository
        self.invoice_log_repository = invoice_log_repository
        self.product_repository = product_repository
        self.user_repository = user_repository
        self.credit_repository = credit_repository
        self.business_domain_service = business_domain_service
        self.invoice_id = invoice_id
        self.user_id = user_id

    @transaction.atomic
    def execute(self, dto: PaymentCreateDTO) -> tuple[InvoiceResponseDTO, PaymentResponseDTO]:
        """Execute payment processing."""
        try:
            invoice = self.invoice_repository.get_by_id_for_update(self.invoice_id)
            if not invoice:
                raise NotFoundError(
                    detail="Invoice not found",
                    code="INVOICE_NOT_FOUND",
                )

            # Check if user can access sales
            if not self.business_domain_service.can_access_sales(invoice.business_id, self.user_id):
                raise ForbiddenError(
                    detail="You don't have permission to process payments for this business",
                    code="PERMISSION_DENIED",
                )

            if dto.idempotency_key:
                existing_payment = self.invoice_payment_repository.get_by_idempotency_key(
                    invoice_id=self.invoice_id,
                    idempotency_key=dto.idempotency_key,
                )
                if existing_payment:
                    logger.info(
                        f"Duplicate payment detected with idempotency_key {dto.idempotency_key}, "
                        f"returning existing payment {existing_payment.id}"
                    )
                    lines = self.invoice_line_repository.get_by_invoice(self.invoice_id)
                    invoice_dto = self._to_invoice_dto(invoice, lines)
                    payment_dto = self._to_payment_dto(existing_payment)
                    return invoice_dto, payment_dto

            payment_result = PaymentProcessingService.process_payment(
                payment_amount=dto.amount,
                invoice_total=invoice.total,
                already_paid=invoice.advance_paid,
            )

            invoice.advance_paid = payment_result["new_paid"]
            invoice.remaining_amount = payment_result["new_remaining"]

            if payment_result["is_fully_paid"]:
                invoice.status = InvoiceStatus.COMPLETED
                invoice.is_credit_settled = True

            invoice.updated_at = timezone.now()
            invoice = self.invoice_repository.update(invoice)

            InvoiceIntegrityService.validate_invoice_integrity(invoice)

            payment_date = dto.payment_date or timezone.now()
            payment = InvoicePayment(
                id=uuid4(),
                invoice_id=invoice.id,
                amount=dto.amount,
                payment_method=PaymentMethod(dto.payment_method),
                change_amount=payment_result["change_amount"],
                refund_amount=Decimal("0.00"),
                payment_date=payment_date,
                notes=dto.notes,
                idempotency_key=dto.idempotency_key,
                created_at=timezone.now(),
                updated_at=timezone.now(),
                created_by=self.user_id,
            )
            payment = self.invoice_payment_repository.create(payment)

            if invoice.customer_id:
                credits = self.credit_repository.get_by_customer(
                    customer_id=invoice.customer_id,
                    business_id=invoice.business_id,
                )
                for credit_temp in credits:
                    if credit_temp.invoice_id == invoice.id:
                        credit = self.credit_repository.get_by_id_for_update(credit_temp.id)
                        if credit:
                            credit.paid_amount += payment_result["amount_applied"]
                            credit.remaining_amount -= payment_result["amount_applied"]
                            credit.updated_at = timezone.now()
                            credit.update_status()
                            self.credit_repository.update(credit)

            log_data = InvoiceLoggingService.create_log(
                invoice_id=invoice.id,
                action=InvoiceLogAction.PAYMENT_RECEIVED,
                old_value=f"advance_paid={invoice.advance_paid - payment_result['amount_applied']}, remaining={invoice.remaining_amount + payment_result['amount_applied']}",
                new_value=f"advance_paid={invoice.advance_paid}, remaining={invoice.remaining_amount}",
                description=f"Payment of {dto.amount} received via {dto.payment_method}. Change: {payment_result['change_amount']}",
                user_id=self.user_id,
            )
            _create_and_save_invoice_log(
                log_data=log_data,
                invoice_id=invoice.id,
                invoice_log_repository=self.invoice_log_repository,
            )

            lines = self.invoice_line_repository.get_by_invoice(self.invoice_id)
            invoice_dto = self._to_invoice_dto(invoice, lines)
            payment_dto = self._to_payment_dto(payment)

            return invoice_dto, payment_dto
        except Exception as e:
            logger.error(
                f"Error processing payment for invoice {self.invoice_id}: {e}",
                exc_info=True,
            )
            raise

    def _to_invoice_dto(self, invoice: Invoice, lines: list[InvoiceLine]) -> InvoiceResponseDTO:
        """Convert invoice entity to DTO."""
        return _invoice_to_dto(
            invoice=invoice,
            lines=lines,
            user_repository=self.user_repository,
            product_repository=self.product_repository,
        )

    def _to_payment_dto(self, payment: InvoicePayment) -> PaymentResponseDTO:
        """Convert payment entity to DTO."""
        return _payment_to_response_dto(payment, self.user_repository)


class CancelInvoiceUseCase:
    """Use case for cancelling an invoice with stock restoration."""

    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        invoice_line_repository: InvoiceLineRepository,
        invoice_log_repository: InvoiceLogRepository,
        product_repository: ProductRepository,
        user_repository: UserRepository,
        inventory_domain_service: InventoryDomainService,
        credit_repository: CreditRepository,
        business_domain_service: BusinessDomainService,
        invoice_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.invoice_repository = invoice_repository
        self.invoice_line_repository = invoice_line_repository
        self.invoice_log_repository = invoice_log_repository
        self.product_repository = product_repository
        self.user_repository = user_repository
        self.inventory_domain_service = inventory_domain_service
        self.credit_repository = credit_repository
        self.business_domain_service = business_domain_service
        self.invoice_id = invoice_id
        self.user_id = user_id

    @transaction.atomic
    def execute(self, reason: str | None = None) -> InvoiceResponseDTO:
        """Execute invoice cancellation."""
        invoice = self.invoice_repository.get_by_id(self.invoice_id)
        if not invoice:
            raise NotFoundError(
                detail="Invoice not found",
                code="INVOICE_NOT_FOUND",
            )

        # Check if user can access sales
        if not self.business_domain_service.can_access_sales(invoice.business_id, self.user_id):
            raise ForbiddenError(
                detail="You don't have permission to cancel invoices for this business",
                code="PERMISSION_DENIED",
            )

        if invoice.status == InvoiceStatus.CANCELLED:
            raise BaseAPIException(
                detail="Invoice is already cancelled",
                code="INVOICE_ALREADY_CANCELLED",
                status_code=400,
            )

        lines = self.invoice_line_repository.get_by_invoice(self.invoice_id)
        for line in lines:
            self.inventory_domain_service.record_stock_entry(
                business_id=invoice.business_id,
                product_id=line.product_id,
                quantity=line.quantity,
                user_id=self.user_id,
                reason=f"Cancellation of Invoice {invoice.number}",
            )

        if invoice.customer_id:
            credits = self.credit_repository.get_by_customer(
                customer_id=invoice.customer_id,
                business_id=invoice.business_id,
            )
            for credit in credits:
                if credit.invoice_id == invoice.id:
                    credit.status = CreditStatus.CANCELLED
                    credit.updated_at = timezone.now()
                    self.credit_repository.update(credit)
                    break

        old_status = invoice.status.value
        invoice.status = InvoiceStatus.CANCELLED
        invoice.reason = reason or "Invoice cancelled"
        invoice.updated_at = timezone.now()
        invoice = self.invoice_repository.update(invoice)

        log_data = InvoiceLoggingService.create_log(
            invoice_id=invoice.id,
            action=InvoiceLogAction.CANCELLED,
            old_value=f"status={old_status}",
            new_value=f"status={invoice.status.value}",
            description=f"Invoice cancelled. Reason: {invoice.reason}",
            user_id=self.user_id,
        )
        _create_and_save_invoice_log(
            log_data=log_data,
            invoice_id=invoice.id,
            invoice_log_repository=self.invoice_log_repository,
        )

        return self._to_dto(invoice, lines)

    def _to_dto(self, invoice: Invoice, lines: list[InvoiceLine]) -> InvoiceResponseDTO:
        """Convert invoice entity to DTO."""
        return _invoice_to_dto(
            invoice=invoice,
            lines=lines,
            user_repository=self.user_repository,
            product_repository=self.product_repository,
        )


class ArchiveInvoiceUseCase:
    """Use case for archiving an invoice (soft delete)."""

    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        invoice_line_repository: InvoiceLineRepository,
        invoice_log_repository: InvoiceLogRepository,
        product_repository: ProductRepository,
        user_repository: UserRepository,
        business_domain_service: BusinessDomainService,
        invoice_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.invoice_repository = invoice_repository
        self.invoice_line_repository = invoice_line_repository
        self.invoice_log_repository = invoice_log_repository
        self.product_repository = product_repository
        self.user_repository = user_repository
        self.business_domain_service = business_domain_service
        self.invoice_id = invoice_id
        self.user_id = user_id

    @transaction.atomic
    def execute(self, reason: str | None = None) -> InvoiceResponseDTO:
        """Archive invoice without altering stock."""
        invoice = self.invoice_repository.get_by_id(self.invoice_id)
        if not invoice:
            raise NotFoundError(
                detail="Invoice not found",
                code="INVOICE_NOT_FOUND",
            )

        # Check if user can access sales (owner, manager, cashier can archive)
        if not self.business_domain_service.can_access_sales(invoice.business_id, self.user_id):
            raise ForbiddenError(
                detail="You don't have permission to archive invoices for this business",
                code="PERMISSION_DENIED",
            )

        if invoice.is_archived:
            raise BaseAPIException(
                detail="Invoice is already archived",
                code="INVOICE_ALREADY_ARCHIVED",
                status_code=400,
            )

        invoice.is_archived = True
        if reason:
            invoice.reason = reason
        invoice.updated_at = timezone.now()
        invoice = self.invoice_repository.update(invoice)

        log_data = InvoiceLoggingService.create_log(
            invoice_id=invoice.id,
            action=InvoiceLogAction.ARCHIVED,
            old_value="is_archived=False",
            new_value="is_archived=True",
            description=reason or "Invoice archived",
            user_id=self.user_id,
        )
        _create_and_save_invoice_log(
            log_data=log_data,
            invoice_id=invoice.id,
            invoice_log_repository=self.invoice_log_repository,
        )

        lines = self.invoice_line_repository.get_by_invoice(self.invoice_id)
        return self._to_dto(invoice, lines)

    def _to_dto(self, invoice: Invoice, lines: list[InvoiceLine]) -> InvoiceResponseDTO:
        """Convert archived invoice to DTO."""
        return _invoice_to_dto(
            invoice=invoice,
            lines=lines,
            user_repository=self.user_repository,
            product_repository=self.product_repository,
        )


class DeleteInvoiceUseCase:
    """Use case for permanently deleting an invoice (hard delete)."""

    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        credit_repository: CreditRepository,
        business_domain_service: BusinessDomainService,
        invoice_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.invoice_repository = invoice_repository
        self.credit_repository = credit_repository
        self.business_domain_service = business_domain_service
        self.invoice_id = invoice_id
        self.user_id = user_id

    @transaction.atomic
    def execute(self) -> None:
        """Permanently delete invoice and all related records."""
        invoice = self.invoice_repository.get_by_id(self.invoice_id)
        if not invoice:
            raise NotFoundError(
                detail="Invoice not found",
                code="INVOICE_NOT_FOUND",
            )

        validate_business_access(
            business_domain_service=self.business_domain_service,
            business_id=invoice.business_id,
            user_id=self.user_id,
            error_message="Only owners or managers can permanently delete invoices",
        )

        credit = self.credit_repository.get_by_invoice(self.invoice_id)
        if credit:
            self.credit_repository.delete(credit.id)
        self.invoice_repository.delete(self.invoice_id)


class ProcessRefundUseCase:
    """Use case for processing a refund on an invoice."""

    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        invoice_payment_repository: InvoicePaymentRepository,
        invoice_line_repository: InvoiceLineRepository,
        invoice_log_repository: InvoiceLogRepository,
        product_repository: ProductRepository,
        user_repository: UserRepository,
        inventory_domain_service: InventoryDomainService,
        invoice_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.invoice_repository = invoice_repository
        self.invoice_payment_repository = invoice_payment_repository
        self.invoice_line_repository = invoice_line_repository
        self.invoice_log_repository = invoice_log_repository
        self.product_repository = product_repository
        self.user_repository = user_repository
        self.inventory_domain_service = inventory_domain_service
        self.invoice_id = invoice_id
        self.user_id = user_id

    @transaction.atomic
    def execute(self, dto: RefundCreateDTO) -> RefundResponseDTO:
        """Execute refund processing."""
        invoice = self.invoice_repository.get_by_id(self.invoice_id)
        if not invoice:
            raise NotFoundError(
                detail="Invoice not found",
                code="INVOICE_NOT_FOUND",
            )

        refund_result = PaymentProcessingService.calculate_refund(
            refund_amount=dto.amount,
            invoice_total=invoice.total,
            already_paid=invoice.advance_paid,
        )

        invoice.advance_paid = refund_result["new_paid"]
        invoice.remaining_amount = refund_result["new_remaining"]

        if refund_result["new_paid"] <= Decimal("0.00"):
            invoice.status = InvoiceStatus.CANCELLED

        invoice.updated_at = timezone.now()
        invoice = self.invoice_repository.update(invoice)

        if dto.restore_stock:
            lines = self.invoice_line_repository.get_by_invoice(self.invoice_id)
            for line in lines:
                self.inventory_domain_service.record_stock_entry(
                    business_id=invoice.business_id,
                    product_id=line.product_id,
                    quantity=line.quantity,
                    user_id=self.user_id,
                    reason=f"Refund for Invoice {invoice.number}",
                )

        payment = InvoicePayment(
            id=uuid4(),
            invoice_id=invoice.id,
            amount=Decimal("0.00"),
            payment_method=PaymentMethod.CASH,
            change_amount=Decimal("0.00"),
            refund_amount=refund_result["refund_amount"],
            payment_date=timezone.now(),
            notes=f"Refund: {dto.reason or 'No reason provided'}",
            idempotency_key=None,
            created_at=timezone.now(),
            updated_at=timezone.now(),
            created_by=self.user_id,
        )
        payment = self.invoice_payment_repository.create(payment)

        log_data = InvoiceLoggingService.create_log(
            invoice_id=invoice.id,
            action=InvoiceLogAction.REFUNDED,
            old_value=f"advance_paid={invoice.advance_paid + refund_result['refund_amount']}, remaining={invoice.remaining_amount - refund_result['refund_amount']}",
            new_value=f"advance_paid={invoice.advance_paid}, remaining={invoice.remaining_amount}",
            description=f"Refund of {refund_result['refund_amount']} processed. Reason: {dto.reason or 'No reason provided'}",
            user_id=self.user_id,
        )
        _create_and_save_invoice_log(
            log_data=log_data,
            invoice_id=invoice.id,
            invoice_log_repository=self.invoice_log_repository,
        )

        return RefundResponseDTO(
            id=payment.id,
            invoice_id=invoice.id,
            refund_amount=refund_result["refund_amount"],
            new_paid_amount=refund_result["new_paid"],
            new_remaining_amount=refund_result["new_remaining"],
            created_at=payment.created_at,
        )


class DeleteInvoiceLineUseCase:
    """Use case for deleting an invoice line."""

    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        invoice_line_repository: InvoiceLineRepository,
        invoice_log_repository: InvoiceLogRepository,
        inventory_domain_service: InventoryDomainService,
        line_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.invoice_repository = invoice_repository
        self.invoice_line_repository = invoice_line_repository
        self.invoice_log_repository = invoice_log_repository
        self.inventory_domain_service = inventory_domain_service
        self.line_id = line_id
        self.user_id = user_id

    @transaction.atomic
    def execute(self) -> InvoiceResponseDTO:
        """Execute line deletion."""
        line_to_delete = self.invoice_line_repository.get_by_id(self.line_id)

        if not line_to_delete:
            raise NotFoundError(
                detail="Invoice line not found",
                code="INVOICE_LINE_NOT_FOUND",
            )

        invoice = self.invoice_repository.get_by_id(line_to_delete.invoice_id)

        if not invoice:
            raise NotFoundError(
                detail="Invoice not found",
                code="INVOICE_NOT_FOUND",
            )

        if invoice.status == InvoiceStatus.COMPLETED:
            raise BaseAPIException(
                detail="Cannot delete line from completed invoice",
                code="INVOICE_ALREADY_COMPLETED",
                status_code=400,
            )

        self.inventory_domain_service.record_stock_entry(
            business_id=invoice.business_id,
            product_id=line_to_delete.product_id,
            quantity=line_to_delete.quantity,
            user_id=self.user_id,
            reason=f"Line removed from Invoice {invoice.number}",
        )

        self.invoice_line_repository.delete(self.line_id)

        remaining_lines = self.invoice_line_repository.get_by_invoice(invoice.id)
        subtotal = InvoiceCalculationService.calculate_subtotal(remaining_lines)
        invoice.total = InvoiceCalculationService.calculate_final_total(
            subtotal=subtotal,
            tax=invoice.tax,
            discount=invoice.total_discount,
        )

        if invoice.status == InvoiceStatus.CREDIT:
            invoice.remaining_amount = invoice.get_remaining_amount()
        else:
            invoice.remaining_amount = Decimal("0.00")

        invoice.updated_at = timezone.now()
        invoice = self.invoice_repository.update(invoice)

        log_data = InvoiceLoggingService.create_log(
            invoice_id=invoice.id,
            action=InvoiceLogAction.LINE_REMOVED,
            old_value=f"line_id={line_to_delete.id}, product_id={line_to_delete.product_id}, quantity={line_to_delete.quantity}",
            new_value="line removed",
            description=f"Line removed from invoice. Product: {line_to_delete.product_id}, Quantity: {line_to_delete.quantity}",
            user_id=self.user_id,
        )
        _create_and_save_invoice_log(
            log_data=log_data,
            invoice_id=invoice.id,
            invoice_log_repository=self.invoice_log_repository,
        )

        return self._to_dto(invoice, remaining_lines)

    def _to_dto(self, invoice: Invoice, lines: list[InvoiceLine]) -> InvoiceResponseDTO:
        """Convert invoice entity to DTO."""
        return _invoice_to_dto(
            invoice=invoice,
            lines=lines,
            user_repository=self.user_repository,
            product_repository=self.product_repository,
        )


class ApplyCreditToInvoiceUseCase:
    """Use case for applying a credit to an invoice."""

    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        invoice_line_repository: InvoiceLineRepository,
        invoice_log_repository: InvoiceLogRepository,
        invoice_payment_repository: InvoicePaymentRepository,
        product_repository: ProductRepository,
        user_repository: UserRepository,
        credit_repository: CreditRepository,
        invoice_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.invoice_repository = invoice_repository
        self.invoice_line_repository = invoice_line_repository
        self.invoice_log_repository = invoice_log_repository
        self.invoice_payment_repository = invoice_payment_repository
        self.product_repository = product_repository
        self.user_repository = user_repository
        self.credit_repository = credit_repository
        self.invoice_id = invoice_id
        self.user_id = user_id

    @transaction.atomic
    def execute(self, dto: CreditApplicationDTO) -> InvoiceResponseDTO:
        """Execute credit payment application to invoice."""
        if dto.amount <= Decimal("0.00"):
            raise BaseAPIException(
                detail="Amount must be positive",
                code="INVALID_AMOUNT",
                status_code=400,
            )

        invoice = self.invoice_repository.get_by_id_for_update(self.invoice_id)
        if not invoice:
            raise NotFoundError(
                detail="Invoice not found",
                code="INVOICE_NOT_FOUND",
            )

        if invoice.status != InvoiceStatus.CREDIT:
            raise BaseAPIException(
                detail="Invoice is not in CREDIT status. Only credit invoices can receive payments.",
                code="INVOICE_NOT_CREDIT",
                status_code=400,
            )

        credit = self.credit_repository.get_by_id_for_update(self.invoice_id)

        if not credit:
            raise NotFoundError(
                detail="No credit found for this invoice",
                code="CREDIT_NOT_FOUND",
            )

        if credit.status in [CreditStatus.SETTLED, CreditStatus.CANCELLED]:
            raise BaseAPIException(
                detail=f"Credit is {credit.status.value} and cannot receive payments",
                code="CREDIT_NOT_ACTIVE",
                status_code=400,
            )

        remaining_debt = invoice.remaining_amount
        credit_remaining = credit.remaining_amount

        amount_to_apply = min(dto.amount, remaining_debt, credit_remaining)
        amount_to_apply = amount_to_apply.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        refund_amount = Decimal("0.00")
        if dto.amount > remaining_debt:
            refund_amount = dto.amount - remaining_debt
            refund_amount = refund_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        old_advance_paid = invoice.advance_paid
        old_remaining = invoice.remaining_amount
        old_status = invoice.status.value

        invoice.advance_paid += amount_to_apply
        invoice.remaining_amount = invoice.get_remaining_amount()

        if invoice.remaining_amount <= Decimal("0.00"):
            invoice.status = InvoiceStatus.COMPLETED
            invoice.is_credit_settled = True
            invoice.remaining_amount = Decimal("0.00")

        invoice.updated_at = timezone.now()
        invoice = self.invoice_repository.update(invoice)

        credit.paid_amount += amount_to_apply
        credit.remaining_amount -= amount_to_apply
        if credit.remaining_amount < Decimal("0.00"):
            credit.remaining_amount = Decimal("0.00")
        credit.updated_at = timezone.now()
        credit.update_status()
        self.credit_repository.update(credit)

        payment = InvoicePayment(
            id=uuid4(),
            invoice_id=invoice.id,
            amount=amount_to_apply,
            payment_method=PaymentMethod(dto.payment_method),
            change_amount=refund_amount,
            refund_amount=Decimal("0.00"),
            payment_date=timezone.now(),
            notes=f"Credit payment applied. Amount: {amount_to_apply}"
            + (f", Refund: {refund_amount}" if refund_amount > Decimal("0.00") else ""),
            idempotency_key=None,
            created_at=timezone.now(),
            updated_at=timezone.now(),
            created_by=self.user_id,
        )
        self.invoice_payment_repository.create(payment)

        log_data = InvoiceLoggingService.create_log(
            invoice_id=invoice.id,
            action=InvoiceLogAction.CREDIT_APPLIED,
            old_value=f"status={old_status}, advance_paid={old_advance_paid}, remaining={old_remaining}",
            new_value=f"status={invoice.status.value}, advance_paid={invoice.advance_paid}, remaining={invoice.remaining_amount}",
            description=f"Credit payment applied. Amount: {amount_to_apply}"
            + (f", Refund: {refund_amount}" if refund_amount > Decimal("0.00") else ""),
            user_id=self.user_id,
        )
        _create_and_save_invoice_log(
            log_data=log_data,
            invoice_id=invoice.id,
            invoice_log_repository=self.invoice_log_repository,
        )

        lines = self.invoice_line_repository.get_by_invoice(self.invoice_id)
        return self._to_dto(invoice, lines)

    def _to_dto(self, invoice: Invoice, lines: list[InvoiceLine]) -> InvoiceResponseDTO:
        """Convert invoice entity to DTO."""
        return _invoice_to_dto(
            invoice=invoice,
            lines=lines,
            user_repository=self.user_repository,
            product_repository=self.product_repository,
        )


class ListPaymentsUseCase:
    """Use case for listing invoice payments for a business."""

    def __init__(
        self,
        invoice_payment_repository: InvoicePaymentRepository,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
        user_repository: UserRepository | None = None,
    ) -> None:
        """Initialize use case."""
        self.invoice_payment_repository = invoice_payment_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id
        self.start_date = start_date
        self.end_date = end_date
        self.limit = limit
        self.user_repository = user_repository

    def execute(self) -> list[PaymentResponseDTO]:
        """Execute payment listing with owner/manager restriction."""
        if not self.business_domain_service.can_user_manage_members(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="Only managers or owners can view payments",
                code="PERMISSION_DENIED",
            )

        payments = self.invoice_payment_repository.get_by_business(
            business_id=self.business_id,
            start_date=self.start_date,
            end_date=self.end_date,
            limit=self.limit,
        )
        return [_payment_to_response_dto(payment, self.user_repository) for payment in payments]


class SearchProductsForSaleUseCase:
    """Use case for searching products for sale (POS)."""

    def __init__(
        self,
        product_repository: ProductRepository,
        business_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.product_repository = product_repository
        self.business_id = business_id

    def execute(self, query: str, limit: int = 20) -> list[ProductSearchResponseDTO]:
        """Execute product search."""
        products = self.product_repository.get_by_business(business_id=self.business_id)

        query_lower = query.lower()
        filtered_products = []
        for product in products:
            if (
                query_lower in product.name.lower()
                or (product.barcode and query_lower in product.barcode.lower())
            ) and product.quantity > 0:
                filtered_products.append(product)

        filtered_products.sort(
            key=lambda p: (
                (
                    0
                    if query_lower == p.name.lower() or query_lower == (p.barcode or "").lower()
                    else 1
                ),
                p.name.lower(),
            )
        )

        filtered_products = filtered_products[:limit]

        return [
            ProductSearchResponseDTO(
                id=product.id,
                name=product.name,
                barcode=product.barcode,
                unit_price=product.get_current_price(),
                promo_price=product.promo_price,
                quantity=product.quantity,
                category_name=None,
                subcategory_name=None,
            )
            for product in filtered_products
        ]


class ScanBarcodeForSaleUseCase:
    """Use case for scanning barcode to get product for sale."""

    def __init__(
        self,
        product_repository: ProductRepository,
        business_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.product_repository = product_repository
        self.business_id = business_id

    def execute(self, barcode: str) -> BarcodeScanResponseDTO:
        """Execute barcode scan."""
        product = self.product_repository.get_by_barcode(
            barcode=barcode, business_id=self.business_id
        )

        if not product:
            raise NotFoundError(
                detail=f"Product with barcode {barcode} not found",
                code="PRODUCT_NOT_FOUND",
            )

        if product.business_id != self.business_id:
            raise ForbiddenError(
                detail="Product does not belong to this business",
                code="PRODUCT_BUSINESS_MISMATCH",
            )

        return BarcodeScanResponseDTO(
            id=product.id,
            name=product.name,
            barcode=product.barcode or "",
            unit_price=product.get_current_price(),
            promo_price=product.promo_price,
            quantity=product.quantity,
            category_name=None,
            subcategory_name=None,
            is_available=product.quantity > 0,
        )


class GenerateInvoiceReceiptUseCase:
    """Use case for generating invoice receipt with QR code."""

    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        invoice_line_repository: InvoiceLineRepository,
        business_repository: BusinessRepository,
        product_repository: ProductRepository,
        user_repository: UserRepository,
        business_domain_service: BusinessDomainService,
        invoice_id: UUID,
        business_id: UUID,
        user_id: UUID,
        format: str = "html",
    ) -> None:
        """Initialize use case."""
        self.invoice_repository = invoice_repository
        self.invoice_line_repository = invoice_line_repository
        self.business_repository = business_repository
        self.product_repository = product_repository
        self.user_repository = user_repository
        self.business_domain_service = business_domain_service
        self.invoice_id = invoice_id
        self.business_id = business_id
        self.user_id = user_id
        self.format = format.lower()

    def execute(self) -> ReceiptResponseDTO:
        """Execute receipt generation."""
        validate_business_access(
            business_domain_service=self.business_domain_service,
            business_id=self.business_id,
            user_id=self.user_id,
        )

        invoice = self.invoice_repository.get_by_id(self.invoice_id)
        validate_entity_belongs_to_business(
            entity=invoice,
            business_id=self.business_id,
            entity_name="Invoice",
        )

        invoice_lines = self.invoice_line_repository.get_by_invoice(self.invoice_id)

        business = self.business_repository.get_by_id(self.business_id)
        if not business:
            raise NotFoundError(
                detail="Business not found",
                code="BUSINESS_NOT_FOUND",
            )

        business_qr_code_url = business.qr_code_url
        if business_qr_code_url:
            try:
                s3 = S3Service()
                business_qr_code_url = (
                    s3.generate_presigned_get_url(business_qr_code_url, expires_in=86400)
                    or business_qr_code_url
                )
            except Exception:
                pass

        invoice_lines_with_names = []
        for line in invoice_lines:
            product = self.product_repository.get_by_id(line.product_id)
            product_name = product.name if product else f"Product {line.product_id}"
            line_dict = {
                "product_name": product_name,
                "quantity": line.quantity,
                "unit_price": line.unit_price,
                "discount": line.discount,
                "line_total": line.line_total,
            }
            invoice_lines_with_names.append(line_dict)

        cashier_name = "Cashier"
        if invoice.cashier_id:
            cashier = self.user_repository.get_by_id(invoice.cashier_id)
            if cashier:
                cashier_name = cashier.name or cashier.email or "Cashier"

        receipt_data = ReceiptGenerationService.prepare_receipt_data(
            invoice=invoice,
            invoice_lines=invoice_lines_with_names,
            business_name=business.name,
            business_qr_code_url=business_qr_code_url,
            business_address=business.address,
            business_phone=business.phone_number,
            business_email=business.email,
            cashier_name=cashier_name,
        )

        receipt_html = render_to_string(
            "receipts/invoice_receipt.html",
            receipt_data,
        )

        receipt_pdf = None
        if self.format == "pdf":
            try:
                receipt_pdf = ReceiptGenerationService.generate_pdf_receipt(
                    receipt_data=receipt_data
                )
                receipt_html = None
            except Exception as e:
                logger.error(f"Error generating PDF receipt: {str(e)}")
                raise BaseAPIException(
                    detail=f"Failed to generate PDF receipt: {str(e)}",
                    code="PDF_GENERATION_ERROR",
                    status_code=500,
                ) from e

        return ReceiptResponseDTO(
            invoice_id=invoice.id,
            invoice_number=invoice.number,
            receipt_html=receipt_html if self.format == "html" else None,
            receipt_pdf=receipt_pdf,
            qr_code_url=business_qr_code_url,
            format=self.format,
        )


class GenerateSalesReportUseCase:
    """Use case for generating sales report with period filtering."""

    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        invoice_line_repository: InvoiceLineRepository,
        product_repository: ProductRepository,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> None:
        """Initialize use case."""
        self.invoice_repository = invoice_repository
        self.invoice_line_repository = invoice_line_repository
        self.product_repository = product_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id
        self.start_date = start_date
        self.end_date = end_date

    @transaction.atomic
    def execute(self) -> SalesReportDTO:
        """Execute sales report generation."""
        validate_business_access(
            business_domain_service=self.business_domain_service,
            business_id=self.business_id,
            user_id=self.user_id,
        )

        start_date, end_date = DateRangeValidationService.validate_date_range(
            start_date=self.start_date,
            end_date=self.end_date,
            allow_future=False,
        )

        if hasattr(self.invoice_repository, "get_sales_aggregations_for_report"):
            aggregations = self.invoice_repository.get_sales_aggregations_for_report(
                business_id=self.business_id,
                start_date=start_date,
                end_date=end_date,
            )

            sales_by_payment_method_dtos = [
                SalesByPaymentMethodDTO(
                    payment_method=item["payment_method"],
                    total_amount=Decimal(str(item["total_amount"])),
                    number_of_invoices=item["invoice_count"],
                )
                for item in aggregations["payment_method_stats"]
            ]

            sales_by_status_dtos = [
                SalesByStatusDTO(
                    status=item["status"],
                    total_amount=Decimal(str(item["total_amount"])),
                    number_of_invoices=item["invoice_count"],
                )
                for item in aggregations["status_stats"]
            ]

            product_stats_list = list(aggregations["product_stats"])
            top_products = []
            for item in product_stats_list:
                product_id = item.get("product_id")
                if product_id is None:
                    continue

                top_products.append(
                    TopProductReportDTO(
                        product_id=product_id,
                        product_name=item.get("product__name") or f"Product {product_id}",
                        total_quantity_sold=item.get("total_quantity_sold", 0),
                        total_revenue=Decimal(str(item.get("total_revenue", 0))),
                        number_of_sales=item.get("number_of_sales", 0),
                    )
                )

            customer_stats_list = list(aggregations["customer_stats"])
            top_customers = []
            for item in customer_stats_list:
                customer_id = item.get("customer_id")
                top_customers.append(
                    TopCustomerReportDTO(
                        customer_id=customer_id,
                        customer_name=item.get("customer_name") or "Walk-in Customer",
                        total_purchases=Decimal(str(item.get("total_purchases", 0))),
                        number_of_invoices=item.get("number_of_invoices", 0),
                    )
                )

            average_invoice_value = (
                aggregations["total_revenue"] / aggregations["total_invoices"]
                if aggregations["total_invoices"] > 0
                else Decimal("0.00")
            )

            return SalesReportDTO(
                business_id=self.business_id,
                period_start=start_date,
                period_end=end_date,
                total_revenue=aggregations["total_revenue"],
                total_invoices=aggregations["total_invoices"],
                total_items_sold=aggregations["total_items_sold"],
                average_invoice_value=average_invoice_value,
                sales_by_payment_method=sales_by_payment_method_dtos,
                sales_by_status=sales_by_status_dtos,
                top_products=top_products,
                top_customers=top_customers,
                generated_at=timezone.now(),
            )

        invoices = self.invoice_repository.get_by_business(
            business_id=self.business_id,
            status=None,
            start_date=start_date,
            end_date=end_date,
            limit=10000,
        )

        total_revenue = Decimal("0.00")
        total_invoices = len(invoices)
        total_items_sold = 0
        sales_by_payment_method: dict[str, dict[str, Decimal | int]] = {}
        sales_by_status: dict[str, dict[str, Decimal | int]] = {}
        product_sales: dict[UUID, dict[str, Any]] = {}
        customer_sales: dict[UUID | None, dict[str, Any]] = {}

        for invoice in invoices:
            total_revenue += invoice.total

            payment_method = invoice.payment_method.value
            if payment_method not in sales_by_payment_method:
                sales_by_payment_method[payment_method] = {
                    "total_amount": Decimal("0.00"),
                    "number_of_invoices": 0,
                }
            sales_by_payment_method[payment_method]["total_amount"] += invoice.total
            sales_by_payment_method[payment_method]["number_of_invoices"] += 1

            status = invoice.status.value
            if status not in sales_by_status:
                sales_by_status[status] = {
                    "total_amount": Decimal("0.00"),
                    "number_of_invoices": 0,
                }
            sales_by_status[status]["total_amount"] += invoice.total
            sales_by_status[status]["number_of_invoices"] += 1

            customer_id = invoice.customer_id
            customer_name = invoice.customer_name or "Walk-in Customer"
            if customer_id not in customer_sales:
                customer_sales[customer_id] = {
                    "customer_id": customer_id,
                    "customer_name": customer_name,
                    "total_purchases": Decimal("0.00"),
                    "number_of_invoices": 0,
                }
            customer_sales[customer_id]["total_purchases"] += invoice.total
            customer_sales[customer_id]["number_of_invoices"] += 1

            invoice_lines = self.invoice_line_repository.get_by_invoice(invoice.id)
            for line in invoice_lines:
                total_items_sold += line.quantity

                if line.product_id not in product_sales:
                    product = self.product_repository.get_by_id(line.product_id)
                    product_name = product.name if product else f"Product {line.product_id}"
                    product_sales[line.product_id] = {
                        "product_id": line.product_id,
                        "product_name": product_name,
                        "total_quantity_sold": 0,
                        "total_revenue": Decimal("0.00"),
                        "number_of_sales": 0,
                    }
                product_sales[line.product_id]["total_quantity_sold"] += line.quantity
                product_sales[line.product_id]["total_revenue"] += line.line_total
                product_sales[line.product_id]["number_of_sales"] += 1

        average_invoice_value = (
            total_revenue / total_invoices if total_invoices > 0 else Decimal("0.00")
        )

        sales_by_payment_method_dtos = [
            SalesByPaymentMethodDTO(
                payment_method=method,
                total_amount=data["total_amount"],
                number_of_invoices=data["number_of_invoices"],
            )
            for method, data in sales_by_payment_method.items()
        ]

        sales_by_status_dtos = [
            SalesByStatusDTO(
                status=status,
                total_amount=data["total_amount"],
                number_of_invoices=data["number_of_invoices"],
            )
            for status, data in sales_by_status.items()
        ]

        top_products = sorted(
            [
                TopProductReportDTO(
                    product_id=product_id,
                    product_name=data.get("product_name", ""),
                    total_quantity_sold=data.get("total_quantity_sold", 0),
                    total_revenue=data.get("total_revenue", Decimal("0.00")),
                    number_of_sales=data.get("number_of_sales", 0),
                )
                for data in product_sales.values()
                if (product_id := data.get("product_id")) is not None
            ],
            key=lambda x: x.total_revenue,
            reverse=True,
        )[:10]

        top_customers = sorted(
            [
                TopCustomerReportDTO(
                    customer_id=data.get("customer_id"),
                    customer_name=data.get("customer_name", "Walk-in Customer"),
                    total_purchases=data.get("total_purchases", Decimal("0.00")),
                    number_of_invoices=data.get("number_of_invoices", 0),
                )
                for data in customer_sales.values()
            ],
            key=lambda x: x.total_purchases,
            reverse=True,
        )[:10]

        return SalesReportDTO(
            business_id=self.business_id,
            period_start=start_date,
            period_end=end_date,
            total_revenue=total_revenue,
            total_invoices=total_invoices,
            total_items_sold=total_items_sold,
            average_invoice_value=average_invoice_value,
            sales_by_payment_method=sales_by_payment_method_dtos,
            sales_by_status=sales_by_status_dtos,
            top_products=top_products,
            top_customers=top_customers,
            generated_at=timezone.now(),
        )
