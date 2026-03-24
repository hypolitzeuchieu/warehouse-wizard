"""Sales domain services for invoice calculations."""

from __future__ import annotations

import io
import logging
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, TypedDict
from uuid import UUID

from django.template.loader import render_to_string
from django.utils import timezone

from domain.sales.entities import Invoice, InvoiceLine, InvoiceLogAction

logger = logging.getLogger(__name__)

try:
    from weasyprint import HTML

    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
    logger.warning("WeasyPrint not available. PDF generation will not work.")


class PaymentProcessingResult(TypedDict):
    amount_applied: Decimal
    change_amount: Decimal
    new_paid: Decimal
    new_remaining: Decimal
    is_fully_paid: bool


class InvoiceCalculationService:
    """Service for invoice calculations with validation and logging."""

    @staticmethod
    def calculate_line_total(
        unit_price: Decimal,
        quantity: int,
        discount: Decimal = Decimal("0.00"),
    ) -> Decimal:
        """
        Calculate line total for an invoice line.

        Formula: (unit_price * quantity) - discount

        Args:
            unit_price: Price per unit
            quantity: Quantity of items
            discount: Discount amount (default: 0.00)

        Returns:
            Line total amount

        Raises:
            ValueError: If any value is negative or invalid
        """
        # Validation
        if unit_price < 0:
            raise ValueError("Unit price cannot be negative")
        if quantity < 0:
            raise ValueError("Quantity cannot be negative")
        if discount < 0:
            raise ValueError("Discount cannot be negative")

        # Calculate
        subtotal = unit_price * quantity
        if discount > subtotal:
            raise ValueError(f"Discount ({discount}) cannot exceed line subtotal ({subtotal})")

        line_total = subtotal - discount

        # Round to 2 decimal places
        line_total = line_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        logger.debug(
            f"Line total calculated: unit_price={unit_price}, quantity={quantity}, "
            f"discount={discount}, line_total={line_total}"
        )

        return line_total

    @staticmethod
    def calculate_subtotal(lines: list[InvoiceLine | dict[str, Any]]) -> Decimal:
        """
        Calculate subtotal from invoice lines.

        Args:
            lines: List of InvoiceLine entities or dicts with 'line_total' key

        Returns:
            Subtotal amount
        """
        subtotal = Decimal("0.00")

        for line in lines:
            if isinstance(line, InvoiceLine):
                line_total = line.line_total
            elif isinstance(line, dict):
                line_total = Decimal(str(line.get("line_total", 0)))
            else:
                raise ValueError(f"Invalid line type: {type(line)}")

            if line_total < 0:
                raise ValueError(f"Line total cannot be negative: {line_total}")

            subtotal += line_total

        # Round to 2 decimal places
        subtotal = subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        logger.debug(f"Subtotal calculated: {subtotal} from {len(lines)} lines")
        return subtotal

    @staticmethod
    def calculate_tax(
        subtotal: Decimal,
        tax_rate: Decimal | None = None,
        tax_amount: Decimal | None = None,
    ) -> Decimal:
        """
        Calculate tax amount.

        Either tax_rate (percentage) or tax_amount (fixed) can be provided.
        If both are provided, tax_amount takes precedence.

        Args:
            subtotal: Subtotal amount
            tax_rate: Tax rate as percentage (e.g., 18.0 for 18%)
            tax_amount: Fixed tax amount

        Returns:
            Tax amount

        Raises:
            ValueError: If both tax_rate and tax_amount are None, or if values are invalid
        """
        if tax_amount is not None:
            if tax_amount < 0:
                raise ValueError("Tax amount cannot be negative")
            tax = tax_amount
        elif tax_rate is not None:
            if tax_rate < 0 or tax_rate > 100:
                raise ValueError(f"Tax rate must be between 0 and 100, got {tax_rate}")
            tax = subtotal * (tax_rate / Decimal("100.00"))
        else:
            tax = Decimal("0.00")

        # Round to 2 decimal places
        tax = tax.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        logger.debug(
            f"Tax calculated: subtotal={subtotal}, tax_rate={tax_rate}, "
            f"tax_amount={tax_amount}, result={tax}"
        )

        return tax

    @staticmethod
    def calculate_final_total(
        subtotal: Decimal,
        tax: Decimal = Decimal("0.00"),
        discount: Decimal = Decimal("0.00"),
    ) -> Decimal:
        """
        Calculate final total for invoice.

        Formula: subtotal + tax - discount

        Args:
            subtotal: Subtotal amount
            tax: Tax amount
            discount: Discount amount

        Returns:
            Final total amount

        Raises:
            ValueError: If discount exceeds subtotal + tax
        """
        # Validation
        if subtotal < 0:
            raise ValueError("Subtotal cannot be negative")
        if tax < 0:
            raise ValueError("Tax cannot be negative")
        if discount < 0:
            raise ValueError("Discount cannot be negative")

        total_before_discount = subtotal + tax
        if discount > total_before_discount:
            raise ValueError(
                f"Discount ({discount}) cannot exceed total before discount ({total_before_discount})"
            )

        final_total = total_before_discount - discount

        # Round to 2 decimal places
        final_total = final_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        logger.info(
            f"Final total calculated: subtotal={subtotal}, tax={tax}, "
            f"discount={discount}, final_total={final_total}"
        )

        return final_total

    @staticmethod
    def validate_invoice_calculations(invoice: Invoice, lines: list[InvoiceLine]) -> dict[str, Any]:
        """
        Validate all calculations for an invoice.

        Recalculates all values and compares with stored values.

        Args:
            invoice: Invoice entity
            lines: List of invoice lines

        Returns:
            Dictionary with validation results:
            - is_valid: bool
            - discrepancies: list of discrepancies found
            - recalculated_values: dict with recalculated values
        """
        discrepancies = []
        recalculated_values = {}

        recalculated_subtotal = InvoiceCalculationService.calculate_subtotal(lines)
        recalculated_values["subtotal"] = recalculated_subtotal

        recalculated_tax = invoice.tax
        recalculated_values["tax"] = recalculated_tax

        recalculated_total = InvoiceCalculationService.calculate_final_total(
            subtotal=recalculated_subtotal,
            tax=recalculated_tax,
            discount=invoice.total_discount,
        )
        recalculated_values["total"] = recalculated_total

        for line in lines:
            recalculated_line_total = InvoiceCalculationService.calculate_line_total(
                unit_price=line.unit_price,
                quantity=line.quantity,
                discount=line.discount,
            )
            if abs(recalculated_line_total - line.line_total) > Decimal("0.01"):
                discrepancies.append(
                    {
                        "type": "line_total_mismatch",
                        "line_id": str(line.id),
                        "stored": str(line.line_total),
                        "recalculated": str(recalculated_line_total),
                    }
                )

        if abs(recalculated_total - invoice.total) > Decimal("0.01"):
            discrepancies.append(
                {
                    "type": "total_mismatch",
                    "stored": str(invoice.total),
                    "recalculated": str(recalculated_total),
                }
            )

        if invoice.status.value == "CREDIT":
            recalculated_remaining = invoice.get_remaining_amount()
            if abs(recalculated_remaining - invoice.remaining_amount) > Decimal("0.01"):
                discrepancies.append(
                    {
                        "type": "remaining_amount_mismatch",
                        "stored": str(invoice.remaining_amount),
                        "recalculated": str(recalculated_remaining),
                    }
                )

        is_valid = len(discrepancies) == 0

        logger.info(
            f"Invoice {invoice.number} validation: is_valid={is_valid}, "
            f"discrepancies={len(discrepancies)}"
        )

        return {
            "is_valid": is_valid,
            "discrepancies": discrepancies,
            "recalculated_values": recalculated_values,
        }

    @staticmethod
    def calculate_invoice_summary(
        lines: list[InvoiceLine | dict[str, Any]],
        tax: Decimal = Decimal("0.00"),
        discount: Decimal = Decimal("0.00"),
    ) -> dict[str, Decimal]:
        """
        Calculate complete invoice summary.

        Args:
            lines: List of invoice lines
            tax: Tax amount
            discount: Discount amount

        Returns:
            Dictionary with:
            - subtotal: Subtotal from lines
            - tax: Tax amount
            - discount: Discount amount
            - total: Final total
        """
        subtotal = InvoiceCalculationService.calculate_subtotal(lines)
        final_total = InvoiceCalculationService.calculate_final_total(
            subtotal=subtotal, tax=tax, discount=discount
        )

        return {
            "subtotal": subtotal,
            "tax": tax,
            "discount": discount,
            "total": final_total,
        }


