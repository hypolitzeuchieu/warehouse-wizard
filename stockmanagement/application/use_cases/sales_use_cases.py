"""Sales use cases."""

import logging
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid4

from django.db import transaction
from django.utils import timezone

from application.dto.sales_dto import (
    BarcodeScanResponseDTO,
    CreditApplicationDTO,
    InvoiceCreateDTO,
    InvoiceLineResponseDTO,
    InvoiceResponseDTO,
    InvoiceUpdateDTO,
    PaymentCreateDTO,
    PaymentResponseDTO,
    ProductSearchResponseDTO,
    RefundCreateDTO,
    RefundResponseDTO,
)
from domain.business.services import BusinessDomainService
from domain.credit.entities import Credit, CreditStatus
from domain.credit.repositories import CreditRepository
from domain.customer.entities import Customer, CustomerType
from domain.customer.repositories import CustomerRepository
from domain.inventory.repositories import ProductRepository
from domain.inventory.services import InventoryDomainService
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
    InvoiceCalculationService,
    InvoiceIntegrityService,
    InvoiceLoggingService,
    PaymentProcessingService,
    WholesalePricingService,
)
from shared.exceptions.base import BaseAPIException
from shared.exceptions.specific import (
    ForbiddenError,
    NotFoundError,
)

logger = logging.getLogger(__name__)


