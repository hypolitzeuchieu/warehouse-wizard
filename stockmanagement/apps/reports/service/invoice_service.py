from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from apps.authentication.models import User
from apps.notifications.service import NotificationService
from apps.reports.models import Invoice
from apps.reports.models import InvoiceArchive
from apps.reports.models import InvoiceArchiveLine
from apps.reports.service.entities import ServiceResponse
from apps.reports.service.expense_service import TreasureService
from apps.stock.models import Product
from apps.stock.models import StockMovement
from django.db import transaction
from django.template.loader import get_template
from django.utils import timezone
from django.utils.timezone import now
from rest_framework.exceptions import ValidationError
from xhtml2pdf import pisa


logger = logging.getLogger(__name__)


class ReportService:
    """
    Service for handling reports, invoices, and related operations.
    """
    notif_service = NotificationService()

    @staticmethod
    def get_managers_and_store_keepers() -> ServiceResponse:
        try:
            managers = User.objects.filter(role__in=['stock_keeper', 'manager'])
            if not managers.exists():
                return ServiceResponse(success=False, error='No manager found.')
            return ServiceResponse(success=True, data=managers)
        except Exception as e:
            logger.error(f"Error fetching managers: {str(e)}")
            return ServiceResponse(success=False, error=str(e))

    def validate_stock(self, product, quantity) -> ServiceResponse:
        """
        Validate if sufficient stock is available for the given product and quantity.
        """
        if quantity <= 0:
            return ServiceResponse(
                success=False,
                error=f"Invalid quantity: {quantity}. Quantity must be greater than 0."
            )

        if product.quantity < quantity:
            message = (f"Stock is low for {product.name}."
                       f"Available: {product.quantity}, Required: {quantity}")

            self.notif_service.create_notification(
                product=product,
                notification_type='CRITICAL_STOCK',
                message=message,
            )
            return ServiceResponse(success=False, error='Insufficient stock.')
        return ServiceResponse(success=True)

    def update_stock(self, product, quantity, user, reason) -> ServiceResponse:
        """
        Update stock levels after a transaction and log the stock movement.
        """
        stock_validation = self.validate_stock(product, quantity)
        if not stock_validation.success:
            return stock_validation

        try:
            product.quantity -= quantity
            StockMovement.objects.create(
                movement_type='EXIT',
                quantity=-quantity,
                product=product,
                category=product.category,
                subcategory=(
                    product.subcategory if product.subcategory else None
                ),
                user=user,
                reason=reason,
            )
            product.save()

            if product.quantity < product.min_quantity:
                message = (
                    f"Critical stock for {product.name}."
                    f" Available quantity : {product.quantity}"
                )
                self.notif_service.create_notification(
                    product=product,
                    notification_type='CRITICAL_STOCK',
                    message=message,
                )
            return ServiceResponse(success=True)
        except Exception as e:
            logger.error(
                f"Error updating stock for product {product.name}: {e}"
            )
            return ServiceResponse(
                success=False,
                error=f"Failed to update stock for product {product.name}: {str(e)}"
            )

    @staticmethod
    def calculate_invoice_totals(invoice) -> ServiceResponse:
        """
        Calculate the total amount for an invoice, including applicable taxes.
        """
        try:
            lines = invoice.lines.all()
            total = sum(line.line_total for line in lines)

            if invoice.tax is None or invoice.tax < 0:
                invoice.tax = Decimal('0.00')

            tax_amount = (total * Decimal(invoice.tax)) / Decimal('100')
            invoice.total = total + tax_amount

            if invoice.status == 'CREDIT':
                invoice.remaining_amount = invoice.total - invoice.advance_paid
                invoice.is_credit_settled = invoice.remaining_amount <= 0
            else:
                invoice.remaining_amount = Decimal('0.00')

            invoice.save()
            return ServiceResponse(success=True)
        except Exception as e:
            logger.error(
                f"Error calculating invoice totals for invoice {invoice.id}: {e}"
            )
            return ServiceResponse(
                success=False, error=f"calculating invoice totals.: {str(e)}"
            )

    @staticmethod
    def create_invoice(data, user):
        """Create new invoice."""
        try:
            invoice = Invoice.objects.create(
                client_name=data.get('client_name'),
                cashier=user,
                tax=data.get('tax', Decimal('0.00')),
                status=data.get('status'),
                reason=data.get('reason', ''),
                advance_paid=data.get('advance_paid', Decimal('0.00')),
                due_date=data.get('due_date', None),
            )
            return ServiceResponse(success=True, data=invoice)
        except Exception as e:
            transaction.set_rollback(True)
            logger.error(f"Error creating invoice: {e}")
            return ServiceResponse(success=False, error=str(e))

    def process_invoice_lines(self, invoice, lines_data, user) -> ServiceResponse:
        """
        Process invoice lines and update stock.
        """
        total_amount = Decimal('0.00')
        sold_products = []

        for line_data in lines_data:
            quantity = line_data['quantity']

            if 'barcode' in line_data:
                identifier = line_data['barcode']
            else:
                identifier = line_data['product_id']

            try:
                product = Product.objects.get(id=identifier)
            except Product.DoesNotExist:
                return ServiceResponse(
                    success=False, error=f"Product with ID {identifier} does not exist."
                )

            stock_validation = self.validate_stock(product, quantity)
            if not stock_validation.success:
                return stock_validation

            unit_price = product.get_price()
            discount = line_data.get('discount', Decimal('0.00'))
            line_total = (unit_price * quantity) - discount
            total_amount += line_total

            try:
                invoice.lines.create(
                    product=product,
                    quantity=quantity,
                    unit_price=unit_price,
                    discount=discount,
                    line_total=line_total,
                )
            except Exception as e:
                logger.error(f'Error in create invoices lines: {str(e)}')
                transaction.set_rollback(True)
                return ServiceResponse(
                    success=False,
                    error=f'Error in create invoices lines: {str(e)}'
                )

            stock_update_response = self.update_stock(
                product, quantity, user, reason='Sale transaction'
            )
            if not stock_update_response.success:
                return stock_update_response

            sold_products.append((product, quantity))

        return ServiceResponse(success=True, data=(total_amount, sold_products))

    @staticmethod
    def handle_completed_or_credit(invoice) -> ServiceResponse:
        """Handle COMPLETED and CREDIT statuses."""
        try:
            remaining_amount = invoice.total - invoice.advance_paid

            if remaining_amount > Decimal('0.00'):
                invoice.status = 'CREDIT'
                invoice.remaining_amount = remaining_amount
                invoice.is_credit_settled = False

                if not invoice.due_date:
                    invoice.due_date = timezone.now().date() + timedelta(days=30)

                invoice.reason = 'CREDIT Invoice Transaction'
                invoice.refund_amount = Decimal('0.00')

            else:
                invoice.status = 'COMPLETED'
                invoice.remaining_amount = Decimal('0.00')
                invoice.is_credit_settled = True

                invoice.refund_amount = max(
                    invoice.advance_paid - invoice.total, Decimal('0.00')
                )
                if not invoice.reason:
                    invoice.reason = 'COMPLETED Invoice Transaction'

            invoice.save()
            return ServiceResponse(success=True)
        except Exception as e:
            logger.error(f"Error handling invoice status: {e}")
            return ServiceResponse(
                success=False, error=f"Error handling invoice status: {str(e)}"
            )

    @staticmethod
    def handle_cancelled_invoice(invoice, sold_products):
        """Restore stock and cancel a CANCELLED invoice."""
        try:
            for product, quantity in sold_products:
                product.quantity += quantity
                product.save()

            invoice.lines.all().delete()
            invoice.total = Decimal('0.00')
            invoice.remaining_amount = Decimal('0.00')
            invoice.is_credit_settled = False
            invoice.refund_amount = Decimal('0.00')

            return ServiceResponse(success=True)
        except Exception as e:
            logger.error(f"Error handling cancelled invoice: {e}")
            return ServiceResponse(
                success=False, error=f"Error handling cancelled invoice: {str(e)}"
            )

    @staticmethod
    def finalize_invoice(invoice) -> ServiceResponse:
        """Calculate totals."""
        try:
            totals_response = ReportService.calculate_invoice_totals(invoice)
            if not totals_response.success:
                return totals_response

            invoice.save()
            return ServiceResponse(success=True)
        except Exception as e:
            logger.error(f"Error finalizing invoice: {e}")
            return ServiceResponse(
                success=False, error=f"Error finalizing invoice: {str(e)}"
            )

    def validate_invoice_data(self, data) -> ServiceResponse:
        """
        Validate invoice data before processing.
        """
        if not data.get('lines') or len(data['lines']) == 0:
            return ServiceResponse(
                success=False,
                error='Une facture doit avoir au moins une ligne.'
            )

            # Vérification du stock pour tous les produits
        for line_data in data['lines']:
            product_id = line_data['product_id']
            quantity = line_data['quantity']

            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                return ServiceResponse(
                    success=False,
                    error=f"Product with ID {product_id} does not exist."
                )

            stock_validation = self.validate_stock(product, quantity)
            if not stock_validation.success:
                return stock_validation

        return ServiceResponse(success=True)

    def process_invoice(self, data, user) -> ServiceResponse:
        """
        Handle the complete workflow for processing a sale and creating an invoice.
        """
        with transaction.atomic():
            try:
                validation_response = self.validate_invoice_data(data)
                if not validation_response.success:
                    return validation_response

                invoice_response = ReportService.create_invoice(data, user)
                if not invoice_response.success:
                    return invoice_response

                invoice = invoice_response.data
                lines_response = self.process_invoice_lines(invoice, data['lines'], user)
                if not lines_response.success:
                    return lines_response

                total_amount, sold_products = lines_response.data
                invoice.total = total_amount
                invoice.save()

                if invoice.status in ['COMPLETED', 'CREDIT']:
                    status_response = ReportService.handle_completed_or_credit(invoice)
                    if not status_response.success:
                        transaction.set_rollback(True)
                        return status_response
                    ReportService._update_treasure_for_status(invoice)
                elif invoice.status == 'CANCELLED':
                    cancel_response = ReportService.handle_cancelled_invoice(
                        invoice, sold_products
                    )
                    if not cancel_response.success:
                        transaction.set_rollback(True)
                        return cancel_response

                finalize_response = ReportService.finalize_invoice(invoice)
                if not finalize_response.success:
                    transaction.set_rollback(True)
                    return finalize_response

                return ServiceResponse(success=True, data=invoice)

            except ValidationError as e:
                transaction.set_rollback(True)
                return ServiceResponse(success=False, error=str(e))

            except Exception as e:
                transaction.set_rollback(True)
                logger.error(f"Error processing invoice: {e}")
                return ServiceResponse(
                    success=False, error=f"Unexpected error in processing invoice: {str(e)}"
                )

    @staticmethod
    def _update_treasure_for_status(invoice):
        if invoice.status == 'COMPLETED':
            TreasureService.update_balance(
                invoice.total,
                'sale',
                {'invoice_id': str(invoice.id)}
            )
        elif invoice.status == 'CREDIT':
            TreasureService.update_balance(
                invoice.total,
                'credit_sale',
                {'invoice_id': str(invoice.id)}
            )
            if invoice.advance_paid > 0:
                TreasureService.update_balance(
                    invoice.advance_paid,
                    'credit_payment',
                    {'invoice_id': str(invoice.id)}
                )

    @staticmethod
    def export_invoice_to_pdf(invoice_id) -> ServiceResponse:
        """
        Export an invoice to PDF format.
        """
        try:
            invoice = Invoice.objects.prefetch_related('lines').get(id=invoice_id)
            invoice_lines = invoice.lines.all()

            template = get_template('invoice_template.html')
            context = {
                'invoice': invoice,
                'invoice_lines': invoice_lines,
            }
            html = template.render(context)
            pdf_buffer = BytesIO()
            pisa_status = pisa.CreatePDF(html, dest=pdf_buffer)

            if pisa_status.err:
                logger.error(
                    f"Failed to generate PDF for invoice {invoice_id}."
                )
                return ServiceResponse(success=False, error='Failed to generate PDF.')

            pdf_buffer.seek(0)
            logger.info(
                f"PDF generated successfully for invoice {invoice_id}."
            )
            return ServiceResponse(success=True, data=pdf_buffer)

        except Invoice.DoesNotExist:
            logger.error(f"Invoice with ID {invoice_id} does not exist.")
            return ServiceResponse(
                success=False, error=f"Invoice with ID {invoice_id} does not exist."
            )
        except Exception as e:
            logger.error(f"Error in export_invoice_to_pdf: {str(e)}")
            return ServiceResponse(
                success=False, error=f"An unexpected error occurred: {str(e)}"
            )

    @staticmethod
    def pay_debt(invoice_id: str, amount: float) -> ServiceResponse:
        """
        Process payment for an outstanding invoice marked as "CREDIT".
        """
        try:
            invoice = Invoice.objects.get(id=invoice_id)
        except Invoice.DoesNotExist:
            logger.error(
                f"Attempted payment on non-existent invoice (ID: {invoice_id})"
            )
            return ServiceResponse(success=False, error='Invoice not found.')

        if invoice.status != 'CREDIT':
            logger.error(f"Payment attempt on non-credit invoice (ID: {invoice_id})")
            return ServiceResponse(
                success=False, error='Only invoices with CREDIT status can be paid.'
            )

        if amount <= 0:
            logger.error(f"Invalid payment amount: {amount} for invoice ID {invoice_id}")
            return ServiceResponse(
                success=False, error='The payment amount must be greater than zero.'
            )

        remaining_debt = invoice.total - invoice.advance_paid

        if remaining_debt <= 0:
            logger.info(f"Invoice ID {invoice_id} is already fully paid.")
            return ServiceResponse(
                success=False, error='This invoice is already fully paid.'
            )

        try:
            with transaction.atomic():
                effective_payment = min(amount, remaining_debt)
                refund_amount = amount - effective_payment

                invoice.advance_paid += effective_payment
                invoice.remaining_amount = remaining_debt - effective_payment

                if invoice.remaining_amount <= 0:
                    invoice.is_credit_settled = True
                    invoice.status = 'COMPLETED'
                    invoice.reason = 'COMPLETED Invoice Transaction'

                    if refund_amount > 0:
                        invoice.refund_amount = refund_amount

                invoice.save()

                TreasureService.update_balance(
                    amount=Decimal(effective_payment),
                    operation_type='credit_payment',
                    details={
                        'invoice_id': str(invoice.id),
                        'payment_type': 'PARTIAL' if invoice.remaining_amount > 0
                        else 'FINAL',
                        'remaining_debt': float(invoice.remaining_amount),
                        'refund_issued': refund_amount > 0
                    }
                )

                if refund_amount > 0:
                    TreasureService.update_balance(
                        amount=Decimal(refund_amount),
                        operation_type='refund',
                        details={
                            'invoice_id': str(invoice.id),
                            'reason': f"Refund for overpayment on invoice {invoice.number}",
                        }
                    )
                    logger.info(f"Issued refund of {refund_amount} for invoice {invoice.id}")

                response_data = {
                    'message': 'Payment processed successfully',
                    'effective_payment': float(effective_payment),
                    'refund_amount': float(refund_amount),
                    'remaining_debt': float(invoice.remaining_amount),
                    'invoice_id': invoice_id,
                    'status': invoice.status
                }

                logger.info(
                    f"Processed payment for invoice {invoice_id}: "
                    f"Effective: {effective_payment}, Refund: {refund_amount}, "
                    f"Remaining: {invoice.remaining_amount}"
                )

                return ServiceResponse(success=True, data=response_data)

        except Exception as e:
            logger.error(f"Payment processing failed for invoice {invoice_id}: {str(e)}")
            return ServiceResponse(
                success=False,
                error=f'An error occurred while processing the payment: {str(e)}'
            )

    @staticmethod
    def archive_and_delete_invoice(invoice_id) -> ServiceResponse:
        try:
            with transaction.atomic():
                invoice = Invoice.objects.filter(id=invoice_id).first()
                if not invoice:
                    logger.error(f"Invoice with ID {invoice_id} does not exist.")
                    return ServiceResponse(success=False, error='Invoice not found.')

                archived_invoice = InvoiceArchive(
                    invoice_id=str(invoice.id),
                    number=invoice.number,
                    created_at=invoice.created_at,
                    client_name=invoice.client_name,
                    cashier=invoice.cashier,
                    status=invoice.status,
                    total=invoice.total,
                    tax=invoice.tax,
                    reason=invoice.reason,
                    refund_amount=invoice.refund_amount,
                    advance_paid=invoice.advance_paid,
                    _remaining_amount=invoice._remaining_amount,
                    due_date=invoice.due_date,
                    is_credit_settled=invoice.is_credit_settled,
                )
                archived_invoice.save()

                for line in invoice.lines.all():
                    InvoiceArchiveLine.objects.create(
                        invoice=archived_invoice,
                        product=line.product,
                        quantity=line.quantity,
                        unit_price=line.unit_price,
                        discount=line.discount,
                        line_total=line.line_total,
                    )

                invoice.delete()
                return ServiceResponse(
                    success=True,
                    data={'message': f'Invoice {invoice_id} archived and deleted.'}
                )
        except Exception as e:
            logger.error(f"Error archiving invoice: {str(e)}", exc_info=True)
            return ServiceResponse(
                success=False,
                error=f'An error occurred while archiving the invoice: {str(e)}'
            )

    @staticmethod
    def get_archives_invoices(start_date=None, end_date=None) -> ServiceResponse:
        """
        Get a list of archived invoices within a specific date range.
        """
        try:
            if not start_date:
                start_date = now() - timedelta(days=30)
            if not end_date:
                end_date = now()

            invoices = InvoiceArchive.objects.filter(
                created_at__date__range=(start_date, end_date)
            ).order_by('-created_at')

            return ServiceResponse(success=True, data=invoices)

        except Exception as e:
            logger.error(f"Error fetching invoices: {str(e)}")
            return ServiceResponse(success=False, error=str(e))

    @staticmethod
    def get_invoices(start_date=None, end_date=None) -> ServiceResponse:
        """
        Get a list of invoices within a specific date range.
        """
        try:
            if not start_date:
                start_date = now() - timedelta(days=30)
            if not end_date:
                end_date = now()

            invoices = Invoice.objects.filter(
                created_at__date__range=[start_date, end_date]
            ).order_by('-created_at')

            return ServiceResponse(success=True, data=invoices)

        except Exception as e:
            logger.error(f"Error fetching invoices: {str(e)}")
            return ServiceResponse(success=False, error=str(e))

    def update_invoice(self, invoice_id, updated_data, user) -> ServiceResponse:
        """
        Update an existing invoice, adjusting stock and prices as needed.
        """
        with transaction.atomic():
            try:
                invoice = Invoice.objects.prefetch_related('lines').get(id=invoice_id)

                if user.role != 'manager' and invoice.cashier != user:
                    return ServiceResponse(
                        success=False,
                        error='You do not have permission to perform this action.'
                    )
                invoice.cashier = user

                original_lines = {line.product_id: line for line in invoice.lines.all()}
                updated_lines = {line['product_id']: line for line in updated_data['lines']}

                for product_id, orig_line in original_lines.items():
                    if product_id not in updated_lines:
                        product = orig_line.product
                        product.quantity += orig_line.quantity
                        product.save()
                        orig_line.delete()
                    else:
                        new_qty = updated_lines[product_id]['quantity']
                        diff = new_qty - orig_line.quantity
                        if diff != 0:
                            product = orig_line.product
                            if diff > 0:
                                stock_validation = self.validate_stock(
                                    product=product, quantity=diff
                                )
                                if not stock_validation.success:
                                    return stock_validation
                                product.quantity -= diff
                            else:
                                product.quantity -= diff
                            product.save()
                            orig_line.quantity = new_qty
                            orig_line.discount = updated_lines[product_id].get(
                                'discount', orig_line.discount
                            )
                            orig_line.unit_price = product.get_price()
                            orig_line.line_total = (orig_line.unit_price * new_qty
                                                    ) - orig_line.discount
                            orig_line.save()

                for product_id, line_data in updated_lines.items():
                    if product_id not in original_lines:
                        product = Product.objects.get(id=product_id)
                        stock_validation = self.validate_stock(
                            product=product, quantity=line_data['quantity']
                        )
                        if not stock_validation.success:
                            return stock_validation
                        product.quantity -= line_data['quantity']
                        product.save()
                        unit_price = product.get_price()
                        discount = line_data.get('discount', Decimal('0.00'))
                        line_total = (unit_price * line_data['quantity']) - discount
                        invoice.lines.create(
                            product=product,
                            quantity=line_data['quantity'],
                            unit_price=unit_price,
                            discount=discount,
                            line_total=line_total,
                        )

                invoice.client_name = updated_data.get('client_name', invoice.client_name)
                invoice.tax = updated_data.get(
                    'tax', invoice.tax if invoice.tax is not None else Decimal('0.00')
                ) or Decimal('0.00')
                invoice.status = updated_data.get('status', invoice.status)
                invoice.reason = updated_data.get('reason', invoice.reason)
                invoice.advance_paid = updated_data.get('advance_paid', invoice.advance_paid)
                invoice.due_date = updated_data.get('due_date', invoice.due_date)
                invoice.save()

                # Recalculate totals
                totals_response = ReportService.calculate_invoice_totals(invoice)
                if not totals_response.success:
                    transaction.set_rollback(True)
                    return totals_response

                return ServiceResponse(success=True, data=invoice)
            except Invoice.DoesNotExist:
                return ServiceResponse(success=False, error='Invoice not found.')

            except Exception as e:
                logger.error(f"Error updating invoice: {e}")
                transaction.set_rollback(True)
                return ServiceResponse(
                    success=False, error=f"Error updating invoice: {str(e)}"
                )