class WholesalePricingService:
    """Service for calculating wholesale prices."""

    DEFAULT_WHOLESALE_DISCOUNT = Decimal("0.00")

    @staticmethod
    def calculate_wholesale_price(
        regular_price: Decimal,
        discount_amount: Decimal | None = None,
    ) -> Decimal:
        """
        Calculate wholesale price from regular price.

        Args:
            regular_price: Regular price for the product
            discount_amount: Wholesale discount amount in currency (default: 0.00)

        Returns:
            Wholesale price
        """
        if regular_price <= 0:
            raise ValueError("Regular price must be greater than zero")

        discount = discount_amount or WholesalePricingService.DEFAULT_WHOLESALE_DISCOUNT

        if discount < 0:
            raise ValueError(f"Discount amount cannot be negative, got {discount}")

        if discount > regular_price:
            raise ValueError(
                f"Discount amount ({discount}) cannot exceed regular price ({regular_price})"
            )

        wholesale_price = regular_price - discount
        wholesale_price = wholesale_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if wholesale_price < Decimal("0.00"):
            wholesale_price = Decimal("0.00")

        logger.debug(
            f"Wholesale price calculated: regular={regular_price}, "
            f"discount={discount} (amount), wholesale={wholesale_price}"
        )

        return wholesale_price

    @staticmethod
    def get_price_for_customer(
        regular_price: Decimal,
        is_wholesaler: bool,
        wholesale_discount: Decimal | None = None,
    ) -> Decimal:
        """
        Get price for a customer based on their type.

        Args:
            regular_price: Regular price for the product
            is_wholesaler: Whether the customer is a wholesaler
            wholesale_discount: Wholesale discount amount in currency (optional)

        Returns:
            Price for the customer
        """
        if is_wholesaler:
            return WholesalePricingService.calculate_wholesale_price(
                regular_price=regular_price,
                discount_amount=wholesale_discount,
            )
        return regular_price