class CreateInvoiceUseCase:
    """Use case for creating an invoice (POS)."""

    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        invoice_line_repository: InvoiceLineRepository,
        invoice_log_repository: InvoiceLogRepository,
        invoice_payment_repository: InvoicePaymentRepository,
        product_repository: ProductRepository,
        inventory_domain_service: InventoryDomainService,
        credit_repository: CreditRepository,
        customer_repository: CustomerRepository,
        business_id: UUID,
        cashier_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.invoice_repository = invoice_repository
        self.invoice_line_repository = invoice_line_repository
        self.invoice_log_repository = invoice_log_repository
        self.invoice_payment_repository = invoice_payment_repository
        self.product_repository = product_repository
        self.inventory_domain_service = inventory_domain_service
        self.credit_repository = credit_repository
        self.customer_repository = customer_repository
        self.business_id = business_id
        self.cashier_id = cashier_id

    @transaction.atomic
    def execute(self, dto: InvoiceCreateDTO) -> InvoiceResponseDTO:
        """Execute invoice creation."""
        try:
            # Get next invoice number
            invoice_number = self.invoice_repository.get_next_invoice_number(self.business_id)

            # Calculate totals
            subtotal = Decimal("0.00")
            lines_data = []

            # Handle customer: get existing or create new one
            customer = None
            customer_id = dto.customer_id

            if customer_id:
                # Get existing customer
                customer = self.customer_repository.get_by_id(customer_id)
                if not customer or customer.business_id != self.business_id:
                    raise BaseAPIException(
                        detail=f"Customer {customer_id} not found",
                        code="CUSTOMER_NOT_FOUND",
                        status_code=404,
                    )
            elif dto.customer_name:
                # Create new customer if name is provided
                # Check if customer with same email or phone already exists
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
                    # Use existing customer
                    customer = existing_customer
                    customer_id = customer.id
                else:
                    # Create new customer
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

            for line_dto in dto.lines or []:
                # Get product with lock to prevent race conditions
                product = self.product_repository.get_by_id_for_update(line_dto.product_id)
                if not product or product.business_id != self.business_id:
                    raise BaseAPIException(
                        detail=f"Product {line_dto.product_id} not found",
                        code="PRODUCT_NOT_FOUND",
                        status_code=404,
                    )

                # Check stock availability (with lock, this is safe from race conditions)
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

                # Calculate line total
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

            # Calculate final totals
            subtotal = InvoiceCalculationService.calculate_subtotal(
                [{"line_total": data["line_total"]} for data in lines_data]
            )
            tax_amount = dto.tax or Decimal("0.00")
            advance_paid = dto.advance_paid or Decimal("0.00")

            # Calculate final total (subtotal + tax)
            final_total = subtotal + tax_amount

            # Determine status based on payment method and advance_paid
            if dto.payment_method == "credit":
                status = InvoiceStatus.CREDIT
            elif advance_paid >= final_total:
                # Fully paid
                status = InvoiceStatus.COMPLETED
            elif advance_paid > Decimal("0.00"):
                # Partially paid - use PENDING status
                status = InvoiceStatus.PENDING
            else:
                # Not paid yet (shouldn't happen with cash/card, but handle it)
                status = (
                    InvoiceStatus.COMPLETED
                    if dto.payment_method != "credit"
                    else InvoiceStatus.CREDIT
                )

            # Calculate remaining amount
            remaining_amount = final_total - advance_paid
            if remaining_amount < Decimal("0.00"):
                remaining_amount = Decimal("0.00")

            # Create invoice
            invoice = Invoice(
                id=uuid4(),
                business_id=self.business_id,
                number=invoice_number,
                customer_name=dto.customer_name or (customer.name if customer else None),
                customer_id=customer_id,
                cashier_id=self.cashier_id,
                status=status,
                total=final_total,
                tax=tax_amount,
                discount=Decimal("0.00"),
                advance_paid=advance_paid,
                remaining_amount=(
                    remaining_amount
                    if status in (InvoiceStatus.CREDIT, InvoiceStatus.PENDING)
                    else Decimal("0.00")
                ),
                payment_method=PaymentMethod(dto.payment_method),
                due_date=dto.due_date,
                is_credit_settled=False,
                created_at=timezone.now(),
                updated_at=timezone.now(),
                reason=dto.reason,
            )

            invoice = self.invoice_repository.create(invoice)

            # Validate invoice integrity
            InvoiceIntegrityService.validate_invoice_integrity(invoice)

            # Create invoice lines and update stock
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

                # Update stock (record exit)
                self.inventory_domain_service.record_stock_exit(
                    business_id=self.business_id,
                    product_id=line_data["product"].id,
                    quantity=line_data["line_dto"].quantity,
                    user_id=self.cashier_id,
                    reason=f"Invoice {invoice.number}",
                )

            # Create credit if invoice is credit type
            if status == InvoiceStatus.CREDIT and invoice.customer_id:

                credit = Credit(
                    id=uuid4(),
                    business_id=self.business_id,
                    customer_id=invoice.customer_id,
                    invoice_id=invoice.id,
                    amount=final_total,
                    paid_amount=Decimal("0.00"),
                    remaining_amount=final_total,
                    due_date=dto.due_date or timezone.now(),
                    status=CreditStatus.PENDING,
                    notes=f"Credit created for Invoice {invoice.number}",
                    created_at=timezone.now(),
                    updated_at=timezone.now(),
                    created_by=self.cashier_id,
                )
                credit.update_status()
                self.credit_repository.create(credit)

            # Create payment record if advance_paid > 0
            if advance_paid > Decimal("0.00"):
                # Calculate change amount if overpayment
                change_amount = Decimal("0.00")
                if advance_paid > final_total:
                    change_amount = advance_paid - final_total
                    change_amount = change_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                payment = InvoicePayment(
                    id=uuid4(),
                    invoice_id=invoice.id,
                    amount=advance_paid,
                    payment_method=PaymentMethod(dto.payment_method),
                    change_amount=change_amount,
                    refund_amount=Decimal("0.00"),
                    payment_date=timezone.now(),
                    notes=f"Initial payment for invoice {invoice.number}",
                    idempotency_key=None,
                    created_at=timezone.now(),
                    updated_at=timezone.now(),
                    created_by=self.cashier_id,
                )
                self.invoice_payment_repository.create(payment)

            # Log the creation
            log_data = InvoiceLoggingService.create_log(
                invoice_id=invoice.id,
                action=InvoiceLogAction.CREATED,
                old_value=None,
                new_value=f"status={invoice.status.value}, total={invoice.total}, customer_id={invoice.customer_id}",
                description=f"Invoice {invoice.number} created",
                user_id=self.cashier_id,
            )
            invoice_log = InvoiceLog(
                id=uuid4(),
                invoice_id=invoice.id,
                action=log_data["action"],
                old_value=log_data["old_value"],
                new_value=log_data["new_value"],
                description=log_data["description"],
                created_at=timezone.now(),
                updated_at=timezone.now(),
                created_by=log_data["user_id"],
            )
            self.invoice_log_repository.create(invoice_log)

            return self._to_dto(invoice, invoice_lines)
        except Exception as e:
            logger.error(
                f"Error creating invoice for business {self.business_id}: {e}",
                exc_info=True,
            )
            raise

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


