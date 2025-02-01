import logging
from decimal import Decimal
from io import BytesIO
from datetime import timedelta

from django.db import transaction
from django.db.models import Sum, F, Exists, OuterRef, Count
from django.utils import timezone
from django.utils.timezone import now
from django.template.loader import get_template
from xhtml2pdf import pisa
from rest_framework.exceptions import ValidationError

from stock.models import Product, Stock, StockMovement
from reports.models import Invoice, SalesReport, InventoryReport, Notification

logger = logging.getLogger(__name__)


class ReportService:
    """
    Service for handling reports, invoices, and related operations.
    """

    @staticmethod
    def create_notification(user, product, notification_type, message):
        try:
            Notification.objects.create(
                user=user,
                product=product,
                notification_type=notification_type,
                message=message,
            )
        except Exception as e:
            logger.error(f'Unexpected error occurred: {str(e)}')
            raise f'Unexpected error occurred: {str(e)}'


    @staticmethod
    def validate_stock(user, product, quantity):
        """
        Validate if sufficient stock is available for the given product and quantity.
        """
        if quantity <= 0:
            raise ValidationError(
                f"Invalid quantity: {quantity}. Quantity must be greater than 0."
            )

        if product.quantity < quantity:

            message = f"Stock is low for {product.name}. "
            f"Available: {product.quantity}, Required: {quantity}"

            ReportService.create_notification(
                user=user,product=product, notification_type="CRITICAL_STOCK", message=message
            )
            return False
        return True

    @staticmethod
    def update_stock(product, quantity, user, reason):
        """
        Update stock levels after a transaction and log the stock movement.
        """
        if not ReportService.validate_stock(user, product, quantity):
            raise ValidationError(f"Insufficient stock for {product.name}.")

        try:
            product.quantity -= quantity
            StockMovement.objects.create(
                movement_type="EXIT",
                quantity=-quantity,
                product=product,
                category=product.category,
                subcategory=product.subcategory if product.subcategory else None,
                user=user,
                reason=reason
            )
            product.save()

            if product.quantity < product.min_quantity:
                message = (f"Critical stock for {product.name}."
                           f" Available quantity : {product.quantity}")
                ReportService.create_notification(
                    user=user,
                    product=product,
                    notification_type="CRITICAL_STOCK",
                    message=message
                )
        except Exception as e:
            logger.error(f"Error updating stock for product {product.name}: {e}")
            raise ValidationError(f"Failed to update stock for product {product.name}")

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

            if invoice.status == "CREDIT" :
                invoice.remaining_amount = invoice.total - invoice.advance_paid
                invoice.is_credit_settled = invoice.remaining_amount <= 0
            else:
                invoice.remaining_amount = Decimal('0.00')

            invoice.save()
        except Exception as e:
            logger.error(f"Error calculating invoice totals for invoice {invoice.id}: {e}")
            raise ValidationError("Error calculating invoice totals.")

    @staticmethod
    def create_sales_report(date=None, user=None):
        """
        Create or retrieve a daily sales report.
        """
        if not date:
            date = timezone.now().date()

        reports = SalesReport.objects.filter(date=date)
        if reports.exists():
            report = reports.first()

        else:
            report = SalesReport.objects.create(
                date=date,
                total_sales=Decimal('0.00'),
                total_invoices=0,
                generated_by=user
            )
        if not report.generated_by:
            report.generated_by = user
            report.save()

        return report

    @staticmethod
    def update_sales_report(invoice):
        """
        Update the sales report with the latest invoice data.
        """
        try:
            report = ReportService.create_sales_report(invoice.created_at.date(), invoice.cashier)
            advance_paid = invoice.advance_paid if invoice.advance_paid is not None else Decimal('0.00')

            if invoice.status in ["COMPLETED", "CREDIT"] and advance_paid >= invoice.total:
                report.total_sales = Decimal(report.total_sales)
                report.total_sales += invoice.total
                report.total_invoices += 1
                report.save()
        except Exception as e:
            logger.error(f"Error updating sales report for invoice {invoice.id}: {e}")
            raise ValidationError("Error updating sales report.")

    @staticmethod
    def process_invoice(data, user):
        """
        Handle the complete workflow for processing a sale and creating an invoice.
        """
        with transaction.atomic():
            try:
                invoice = Invoice.objects.create(
                    client_name=data.get("client_name"),
                    cashier=user,
                    tax=data.get("tax", Decimal('0.00')),
                    status=data.get("status"),
                    reason=data.get("reason", ""),
                    advance_paid=data.get("advance_paid", Decimal('0.00')),
                    due_date=data.get('due_date', '')
                )

                total_amount = Decimal('0.00')

                for line_data in data["lines"]:
                    product_id = line_data["product_id"]
                    quantity = line_data["quantity"]

                    try:
                        product = Product.objects.get(id=product_id)
                    except Product.DoesNotExist:
                        raise ValidationError(f"Product with ID {product_id} does not exist.")

                    if not ReportService.validate_stock(product, quantity):
                        raise ValidationError(f"Insufficient stock for {product.name}.")

                    unit_price = product.get_price()
                    discount = line_data.get("discount", Decimal('0.00'))
                    line_total = (unit_price * quantity) - discount
                    total_amount += line_total
                    invoice.lines.create(
                        product=product,
                        quantity=quantity,
                        unit_price=unit_price,
                        discount=discount,
                        line_total=line_total
                    )

                    ReportService.update_stock(product, quantity, user, reason="Sale transaction")

                    if product.quantity < product.min_quantity:
                        message = (f"Low stock for {product.name} after sale. "
                                   f"Available: {product.quantity}")
                        ReportService.create_notification(
                            user=user,
                            product=product,
                            notification_type="CRITICAL_STOCK",
                            message=message
                        )

                invoice.total = total_amount
                invoice.save()

                if invoice.status == "COMPLETED" or (
                        invoice.status == "CREDIT" and invoice.advance_paid >= invoice.total):
                    ReportService.calculate_invoice_totals(invoice)
                    ReportService.update_sales_report(invoice)

                return invoice
            except Exception as e:
                logger.error(f"Error processing invoice: {e}")
                raise ValidationError(f"An error occurred while processing the invoice: {str(e)}")

    @staticmethod
    def generate_inventory_report(start_date=None, end_date=None, user=None):
        """
        Generate a detailed inventory report with optional date filters.
        """
        if not start_date:
            start_date = now() - timedelta(days=30)
        if not end_date:
            end_date = now()

        if end_date < start_date:
            raise ValidationError("End date cannot be earlier than start date.")

        total_products = Product.objects.count()
        expired_products = Product.objects.filter(is_expired=True).count()
        low_stock_products = Product.objects.filter(quantity__lt=F('min_quantity')).count()

        report = InventoryReport.objects.create(
            generated_by=user,
            total_products=total_products,
            expired_products=expired_products,
            low_stock_products=low_stock_products,
            date_range=f"{start_date.date()} to {end_date.date()}",
        )

        logger.info(f"Inventory report generated by {user}.")
        return report

    @staticmethod
    def get_inventory_data(start_date=None, end_date=None):
        """
        Generate data for inventory levels within a specific date range.
        """

        if not start_date:
            start_date = now() - timedelta(days=30)
        if not end_date:
            end_date = now()

        if end_date < start_date:
            raise ValidationError("End date cannot be earlier than start date.")

        products = Product.objects.filter(
            Exists(Stock.objects.filter(product=OuterRef('pk'), created_at__range=[start_date, end_date]))
        ).prefetch_related('stocks')

        inventory_data = []
        for product in products:
            stocks_in_range = product.stocks.filter(created_at__range=[start_date, end_date])

            for stock in stocks_in_range:
                inventory_data.append({
                    "product_name": product.name,
                    "category": product.category.name,
                    "subcategory": product.subcategory.name if product.subcategory else None,
                    "unit_price": product.unit_price,
                    "created_at": stock.product.created_at,
                    "expiry_date": product.expiry_date,
                    "is_expired": product.is_expired,
                    "quantity": stock.product.quantity,
                    "min_quantity": product.min_quantity,
                    "is_critical": stock.product.quantity < product.min_quantity,
                })

        logger.info(f"Inventory data generated for range: {start_date} to {end_date}.")
        return inventory_data

    @staticmethod
    def get_sales_summary(start_date=None, end_date=None, user=None):
        """
        Get a summary of sales for a given period.
        """
        if not start_date:
            start_date = now() - timedelta(days=30)
        if not end_date:
            end_date = now()

        if end_date < start_date:
            raise ValidationError("End date cannot be earlier than start date.")

        invoices = Invoice.objects.filter(created_at__range=(start_date, end_date))

        if user:
            invoices = invoices.filter(cashier=user)

        total_revenue = Decimal('0.00')
        total_invoices = invoices.count()

        for invoice in invoices:
            total_revenue += invoice.total

        logger.info(f"Sales summary retrieved for period {start_date} to {end_date}.")

        return {
            "total_revenue": total_revenue,
            "total_invoices": total_invoices
        }

    @staticmethod
    def export_invoice_to_pdf(invoice_id):
        """
        Export an invoice to PDF format.
        """
        try:
            invoice = Invoice.objects.prefetch_related('lines__product').get(id=invoice_id)
            template = get_template("invoice_template.html")
            context = {
                "invoice": invoice,
                "lines": invoice.lines.all(),
            }
            html = template.render(context)
            pdf_buffer = BytesIO()
            pisa_status = pisa.CreatePDF(html, dest=pdf_buffer)

            if pisa_status.err:
                logger.error(f"Failed to generate PDF for invoice {invoice_id}.")
                raise ValidationError("Failed to generate PDF.")

            pdf_buffer.seek(0)
            logger.info(f"PDF generated successfully for invoice {invoice_id}.")
            return pdf_buffer

        except Invoice.DoesNotExist:
            logger.error(f"Invoice with ID {invoice_id} does not exist.")
            raise ValidationError(f"Invoice with ID {invoice_id} does not exist.")
        except Exception as e:
            logger.error(f"Error in export_invoice_to_pdf: {str(e)}")
            raise ValidationError({"error": f"An unexpected error occurred: {str(e)}"})