class InvoiceIntegrityService:
    """Service for validating invoice financial integrity."""

    @staticmethod
    def validate_invoice_integrity(invoice: Invoice) -> None:
        """
        Validate invoice financial integrity.

        Raises:
            ValueError: If invoice has invalid financial data
        """
        errors = []

        # Validate advance_paid
        if invoice.advance_paid < Decimal("0.00"):
            errors.append("advance_paid cannot be negative")

        # Validate remaining_amount
        if invoice.remaining_amount < Decimal("0.00"):
            errors.append("remaining_amount cannot be negative")

        # Validate remaining_amount calculation
        if invoice.advance_paid >= invoice.total:
            expected_remaining = Decimal("0.00")
        else:
            expected_remaining = invoice.total - invoice.advance_paid

        expected_remaining = expected_remaining.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Allow small rounding differences (0.01)
        difference = abs(invoice.remaining_amount - expected_remaining)
        if difference > Decimal("0.01"):
            errors.append(
                f"remaining_amount calculation mismatch: "
                f"expected {expected_remaining}, got {invoice.remaining_amount} "
                f"(total={invoice.total}, advance_paid={invoice.advance_paid})"
            )

        # Validate total
        if invoice.total < Decimal("0.00"):
            errors.append("total cannot be negative")

        if errors:
            error_msg = "; ".join(errors)
            logger.error(
                f"Invoice integrity validation failed for invoice {invoice.id}: {error_msg}"
            )
            raise ValueError(f"Invoice integrity validation failed: {error_msg}")