class UpdateInvoiceUseCase:
    """Use case for updating an invoice."""

    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        invoice_line_repository: InvoiceLineRepository,
        invoice_log_repository: InvoiceLogRepository,
        inventory_domain_service: InventoryDomainService,
        invoice_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.invoice_repository = invoice_repository
        self.invoice_line_repository = invoice_line_repository
        self.invoice_log_repository = invoice_log_repository
        self.inventory_domain_service = inventory_domain_service
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

        # Cannot update completed invoices (except for cancellation)
        if invoice.status == InvoiceStatus.COMPLETED and dto.status != "CANCELLED":
            raise BaseAPIException(
                detail="Cannot update a completed invoice",
                code="INVOICE_ALREADY_COMPLETED",
                status_code=400,
            )

        # Store old values for logging
        old_status = invoice.status.value
        old_total = invoice.total
        old_discount = invoice.discount
        old_tax = invoice.tax

        # Update fields
        if dto.status is not None:
            invoice.status = InvoiceStatus(dto.status)

        if dto.tax is not None:
            invoice.tax = dto.tax

        if dto.discount is not None:
            invoice.discount = dto.discount

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

        # Recalculate totals if tax or discount changed
        if dto.tax is not None or dto.discount is not None:
            lines = self.invoice_line_repository.get_by_invoice(self.invoice_id)
            subtotal = InvoiceCalculationService.calculate_subtotal(lines)
            invoice.total = InvoiceCalculationService.calculate_final_total(
                subtotal=subtotal,
                tax=invoice.tax,
                discount=invoice.discount,
            )

        # Update remaining amount for credit invoices
        if invoice.status == InvoiceStatus.CREDIT:
            invoice.remaining_amount = invoice.get_remaining_amount()
        else:
            invoice.remaining_amount = Decimal("0.00")

        invoice.updated_at = timezone.now()
        invoice = self.invoice_repository.update(invoice)

        # Log the update
        log_data = InvoiceLoggingService.create_log(
            invoice_id=invoice.id,
            action=InvoiceLogAction.UPDATED,
            old_value=f"status={old_status}, total={old_total}, discount={old_discount}, tax={old_tax}",
            new_value=f"status={invoice.status.value}, total={invoice.total}, discount={invoice.discount}, tax={invoice.tax}",
            description=f"Invoice updated by user {self.user_id}",
            user_id=self.user_id,
        )
        invoice_log = InvoiceLog(
            id=uuid4(),
            invoice_id=invoice.id,
            action=log_data["action"],
            old_value=log_data["old_value"],
            new_value=log_data["new_value"],
            description=log_data["description"],
            created_at=timezone.now(),
            updated_at=timezone.now(),
            created_by=log_data["user_id"],
        )
        self.invoice_log_repository.create(invoice_log)

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


