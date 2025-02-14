from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from authentication.models import User
from django.db import transaction
from django.db.models import Exists
from django.db.models import F
from django.db.models import OuterRef
from django.template.loader import get_template
from django.utils import timezone
from django.utils.timezone import now
from notifications.service import NotificationService
from reports.models import InventoryReport
from reports.models import Invoice
from reports.models import SalesReport
from rest_framework.exceptions import ValidationError
from stock.models import Product
from stock.models import Stock
from stock.models import StockMovement
from xhtml2pdf import pisa

logger = logging.getLogger(__name__)


class ServiceResponse:
    def __init__(self, success, data=None, error=None):
        self.success = success
        self.data = data
        self.error = error

    def to_dict(self):
        return {
            'success': self.success,
            'data': self.data,
            'error': self.error
        }


class ReportService:
    """
    Service for handling reports, invoices, and related operations.
    """
    notif_service = NotificationService()

    @staticmethod
    def get_managers_and_store_keepers():
        try:
            managers = User.objects.filter(role__in=['stock_keeper', 'manager'])
            if not managers.exists():
                return ServiceResponse(success=False, error='No manager found.')
            return ServiceResponse(success=True, data=managers)
        except Exception as e:
            logger.error(f"Error fetching managers: {str(e)}")
            return ServiceResponse(success=False, error=str(e))

    def validate_stock(self, product, quantity):
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
            print('message', message)
            users_response = ReportService.get_managers_and_store_keepers()
            if not users_response.success:
                return users_response

            for user in users_response.data:
                self.notif_service.create_notification(
                    user=user,
                    product=product,
                    notification_type='CRITICAL_STOCK',
                    message=message,
                )
            return ServiceResponse(success=False, error='Insufficient stock.')
        return ServiceResponse(success=True)

    def update_stock(self, product, quantity, user, reason):
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
                users_response = ReportService.get_managers_and_store_keepers()
                if not users_response.success:
                    return users_response

                for manager in users_response.data:
                    self.notif_service.create_notification(
                        user=manager,
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
    def calculate_invoice_totals(invoice):
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
    def create_sales_report(date=None, user=None):
        """
        Create or retrieve a daily sales report.
        """
        if not date:
            date = timezone.now().date()

        try:
            reports = SalesReport.objects.filter(date=date)
            if reports.exists():
                report = reports.first()
            else:
                report = SalesReport.objects.create(
                    date=date,
                    total_sales=Decimal('0.00'),
                    total_invoices=0,
                    generated_by=user,
                )
            if not report.generated_by:
                report.generated_by = user
                report.save()

            return ServiceResponse(success=True, data=report)
        except Exception as e:
            logger.error(f"Error creating sales report: {e}")
            return ServiceResponse(success=False, error=str(e))

    @staticmethod
    def update_sales_report(invoice):
        """
        Update the sales report with the latest invoice data.
        """
        try:
            report_response = ReportService.create_sales_report(
                invoice.created_at.date(), invoice.cashier
            )
            if not report_response.success:
                return report_response

            report = report_response.data
            advance_paid = (
                invoice.advance_paid
                if invoice.advance_paid is not None
                else Decimal('0.00')
            )

            if (
                invoice.status in ['COMPLETED', 'CREDIT']
                and advance_paid >= invoice.total
            ):
                report.total_sales = Decimal(report.total_sales)
                report.total_sales += invoice.total
                report.total_invoices += 1
                report.save()
            return ServiceResponse(success=True)
        except Exception as e:
            logger.error(
                f"Error updating sales report for invoice {invoice.id}: {e}"
            )
            return ServiceResponse(
                success=False, error=f"Error updating sales report: {str(e)}"
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
            logger.error(f"Error creating invoice: {e}")
            return ServiceResponse(success=False, error=str(e))

    def process_invoice_lines(self, invoice, lines_data, user):
        """
        Process invoice lines and update stock.
        """
        total_amount = Decimal('0.00')
        sold_products = []

        for line_data in lines_data:
            product_id = line_data['product_id']
            quantity = line_data['quantity']

            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                return ServiceResponse(
                    success=False, error=f"Product with ID {product_id} does not exist."
                )

            stock_validation = self.validate_stock(product, quantity)
            if not stock_validation.success:
                return stock_validation

            unit_price = product.get_price()
            discount = line_data.get('discount', Decimal('0.00'))
            line_total = (unit_price * quantity) - discount
            total_amount += line_total

            invoice.lines.create(
                product=product,
                quantity=quantity,
                unit_price=unit_price,
                discount=discount,
                line_total=line_total,
            )

            stock_update_response = self.update_stock(
                product, quantity, user, reason='Sale transaction'
            )
            if not stock_update_response.success:
                return stock_update_response

            sold_products.append((product, quantity))

        return ServiceResponse(success=True, data=(total_amount, sold_products))

    @staticmethod
    def handle_completed_or_credit(invoice):
        """Handle COMPLETED and CREDIT statuses."""
        try:
            if invoice.status == 'CREDIT':
                invoice.remaining_amount = max(
                    invoice.total - invoice.advance_paid, Decimal('0.00'))

                if invoice.advance_paid >= invoice.total:
                    invoice.status = 'COMPLETED'
                    invoice.is_credit_settled = True
                    invoice.refund_amount = invoice.advance_paid - invoice.total

            elif invoice.status == 'COMPLETED':
                invoice.remaining_amount = Decimal('0.00')
                invoice.is_credit_settled = True

            return ServiceResponse(success=True)
        except Exception as e:
            logger.error(f"Error handling invoice status: {e}")
            return ServiceResponse(success=False, error=str(e))

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
            return ServiceResponse(success=False, error=str(e))

    @staticmethod
    def finalize_invoice(invoice):
        """Calculate totals and update reports."""
        try:
            totals_response = ReportService.calculate_invoice_totals(invoice)
            if not totals_response.success:
                return totals_response

            if invoice.status != 'CANCELLED':
                report_response = ReportService.update_sales_report(invoice)
                if not report_response.success:
                    return report_response

            invoice.save()
            return ServiceResponse(success=True)
        except Exception as e:
            logger.error(f"Error finalizing invoice: {e}")
            return ServiceResponse(success=False, error=str(e))

    def process_invoice(self, data, user):
        """
        Handle the complete workflow for processing a sale and creating an invoice.
        """
        with transaction.atomic():
            try:
                invoice_response = ReportService.create_invoice(data, user)
                if not invoice_response.success:
                    return invoice_response

                invoice = invoice_response.data
                lines_response = self.process_invoice_lines(invoice, data['lines'], user)
                if not lines_response.success:
                    transaction.set_rollback(True)
                    return lines_response

                total_amount, sold_products = lines_response.data
                invoice.total = total_amount
                invoice.save()

                if invoice.status in ['COMPLETED', 'CREDIT']:
                    status_response = ReportService.handle_completed_or_credit(invoice)
                    if not status_response.success:
                        transaction.set_rollback(True)
                        return status_response
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
    def generate_inventory_report(start_date=None, end_date=None, user=None):
        """
        Generate a detailed inventory report with optional date filters.
        """
        try:
            if not start_date:
                start_date = now() - timedelta(days=30)
            if not end_date:
                end_date = now()

            if end_date < start_date:
                return ServiceResponse(
                    success=False, error='End date cannot be earlier than start date.'
                )

            products = Product.objects.filter(created_at__range=[start_date, end_date])
            total_products = products.count()
            expired_products = products.filter(is_expired=True).count()
            low_stock_products = products.filter(
                quantity__lt=F('min_quantity')
            ).count()

            report = InventoryReport.objects.create(
                generated_by=user,
                total_products=total_products,
                expired_products=expired_products,
                low_stock_products=low_stock_products,
                date_range=f"{start_date.date()} to {end_date.date()}",
            )

            logger.info(f"Inventory report generated by {user}.")
            return ServiceResponse(success=True, data=report)

        except Exception as e:
            logger.error(f"Error generating inventory report: {str(e)}")
            return ServiceResponse(success=False, error=str(e))

    @staticmethod
    def get_inventory_data(start_date=None, end_date=None):
        """
        Generate data for inventory levels within a specific date range.
        """
        try:
            if not start_date:
                start_date = now() - timedelta(days=30)
            if not end_date:
                end_date = now()

            if end_date < start_date:
                return ServiceResponse(
                    success=False, error='End date cannot be earlier than start date.'
                )

            products = Product.objects.filter(
                Exists(
                    Stock.objects.filter(
                        product=OuterRef('pk'),
                        created_at__range=[start_date, end_date],
                    )
                )
            ).prefetch_related('stocks')

            inventory_data = []
            for product in products:
                stocks_in_range = product.stocks.filter(
                    created_at__range=[start_date, end_date]
                )

                for stock in stocks_in_range:
                    inventory_data.append(
                        {
                            'product_name': product.name,
                            'category': product.category.name,
                            'subcategory': (
                                product.subcategory.name
                                if product.subcategory
                                else None
                            ),
                            'unit_price': product.unit_price,
                            'created_at': stock.product.created_at,
                            'expiry_date': product.expiry_date,
                            'is_expired': product.is_expired,
                            'quantity': stock.product.quantity,
                            'min_quantity': product.min_quantity,
                            'is_critical': stock.product.quantity < product.min_quantity,
                        }
                    )

            logger.info(
                f"Inventory data generated for range: {start_date} to {end_date}."
            )
            return ServiceResponse(success=True, data=inventory_data)

        except Exception as e:
            logger.error(f"Error generating inventory data: {str(e)}")
            return ServiceResponse(success=False, error=str(e))

    @staticmethod
    def get_sales_summary(start_date=None, end_date=None, user=None):
        """
        Get a summary of sales for a given period.
        """
        try:
            if not start_date:
                start_date = now() - timedelta(days=30)
            if not end_date:
                end_date = now()

            if end_date < start_date:
                return ServiceResponse(
                    success=False, error='End date cannot be earlier than start date.'
                )

            invoices = Invoice.objects.filter(
                created_at__range=(start_date, end_date)
            )

            if user:
                invoices = invoices.filter(cashier=user)

            total_revenue = Decimal('0.00')
            total_invoices = invoices.count()

            for invoice in invoices:
                total_revenue += invoice.total

            logger.info(
                f"Sales summary retrieved for period {start_date} to {end_date}."
            )

            return ServiceResponse(success=True, data={
                'total_revenue': total_revenue,
                'total_invoices': total_invoices,
            })

        except Exception as e:
            logger.error(f"Error generating sales summary: {str(e)}")
            return ServiceResponse(success=False, error=str(e))

    @staticmethod
    def export_invoice_to_pdf(invoice_id):
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
                invoice.advance_paid += amount
                refund_amount = 0

                if invoice.advance_paid >= invoice.total:
                    refund_amount = invoice.advance_paid - invoice.total
                    invoice.advance_paid = invoice.total
                    invoice.remaining_amount = 0
                    invoice.refund_amount = refund_amount
                    invoice.is_credit_settled = True
                    invoice.status = 'COMPLETED'

                invoice.save()

            if refund_amount > 0:
                logger.info(
                    f"Overpayment detected for invoice ID {invoice_id}."
                    f" Refund amount: {refund_amount}."
                )
                return ServiceResponse(
                    success=True,
                    data={
                        'message': 'Payment processed successfully.',
                        'advance_paid': amount,
                        'refund_amount': refund_amount,
                        'remaining_amount': 0,
                        'invoice_id': invoice_id,
                        'status': invoice.status
                    }
                )
            logger.info(
                f"Payment of {amount} successfully applied to invoice ID {invoice_id}."
            )
            return ServiceResponse(
                success=True,
                data={
                    'message': 'Payment processed successfully.',
                    'refund_amount': refund_amount,
                    'invoice_id': invoice_id,
                    'status': invoice.status
                }
            )

        except Exception as e:
            logger.error(f"Payment processing failed for invoice ID {invoice_id}: {str(e)}")
            return ServiceResponse(
                success=False, error='An error occurred while processing the payment.'
            )