class PaymentValidationService:
    """Service for validating payment scenarios."""

    @staticmethod
    def validate_payment_amount(
        payment_amount: Decimal,
        invoice_total: Decimal,
        already_paid: Decimal = Decimal("0.00"),
    ) -> dict[str, Any]:
        """
        Validate payment amount against invoice.

        Args:
            payment_amount: Amount being paid
            invoice_total: Total invoice amount
            already_paid: Amount already paid (for partial payments)

        Returns:
            Dictionary with validation results:
            - is_valid: bool
            - remaining_amount: Decimal
            - change_amount: Decimal (if overpayment)
            - errors: list of error messages
        """
        errors = []
        remaining_amount = invoice_total - already_paid
        change_amount = Decimal("0.00")

        # Validation
        if payment_amount <= 0:
            errors.append("Payment amount must be greater than zero")

        if payment_amount > remaining_amount:
            # Overpayment - calculate change
            change_amount = payment_amount - remaining_amount
            change_amount = change_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            logger.info(
                f"Overpayment detected: payment={payment_amount}, "
                f"remaining={remaining_amount}, change={change_amount}"
            )

        is_valid = len(errors) == 0

        return {
            "is_valid": is_valid,
            "remaining_amount": remaining_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "change_amount": change_amount,
            "errors": errors,
        }

    @staticmethod
    def validate_refund_amount(
        refund_amount: Decimal,
        invoice_total: Decimal,
        already_paid: Decimal,
    ) -> dict[str, Any]:
        """
        Validate refund amount.

        Args:
            refund_amount: Amount to refund
            invoice_total: Total invoice amount
            already_paid: Amount already paid

        Returns:
            Dictionary with validation results
        """
        errors = []
        max_refund = min(invoice_total, already_paid)

        if refund_amount <= 0:
            errors.append("Refund amount must be greater than zero")

        if refund_amount > max_refund:
            errors.append(
                f"Refund amount ({refund_amount}) cannot exceed "
                f"maximum refundable amount ({max_refund})"
            )

        is_valid = len(errors) == 0

        return {
            "is_valid": is_valid,
            "max_refund": max_refund.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "errors": errors,
        }