class PayInvoiceUseCase:
    """Use case for processing a payment on an invoice."""

    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        invoice_line_repository: InvoiceLineRepository,
        invoice_payment_repository: InvoicePaymentRepository,
        invoice_log_repository: InvoiceLogRepository,
        credit_repository: CreditRepository,
        invoice_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.invoice_repository = invoice_repository
        self.invoice_line_repository = invoice_line_repository
        self.invoice_payment_repository = invoice_payment_repository
        self.invoice_log_repository = invoice_log_repository
        self.credit_repository = credit_repository
        self.invoice_id = invoice_id
        self.user_id = user_id

    @transaction.atomic
    def execute(self, dto: PaymentCreateDTO) -> tuple[InvoiceResponseDTO, PaymentResponseDTO]:
        """Execute payment processing."""
        try:
            # Get invoice with lock to prevent race conditions on payments
            invoice = self.invoice_repository.get_by_id_for_update(self.invoice_id)
            if not invoice:
                raise NotFoundError(
                    detail="Invoice not found",
                    code="INVOICE_NOT_FOUND",
                )

            # Check for duplicate payment (idempotency)
            if dto.idempotency_key:
                existing_payment = self.invoice_payment_repository.get_by_idempotency_key(
                    invoice_id=self.invoice_id,
                    idempotency_key=dto.idempotency_key,
                )
                if existing_payment:
                    # Return existing payment (idempotent)
                    logger.info(
                        f"Duplicate payment detected with idempotency_key {dto.idempotency_key}, "
                        f"returning existing payment {existing_payment.id}"
                    )
                    lines = self.invoice_line_repository.get_by_invoice(self.invoice_id)
                    invoice_dto = self._to_invoice_dto(invoice, lines)
                    payment_dto = self._to_payment_dto(existing_payment)
                    return invoice_dto, payment_dto

            # Process payment
            payment_result = PaymentProcessingService.process_payment(
                payment_amount=dto.amount,
                invoice_total=invoice.total,
                already_paid=invoice.advance_paid,
            )

            # Update invoice
            invoice.advance_paid = payment_result["new_paid"]
            invoice.remaining_amount = payment_result["new_remaining"]

            # Update status
            if payment_result["is_fully_paid"]:
                invoice.status = InvoiceStatus.COMPLETED
                invoice.is_credit_settled = True
            elif invoice.status == InvoiceStatus.PENDING:
                invoice.status = InvoiceStatus.CREDIT

            invoice.updated_at = timezone.now()
            invoice = self.invoice_repository.update(invoice)

            # Validate invoice integrity after update
            InvoiceIntegrityService.validate_invoice_integrity(invoice)

            # Create payment record
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

            # Update credit if invoice is linked to a credit
            if invoice.customer_id:
                credits = self.credit_repository.get_by_customer(
                    customer_id=invoice.customer_id,
                    business_id=invoice.business_id,
                )
                # Find credit linked to this invoice
                for credit in credits:
                    if credit.invoice_id == invoice.id:
                        credit.paid_amount += payment_result["amount_applied"]
                        credit.remaining_amount -= payment_result["amount_applied"]
                        credit.updated_at = timezone.now()
                        credit.update_status()
                        self.credit_repository.update(credit)
                        break

            # Log the payment
            log_data = InvoiceLoggingService.create_log(
                invoice_id=invoice.id,
                action=InvoiceLogAction.PAYMENT_RECEIVED,
                old_value=f"advance_paid={invoice.advance_paid - payment_result['amount_applied']}, remaining={invoice.remaining_amount + payment_result['amount_applied']}",
                new_value=f"advance_paid={invoice.advance_paid}, remaining={invoice.remaining_amount}",
                description=f"Payment of {dto.amount} received via {dto.payment_method}. Change: {payment_result['change_amount']}",
                user_id=self.user_id,
            )
            invoice_log = InvoiceLog(
                id=uuid4(),
                invoice_id=invoice.id,
                action=log_data["action"],
                old_value=log_data["old_value"],
                new_value=log_data["new_value"],
                description=log_data["description"],
                created_at=timezone.now(),
                updated_at=timezone.now(),
                created_by=log_data["user_id"],
            )
            self.invoice_log_repository.create(invoice_log)

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

    def _to_payment_dto(self, payment: InvoicePayment) -> PaymentResponseDTO:
        """Convert payment entity to DTO."""
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
        )


