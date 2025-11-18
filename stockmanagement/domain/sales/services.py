"""Sales domain services for invoice calculations."""

from __future__ import annotations

import logging
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from domain.sales.entities import Invoice, InvoiceLine

logger = logging.getLogger(__name__)


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

        # Recalculate subtotal from lines
        recalculated_subtotal = InvoiceCalculationService.calculate_subtotal(lines)
        recalculated_values["subtotal"] = recalculated_subtotal

        # Recalculate tax
        recalculated_tax = invoice.tax  # Tax is provided, not calculated from rate
        recalculated_values["tax"] = recalculated_tax

        # Recalculate final total
        recalculated_total = InvoiceCalculationService.calculate_final_total(
            subtotal=recalculated_subtotal,
            tax=recalculated_tax,
            discount=invoice.discount,
        )
        recalculated_values["total"] = recalculated_total

        # Validate line totals
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

        # Validate invoice total
        if abs(recalculated_total - invoice.total) > Decimal("0.01"):
            discrepancies.append(
                {
                    "type": "total_mismatch",
                    "stored": str(invoice.total),
                    "recalculated": str(recalculated_total),
                }
            )

        # Validate remaining amount for credit invoices
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

    # Default wholesale discount percentage (can be configured per business)
    DEFAULT_WHOLESALE_DISCOUNT = Decimal("10.00")  # 10% discount

    @staticmethod
    def calculate_wholesale_price(
        regular_price: Decimal,
        discount_percentage: Decimal | None = None,
    ) -> Decimal:
        """
        Calculate wholesale price from regular price.

        Args:
            regular_price: Regular price for the product
            discount_percentage: Wholesale discount percentage (default: 10%)

        Returns:
            Wholesale price
        """
        if regular_price <= 0:
            raise ValueError("Regular price must be greater than zero")

        discount = discount_percentage or WholesalePricingService.DEFAULT_WHOLESALE_DISCOUNT

        if discount < 0 or discount > 100:
            raise ValueError(f"Discount percentage must be between 0 and 100, got {discount}")

        wholesale_price = regular_price * (1 - discount / Decimal("100.00"))
        wholesale_price = wholesale_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        logger.debug(
            f"Wholesale price calculated: regular={regular_price}, "
            f"discount={discount}%, wholesale={wholesale_price}"
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
            wholesale_discount: Wholesale discount percentage (optional)

        Returns:
            Price for the customer
        """
        if is_wholesaler:
            return WholesalePricingService.calculate_wholesale_price(
                regular_price=regular_price,
                discount_percentage=wholesale_discount,
            )
        return regular_price