class PaymentProcessingService:
    """Service for processing payments with precision."""

    @staticmethod
    def process_payment(
        payment_amount: Decimal,
        invoice_total: Decimal,
        already_paid: Decimal = Decimal("0.00"),
    ) -> PaymentProcessingResult:
        """
        Process a payment and calculate all amounts.

        Handles:
        - Exact payment
        - Partial payment (for credit)
        - Overpayment with change calculation

        Args:
            payment_amount: Amount being paid
            invoice_total: Total invoice amount
            already_paid: Amount already paid

        Returns:
            Dictionary with:
            - amount_applied: Amount applied to invoice
            - change_amount: Amount to return to customer (overpayment)
            - new_remaining: New remaining amount
            - is_fully_paid: Whether invoice is fully paid
        """
        # Validate
        validation = PaymentValidationService.validate_payment_amount(
            payment_amount=payment_amount,
            invoice_total=invoice_total,
            already_paid=already_paid,
        )

        if not validation["is_valid"] and validation["change_amount"] == Decimal("0.00"):
            raise ValueError(f"Payment validation failed: {validation['errors']}")

        remaining_before = invoice_total - already_paid
        remaining_before = remaining_before.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Calculate amounts
        if payment_amount <= remaining_before:
            # Normal payment or partial payment
            amount_applied = payment_amount
            change_amount = Decimal("0.00")
        else:
            # Overpayment
            amount_applied = remaining_before
            change_amount = payment_amount - remaining_before
            change_amount = change_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        new_paid = already_paid + amount_applied
        new_remaining = invoice_total - new_paid
        new_remaining = max(new_remaining, Decimal("0.00"))
        new_remaining = new_remaining.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        is_fully_paid = new_remaining <= Decimal("0.00")

        logger.info(
            f"Payment processed: payment={payment_amount}, applied={amount_applied}, "
            f"change={change_amount}, remaining={new_remaining}, fully_paid={is_fully_paid}"
        )

        return {
            "amount_applied": amount_applied,
            "change_amount": change_amount,
            "new_paid": new_paid,
            "new_remaining": new_remaining,
            "is_fully_paid": is_fully_paid,
        }

    @staticmethod
    def calculate_refund(
        refund_amount: Decimal,
        invoice_total: Decimal,
        already_paid: Decimal,
    ) -> dict[str, Decimal]:
        """
        Calculate refund amounts.

        Args:
            refund_amount: Amount to refund
            invoice_total: Total invoice amount
            already_paid: Amount already paid

        Returns:
            Dictionary with:
            - refund_amount: Actual refund amount (validated)
            - new_paid: New paid amount after refund
            - new_remaining: New remaining amount
        """
        # Validate
        validation = PaymentValidationService.validate_refund_amount(
            refund_amount=refund_amount,
            invoice_total=invoice_total,
            already_paid=already_paid,
        )

        if not validation["is_valid"]:
            raise ValueError(f"Refund validation failed: {validation['errors']}")

        # Ensure refund doesn't exceed max
        max_refund = validation["max_refund"]
        actual_refund = min(refund_amount, max_refund)
        actual_refund = actual_refund.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        new_paid = already_paid - actual_refund
        new_paid = max(new_paid, Decimal("0.00"))
        new_paid = new_paid.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        new_remaining = invoice_total - new_paid
        new_remaining = max(new_remaining, Decimal("0.00"))
        new_remaining = new_remaining.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        logger.info(
            f"Refund calculated: refund={actual_refund}, "
            f"new_paid={new_paid}, new_remaining={new_remaining}"
        )

        return {
            "refund_amount": actual_refund,
            "new_paid": new_paid,
            "new_remaining": new_remaining,
        }


class InvoiceLoggingService:
    """Service for logging invoice actions."""

    @staticmethod
    def create_log(
        invoice_id: UUID,
        action: InvoiceLogAction,
        old_value: str | None = None,
        new_value: str | None = None,
        description: str | None = None,
        user_id: UUID | None = None,
    ) -> dict[str, Any]:
        """
        Create a log entry for an invoice action.

        Args:
            invoice_id: Invoice ID
            action: Action type
            old_value: Old value (JSON string or text)
            new_value: New value (JSON string or text)
            description: Description of the action
            user_id: User who performed the action

        Returns:
            Dictionary with log data
        """
        return {
            "invoice_id": invoice_id,
            "action": action,
            "old_value": old_value,
            "new_value": new_value,
            "description": description,
            "user_id": user_id,
        }


class DateRangeValidationService:
    """Service for validating date ranges securely."""

    @staticmethod
    def validate_date_range(
        start_date: datetime | None,
        end_date: datetime | None,
        allow_future: bool = False,
    ) -> tuple[datetime, datetime]:
        """
        Validate and normalize date range.

        Args:
            start_date: Start date (optional, defaults to 30 days ago)
            end_date: End date (optional, defaults to today)
            allow_future: Allow future dates (default: False)

        Returns:
            Tuple of (validated_start_date, validated_end_date)

        Raises:
            ValueError: If date range is invalid
        """
        now = timezone.now()
        # Default to last 30 days if not provided
        if start_date is None:
            start_date = now - timedelta(days=7)
        if end_date is None:
            end_date = now

        # Normalize to start/end of day
        if isinstance(start_date, datetime):
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        if isinstance(end_date, datetime):
            end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        # Validate start < end
        if start_date > end_date:
            raise ValueError(f"Start date ({start_date}) cannot be after end date ({end_date})")

        if not allow_future:
            today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            if start_date > today_end:
                raise ValueError(f"Start date ({start_date}) cannot be in the future")
            if end_date > today_end:
                raise ValueError(f"End date ({end_date}) cannot be in the future")

        return start_date, end_date