class CancelInvoiceUseCase:
    """Use case for cancelling an invoice with stock restoration."""

    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        invoice_line_repository: InvoiceLineRepository,
        invoice_log_repository: InvoiceLogRepository,
        inventory_domain_service: InventoryDomainService,
        credit_repository: CreditRepository,
        invoice_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.invoice_repository = invoice_repository
        self.invoice_line_repository = invoice_line_repository
        self.invoice_log_repository = invoice_log_repository
        self.inventory_domain_service = inventory_domain_service
        self.credit_repository = credit_repository
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

        if invoice.status == InvoiceStatus.CANCELLED:
            raise BaseAPIException(
                detail="Invoice is already cancelled",
                code="INVOICE_ALREADY_CANCELLED",
                status_code=400,
            )

        # Restore stock for all lines
        lines = self.invoice_line_repository.get_by_invoice(self.invoice_id)
        for line in lines:
            self.inventory_domain_service.record_stock_entry(
                business_id=invoice.business_id,
                product_id=line.product_id,
                quantity=line.quantity,
                user_id=self.user_id,
                reason=f"Cancellation of Invoice {invoice.number}",
            )

        # Cancel associated credit if exists
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

        # Update invoice
        old_status = invoice.status.value
        invoice.status = InvoiceStatus.CANCELLED
        invoice.reason = reason or "Invoice cancelled"
        invoice.updated_at = timezone.now()
        invoice = self.invoice_repository.update(invoice)

        # Log the cancellation
        log_data = InvoiceLoggingService.create_log(
            invoice_id=invoice.id,
            action=InvoiceLogAction.CANCELLED,
            old_value=f"status={old_status}",
            new_value=f"status={invoice.status.value}",
            description=f"Invoice cancelled. Reason: {invoice.reason}",
            user_id=self.user_id,
        )
        invoice_log = InvoiceLog(
            id=uuid4(),
            invoice_id=invoice.id,
            action=log_data["action"],
            old_value=log_data["old_value"],
            new_value=log_data["new_value"],
            description=log_data["description"],
            created_at=timezone.now(),
            updated_at=timezone.now(),
            created_by=log_data["user_id"],
        )
        self.invoice_log_repository.create(invoice_log)

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


