import logging
from io import BytesIO
from datetime import timedelta

from django.db import transaction
from django.db.models import Sum, F
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
    def validate_stock(product, quantity):
        """
        Validate if sufficient stock is available for the given product and quantity.
        """
        if product.quantity < quantity:
            Notification.objects.create(
                product=product,
                type="LOW_STOCK",
                message=f"Stock is low for {product.name}. "
                        f"Available: {product.quantity}, Required: {quantity}"
            )
            return False
        return True

    @staticmethod
    def update_stock(product, quantity, reason=None):
        """
        Update stock levels after a transaction and log the stock movement.
        """
        product.quantity -= quantity

        StockMovement.objects.create(
            movement_type="EXIT",
            quantity=-quantity,
            product=product,
            category=product.category,
            subcategory=product.subcategory,
            reason=reason
        )
        product.save()

    @staticmethod
    def calculate_invoice_totals(invoice):
        """
        Calculate the total amount for an invoice, including applicable taxes.
        """
        lines = invoice.lines.all()
        total = sum(line.line_total for line in lines)

        tax_amount = (total * invoice.tax) / 100
        invoice.total = total + tax_amount
        invoice.save()

    @staticmethod
    def create_sales_report(date=None):
        """
        Create or retrieve a daily sales report.
        """
        if not date:
            date = now().date()
        report, _ = SalesReport.objects.get_or_create(
            date=date,
            defaults={
                "total_sales": 0.00,
                "total_invoices": 0
            }
        )
        return report

    @staticmethod
    def update_sales_report(invoice):
        """
        Update the sales report with the latest invoice data.
        """
        report = ReportService.create_sales_report(invoice.created_at.date())
        report.total_sales += invoice.total
        report.total_invoices += 1
        report.save()

    @staticmethod
    def process_invoice(data, user):
        """
        Handle the complete workflow for processing a sale and creating an invoice.
        """
        with transaction.atomic():
            invoice = Invoice.objects.create(
                client_name=data.get("client_name"),
                cashier=user,
                tax=data.get("tax", 0.00),
            )

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
                discount = line_data.get("discount", 0.00)
                line_total = (unit_price * quantity) - discount

                invoice.lines.create(
                    product=product,
                    quantity=quantity,
                    unit_price=unit_price,
                    discount=discount,
                    line_total=line_total
                )

                ReportService.update_stock(product, quantity, reason="Sale transaction")

            ReportService.calculate_invoice_totals(invoice)
            ReportService.update_sales_report(invoice)

            return invoice

    @staticmethod
    def generate_inventory_report(start_date=None, end_date=None, user=None):
        """
        Generate a detailed inventory report with optional date filters.
        """
        if not start_date:
            start_date = now() - timedelta(days=30)
        if not end_date:
            end_date = now()

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

        products = Product.objects.prefetch_related('stock').all()
        inventory_data = []

        for product in products:
            stock = product.stock.first()
            if stock:
                inventory_data.append({
                    "product_name": product.name,
                    "category": product.category.name,
                    "subcategory": product.subcategory.name if product.subcategory else None,
                    "quantity": stock.quantity,
                    "min_quantity": product.min_quantity,
                    "is_critical": stock.quantity < product.min_quantity,
                })

        logger.info(f"Inventory data generated for range: {start_date} to {end_date}.")
        return inventory_data

    @staticmethod
    def get_sales_summary(start_date=None, end_date=None):
        """
        Get a summary of sales for a given period.
        """
        if not start_date:
            start_date = now() - timedelta(days=30)
        if not end_date:
            end_date = now()

        sales = SalesReport.objects.filter(
            date__range=(start_date, end_date)
        ).aggregate(
            total_revenue=Sum('total_revenue'),
            total_tax=Sum('total_tax'),
            total_quantity=Sum('total_quantity_sold'),
        )

        logger.info(f"Sales summary retrieved for period {start_date} to {end_date}.")
        return sales

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