class ReceiptGenerationService:
    """Service for generating invoice receipts with business QR code."""

    @staticmethod
    def prepare_receipt_data(
        invoice: Invoice,
        invoice_lines: list[dict[str, Any] | InvoiceLine],
        business_name: str,
        business_qr_code_url: str | None = None,
        business_logo_url: str | None = None,
        business_address: str | None = None,
        business_phone: str | None = None,
        business_email: str | None = None,
        cashier_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Prepare receipt data for template rendering.

        Args:
            invoice: Invoice entity
            invoice_lines: List of invoice lines
            business_name: Business name
            business_qr_code_url: Business QR code URL (optional)
            business_logo_url: Business logo URL (optional)
            business_address: Business address (optional)
            business_phone: Business phone (optional)
            business_email: Business email (optional)
            cashier_name: Cashier name (optional)

        Returns:
            Dictionary with receipt data
        """
        return {
            "invoice": {
                "id": str(invoice.id),
                "number": invoice.number,
                "customer_name": invoice.customer_name or "Walk-in Customer",
                "status": invoice.status.value,
                "created_at": invoice.created_at,
                "total": invoice.total,
                "tax": invoice.tax,
                "total_discount": invoice.total_discount,
                "advance_paid": invoice.advance_paid,
                "remaining_amount": invoice.remaining_amount,
                "payment_method": invoice.payment_method.value,
                "change_amount": max(
                    Decimal("0.00"),
                    invoice.advance_paid - invoice.total,
                ),
            },
            "business": {
                "name": business_name,
                "address": business_address,
                "phone": business_phone,
                "email": business_email,
                "qr_code_url": business_qr_code_url,
                "logo_url": business_logo_url,
            },
            "cashier": {
                "name": cashier_name or "Cashier",
            },
            "lines": [
                {
                    "product_name": (
                        line["product_name"]
                        if isinstance(line, dict)
                        else f"Product {line.product_id}"
                    ),
                    "quantity": line["quantity"] if isinstance(line, dict) else line.quantity,
                    "unit_price": (
                        line["unit_price"] if isinstance(line, dict) else line.unit_price
                    ),
                    "discount": line["discount"] if isinstance(line, dict) else line.discount,
                    "line_total": (
                        line["line_total"] if isinstance(line, dict) else line.line_total
                    ),
                }
                for line in invoice_lines
            ],
            "generated_at": timezone.now(),
        }

    @staticmethod
    def generate_pdf_receipt(receipt_data: dict[str, Any]) -> bytes:
        """
        Generate PDF receipt from receipt data.

        Args:
            receipt_data: Receipt data dictionary

        Returns:
            PDF file as bytes

        Raises:
            ValueError: If WeasyPrint is not available
        """
        if not WEASYPRINT_AVAILABLE:
            raise ValueError("Generating PDF service unavailable.")

        # Render HTML template
        html_content = render_to_string("receipts/invoice_receipt.html", receipt_data)

        # Convert HTML to PDF
        try:
            pdf_buffer = io.BytesIO()
            HTML(string=html_content).write_pdf(pdf_buffer)
            pdf_buffer.seek(0)
            pdf_bytes = pdf_buffer.read()
            logger.info("PDF receipt generated successfully")
            return pdf_bytes
        except Exception as e:
            logger.error(f"Error generating PDF receipt: {str(e)}")
            raise