class ProcessRefundUseCase:
    """Use case for processing a refund on an invoice."""

    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        invoice_payment_repository: InvoicePaymentRepository,
        invoice_line_repository: InvoiceLineRepository,
        invoice_log_repository: InvoiceLogRepository,
        inventory_domain_service: InventoryDomainService,
        invoice_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.invoice_repository = invoice_repository
        self.invoice_payment_repository = invoice_payment_repository
        self.invoice_line_repository = invoice_line_repository
        self.invoice_log_repository = invoice_log_repository
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

        # Calculate refund
        refund_result = PaymentProcessingService.calculate_refund(
            refund_amount=dto.amount,
            invoice_total=invoice.total,
            already_paid=invoice.advance_paid,
        )

        # Update invoice
        invoice.advance_paid = refund_result["new_paid"]
        invoice.remaining_amount = refund_result["new_remaining"]

        # Update status if fully refunded
        if refund_result["new_paid"] <= Decimal("0.00"):
            invoice.status = InvoiceStatus.CANCELLED

        invoice.updated_at = timezone.now()
        invoice = self.invoice_repository.update(invoice)

        # Restore stock if requested
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

        # Create refund payment record
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

        # Log the refund
        log_data = InvoiceLoggingService.create_log(
            invoice_id=invoice.id,
            action=InvoiceLogAction.REFUNDED,
            old_value=f"advance_paid={invoice.advance_paid + refund_result['refund_amount']}, remaining={invoice.remaining_amount - refund_result['refund_amount']}",
            new_value=f"advance_paid={invoice.advance_paid}, remaining={invoice.remaining_amount}",
            description=f"Refund of {refund_result['refund_amount']} processed. Reason: {dto.reason or 'No reason provided'}",
            user_id=self.user_id,
        )
        invoice_log = InvoiceLog(
            id=uuid4(),
            invoice_id=invoice.id,
            action=log_data["action"],
            old_value=log_data["old_value"],
            new_value=log_data["new_value"],
            description=log_data["description"],
            created_at=timezone.now(),
            updated_at=timezone.now(),
            created_by=log_data["user_id"],
        )
        self.invoice_log_repository.create(invoice_log)

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
        # Get the invoice line
        line_to_delete = self.invoice_line_repository.get_by_id(self.line_id)

        if not line_to_delete:
            raise NotFoundError(
                detail="Invoice line not found",
                code="INVOICE_LINE_NOT_FOUND",
            )

        # Get the invoice
        invoice = self.invoice_repository.get_by_id(line_to_delete.invoice_id)

        if not invoice:
            raise NotFoundError(
                detail="Invoice not found",
                code="INVOICE_NOT_FOUND",
            )

        # Cannot delete line from completed invoice
        if invoice.status == InvoiceStatus.COMPLETED:
            raise BaseAPIException(
                detail="Cannot delete line from completed invoice",
                code="INVOICE_ALREADY_COMPLETED",
                status_code=400,
            )

        # Restore stock
        self.inventory_domain_service.record_stock_entry(
            business_id=invoice.business_id,
            product_id=line_to_delete.product_id,
            quantity=line_to_delete.quantity,
            user_id=self.user_id,
            reason=f"Line removed from Invoice {invoice.number}",
        )

        # Delete line
        self.invoice_line_repository.delete(self.line_id)

        # Recalculate totals
        remaining_lines = self.invoice_line_repository.get_by_invoice(invoice.id)
        subtotal = InvoiceCalculationService.calculate_subtotal(remaining_lines)
        invoice.total = InvoiceCalculationService.calculate_final_total(
            subtotal=subtotal,
            tax=invoice.tax,
            discount=invoice.discount,
        )

        # Update remaining amount
        if invoice.status == InvoiceStatus.CREDIT:
            invoice.remaining_amount = invoice.get_remaining_amount()
        else:
            invoice.remaining_amount = Decimal("0.00")

        invoice.updated_at = timezone.now()
        invoice = self.invoice_repository.update(invoice)

        # Log the deletion
        log_data = InvoiceLoggingService.create_log(
            invoice_id=invoice.id,
            action=InvoiceLogAction.LINE_REMOVED,
            old_value=f"line_id={line_to_delete.id}, product_id={line_to_delete.product_id}, quantity={line_to_delete.quantity}",
            new_value="line removed",
            description=f"Line removed from invoice. Product: {line_to_delete.product_id}, Quantity: {line_to_delete.quantity}",
            user_id=self.user_id,
        )
        invoice_log = InvoiceLog(
            id=uuid4(),
            invoice_id=invoice.id,
            action=log_data["action"],
            old_value=log_data["old_value"],
            new_value=log_data["new_value"],
            description=log_data["description"],
            created_at=timezone.now(),
            updated_at=timezone.now(),
            created_by=log_data["user_id"],
        )
        self.invoice_log_repository.create(invoice_log)

        return self._to_dto(invoice, remaining_lines)

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


class ApplyCreditToInvoiceUseCase:
    """Use case for applying a credit to an invoice."""

    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        invoice_line_repository: InvoiceLineRepository,
        invoice_log_repository: InvoiceLogRepository,
        credit_repository: CreditRepository,
        invoice_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.invoice_repository = invoice_repository
        self.invoice_line_repository = invoice_line_repository
        self.invoice_log_repository = invoice_log_repository
        self.credit_repository = credit_repository
        self.invoice_id = invoice_id
        self.user_id = user_id

    @transaction.atomic
    def execute(self, dto: CreditApplicationDTO) -> InvoiceResponseDTO:
        """Execute credit application."""
        invoice = self.invoice_repository.get_by_id(self.invoice_id)
        if not invoice:
            raise NotFoundError(
                detail="Invoice not found",
                code="INVOICE_NOT_FOUND",
            )

        credit = self.credit_repository.get_by_id(dto.credit_id)
        if not credit:
            raise NotFoundError(
                detail="Credit not found",
                code="CREDIT_NOT_FOUND",
            )

        # Validate credit belongs to customer
        if credit.customer_id != invoice.customer_id:
            raise BaseAPIException(
                detail="Credit does not belong to invoice customer",
                code="CREDIT_CUSTOMER_MISMATCH",
                status_code=400,
            )

        # Validate credit is available
        if credit.status == CreditStatus.SETTLED:
            raise BaseAPIException(
                detail="Credit is already fully settled",
                code="CREDIT_ALREADY_SETTLED",
                status_code=400,
            )

        if credit.status == CreditStatus.CANCELLED:
            raise BaseAPIException(
                detail="Credit is cancelled",
                code="CREDIT_CANCELLED",
                status_code=400,
            )

        # Calculate amount to apply
        amount_to_apply = dto.amount or credit.remaining_amount
        amount_to_apply = min(amount_to_apply, credit.remaining_amount, invoice.remaining_amount)
        amount_to_apply = amount_to_apply.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Update invoice
        old_advance_paid = invoice.advance_paid
        invoice.advance_paid += amount_to_apply
        invoice.remaining_amount = invoice.get_remaining_amount()

        if invoice.remaining_amount <= Decimal("0.00"):
            invoice.status = InvoiceStatus.COMPLETED
            invoice.is_credit_settled = True

        invoice.updated_at = timezone.now()
        invoice = self.invoice_repository.update(invoice)

        # Update credit
        credit.paid_amount += amount_to_apply
        credit.remaining_amount -= amount_to_apply
        credit.updated_at = timezone.now()
        credit.update_status()
        self.credit_repository.update(credit)

        # Log the credit application
        log_data = InvoiceLoggingService.create_log(
            invoice_id=invoice.id,
            action=InvoiceLogAction.CREDIT_APPLIED,
            old_value=f"advance_paid={old_advance_paid}, remaining={invoice.remaining_amount + amount_to_apply}",
            new_value=f"advance_paid={invoice.advance_paid}, remaining={invoice.remaining_amount}",
            description=f"Credit {dto.credit_id} applied. Amount: {amount_to_apply}",
            user_id=self.user_id,
        )
        invoice_log = InvoiceLog(
            id=uuid4(),
            invoice_id=invoice.id,
            action=log_data["action"],
            old_value=log_data["old_value"],
            new_value=log_data["new_value"],
            description=log_data["description"],
            created_at=timezone.now(),
            updated_at=timezone.now(),
            created_by=log_data["user_id"],
        )
        self.invoice_log_repository.create(invoice_log)

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
        # Get all products for business
        products = self.product_repository.get_by_business(business_id=self.business_id)

        # Filter by query (name or barcode)
        query_lower = query.lower()
        filtered_products = []
        for product in products:
            if (
                query_lower in product.name.lower()
                or (product.barcode and query_lower in product.barcode.lower())
            ) and product.quantity > 0:  # Only products in stock
                filtered_products.append(product)

        # Sort by relevance (exact match first, then by name)
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

        # Limit results
        filtered_products = filtered_products[:limit]

        return [
            ProductSearchResponseDTO(
                id=product.id,
                name=product.name,
                barcode=product.barcode,
                unit_price=product.get_current_price(),
                promo_price=product.promo_price,
                quantity=product.quantity,
                category_name=None,  # Could be added if needed
                subcategory_name=None,  # Could be added if needed
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
            category_name=None,  # Could be added if needed
            subcategory_name=None,  # Could be added if needed
            is_available=product.quantity > 0,
        )
