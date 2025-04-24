from __future__ import annotations

import io
import logging
from datetime import datetime
from datetime import time
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.db.models import Sum
from django.db.models.functions import TruncDay
from django.db.models.functions import TruncMonth
from django.db.models.functions import TruncWeek
from django.db.models.functions import TruncYear
from django.template.loader import render_to_string
from django.utils import timezone
from reports.models import InventoryReport
from reports.models import Invoice
from reports.models import InvoiceLine
from reports.models import Report
from reports.models import SalesReport
from reports.service.entities import ServiceResponse
from stock.models import Product
from stock.models import Stock
from weasyprint import HTML

logger = logging.getLogger(__name__)


class GenerateReportService:

    trunc_mapping = {
        'daily': TruncDay,
        'weekly': TruncWeek,
        'monthly': TruncMonth,
        'yearly': TruncYear,
    }

    @staticmethod
    def normalize_date_range(start_date, end_date):
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date).date()
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date).date()
        start = datetime.combine(start_date, time.min)
        end = datetime.combine(end_date, time.max)
        return timezone.make_aware(start), timezone.make_aware(end)

    @staticmethod
    def get_period_boundaries(period):
        today = timezone.now().date()
        if period == 'daily':
            start_date = today
            end_date = today
        elif period == 'weekly':
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=6)
        elif period == 'monthly':
            start_date = today.replace(day=1)
            next_month = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
            end_date = next_month - timedelta(days=1)
        elif period == 'yearly':
            start_date = today.replace(month=1, day=1)
            end_date = today.replace(month=12, day=31)
        else:
            start_date = today - timedelta(days=29)
            end_date = today
        return start_date, end_date

    @staticmethod
    def determine_date_range(period=None, start_date=None, end_date=None):
        if start_date and end_date:
            return start_date, end_date

        elif period:
            return GenerateReportService.get_period_boundaries(period)

        else:
            today = timezone.now()
            start_date = today.replace(day=1)
            next_month = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
            end_date = next_month - timedelta(days=1)
            return start_date, end_date

    @staticmethod
    def decimal_to_json_serializable(obj):
        import decimal
        import datetime

        if isinstance(obj, decimal.Decimal):
            return float(obj)
        elif isinstance(obj, datetime.datetime):
            return obj.isoformat()
        elif isinstance(obj, datetime.date):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: GenerateReportService.decimal_to_json_serializable(v)
                    for k, v in obj.items()}
        elif isinstance(obj, list):
            return [GenerateReportService.decimal_to_json_serializable(i) for i in obj]
        return obj

    @staticmethod
    def generate_report(
            report_type: str,
            user,
            start_date: str = None,
            end_date: str = None,
            period: str = None
    ) -> ServiceResponse:
        try:
            # Déterminer la plage de dates
            start_date, end_date = GenerateReportService.determine_date_range(
                period, start_date, end_date  # Ordre corrigé des arguments
            )

            # Normaliser les dates pour inclure heures, minutes, secondes
            start_date, end_date = GenerateReportService.normalize_date_range(
                start_date, end_date
            )

            if report_type not in dict(Report.REPORT_TYPE_CHOICES):
                return ServiceResponse(success=False, error='Invalid report type.')

            report_data = GenerateReportService._get_report_data(
                report_type, start_date, end_date, period
            )
            report_data = GenerateReportService.decimal_to_json_serializable(report_data)
            report_data['report_type'] = report_type
            report_data['generated_by'] = user.username
            report_data['created_at'] = timezone.now().isoformat()
            report_data['start_date'] = start_date.isoformat()
            report_data['end_date'] = end_date.isoformat()
            print('report data', report_data)

            with transaction.atomic():
                current_time = timezone.now()
                report = Report.objects.create(
                    type=report_type,
                    generated_by=user,
                    description=f"{report_type.capitalize()} report generated by {user}",
                    generated_at=current_time
                )

                if report_type == 'inventory':
                    inventory_report = InventoryReport.objects.create(
                        report=report,
                        generated_by=user,
                        start_date=start_date,
                        end_date=end_date,
                        total_products=report_data['total_products'],
                        expired_products=report_data['expired_products'],
                        low_stock_products=report_data['low_stock_products'],
                        data=report_data,
                    )
                    inventory_report.stocks.set(Stock.objects.filter(
                        created_at__range=[start_date, end_date])
                    )

                elif report_type == 'sales':

                    total_completed_revenue = report_data.get('total_completed_revenue', 0)
                    total_advance_paid = report_data.get('total_advance_paid', 0)
                    total_completed_sales = report_data.get('total_completed_sales', 0)
                    total_credit_sales = report_data.get('total_credit_sales', 0)
                    total_sales = total_completed_revenue + total_advance_paid
                    total_invoices = total_completed_sales + total_credit_sales

                    sales_report, created = SalesReport.objects.get_or_create(
                        date=current_time.date(),
                        defaults={
                            'report': report,
                            'generated_by': user,
                            'start_date': start_date,
                            'end_date': end_date,
                            'total_sales': total_sales,
                            'total_invoices': total_invoices,
                            'data': report_data,
                        }
                    )
                    if not created:
                        sales_report.report = report
                        sales_report.generated_by = user
                        sales_report.start_date = start_date
                        sales_report.end_date = end_date
                        sales_report.total_sales = total_sales
                        sales_report.total_invoices = total_invoices
                        sales_report.data = report_data
                        sales_report.created_at = current_time
                        sales_report.save()

            return ServiceResponse(
                success=True, data={'report_id': report.id, 'report_data': report_data}
            )
        except Exception as e:
            return ServiceResponse(success=False, error=str(e))

    @staticmethod
    def _get_report_data(
            report_type: str, start_date=None, end_date=None, period=None
    ):
        if report_type == 'inventory':
            return GenerateReportService._generate_inventory_data(start_date, end_date)
        elif report_type == 'sales':
            sales_data_response = GenerateReportService._generate_sales_data(
                start_date, end_date, period
            )
            return sales_data_response.data if sales_data_response.success else {}
        return {}

    @staticmethod
    def _generate_inventory_data(start_date=None, end_date=None):
        now = timezone.now()
        soon = now + timedelta(days=14)

        if start_date and end_date:
            products = Product.objects.filter(
                created_at__range=[start_date, end_date]
            ).select_related('category', 'subcategory')
        else:
            products = Product.objects.all().select_related('category', 'subcategory')

        near_expiry = products.filter(
            expiry_date__range=(now, soon), is_expired=False
        )

        product_list = []
        for product in products:
            product_list.append({
                'name': product.name,
                'category': product.category.name if product.category else None,
                'subcategory': product.subcategory.name if product.subcategory else None,
                'quantity': product.quantity,
                'min_quantity': product.min_quantity,
                'is_expired': product.is_expired,
                'expiry_date': product.expiry_date.isoformat()
                if product.expiry_date else None,
                'is_near_expiry': product in near_expiry,
                'is_critical': product.quantity < product.min_quantity,
                'created_at': product.created_at.isoformat() if product.created_at else None,
            })

        return {
            'total_products': products.count(),
            'expired_products': products.filter(is_expired=True).count(),
            'near_expiry_count': near_expiry.count(),
            'low_stock_products': products.filter(quantity__lt=F('min_quantity')).count(),
            'product_list': product_list,
        }

    @staticmethod
    def _generate_sales_data(
            start_date=None, end_date=None, period=None
    ):
        try:
            # Assurez-vous que start_date et end_date sont bien définis
            if not start_date or not end_date:
                if period:
                    start_date, end_date = GenerateReportService.get_period_boundaries(period)
                    start_date, end_date = GenerateReportService.normalize_date_range(
                        start_date, end_date
                    )
                else:
                    today = timezone.now().date()
                    start_date = datetime.combine(today, time.min)
                    end_date = datetime.combine(today, time.max)
                    start_date = timezone.make_aware(start_date)
                    end_date = timezone.make_aware(end_date)

            completed_invoices = Invoice.objects.filter(
                status='COMPLETED',
                created_at__range=[start_date, end_date]
            )
            credit_invoices = Invoice.objects.filter(
                status='CREDIT',
                created_at__range=[start_date, end_date]
            )

            invoice_ids = list(completed_invoices.values_list('id', flat=True)) + list(
                credit_invoices.values_list('id', flat=True))

            completed_revenue = InvoiceLine.objects.filter(
                invoice__in=completed_invoices
            ).aggregate(total=Sum('line_total'))['total'] or 0

            total_credit_revenue = InvoiceLine.objects.filter(
                invoice__in=credit_invoices
            ).aggregate(total=Sum('line_total'))['total'] or 0

            total_advance_paid = credit_invoices.aggregate(
                total=Sum('advance_paid'))['total'] or 0
            total_remaining_amount = credit_invoices.aggregate(
                total=Sum('_remaining_amount'))['total'] or 0

            credit_profit = InvoiceLine.objects.filter(
                invoice__in=credit_invoices
            ).aggregate(
                total=Sum((F('unit_price') - F('product__purchase_price')) * F('quantity'))
            )['total'] or 0

            profit = InvoiceLine.objects.filter(
                invoice__in=completed_invoices
            ).aggregate(
                total=Sum((F('unit_price') - F('product__purchase_price')) * F('quantity'))
            )['total'] or 0
            discount = InvoiceLine.objects.filter(
                invoice__in=invoice_ids
            ).aggregate(discount=Sum('discount'))['discount'] or 0

            # Utiliser le trunc_func uniquement si period est fourni
            if period and period in GenerateReportService.trunc_mapping:
                trunc_func = GenerateReportService.trunc_mapping.get(period)
                sold_products = list(
                    InvoiceLine.objects.filter(invoice_id__in=invoice_ids)
                    .annotate(period=trunc_func('invoice__created_at'))
                    .values('period', 'product__name', 'unit_price')
                    .annotate(
                        total_quantity=Sum('quantity'),
                        total_revenue=Sum('line_total')
                    ).order_by('-total_quantity')
                )
            else:
                sold_products = list(
                    InvoiceLine.objects.filter(invoice_id__in=invoice_ids)
                    .values('product__name', 'unit_price')
                    .annotate(
                        total_quantity=Sum('quantity'),
                        total_revenue=Sum('line_total')
                    ).order_by('-total_quantity')
                )

            return ServiceResponse(success=True, data={
                'total_completed_sales': completed_invoices.count(),
                'total_completed_revenue': completed_revenue,
                'total_credit_sales': credit_invoices.count(),
                'total_credit_revenue': total_credit_revenue,
                'total_advance_paid': total_advance_paid,
                'total_general': completed_revenue + total_credit_revenue,
                'credit_profit': credit_profit,
                'marge_brute': profit,
                'marge_nette': profit - discount,
                'total_profit_brute': credit_profit + profit,
                'total_profit_nette': credit_profit + profit - discount,
                'money_outstanding': total_remaining_amount,
                'total_discount': discount,
                'products_sold': sold_products
            })

        except Exception as e:
            logger.error(f'Error generating sales data: {e}')
            return ServiceResponse(success=False, error=str(e))

    @staticmethod
    def download_report(report_id):
        try:
            report = Report.objects.get(id=report_id)
            report_type = report.type
            print('report_type', report_type)
            if report_type == 'inventory':
                specific = InventoryReport.objects.get(report_id=report.id)
                print('inventory', specific)
            elif report_type == 'sales':
                specific = SalesReport.objects.get(report_id=report.id)
                print('sales', specific)

            else:
                return ServiceResponse(success=False, error='Unsupported report type.')

            html_string = render_to_string(
                f'{report_type}_report_template.html',
                {'data': specific.data}
            )

            buffer = io.BytesIO()
            HTML(string=html_string).write_pdf(buffer)
            buffer.seek(0)
            return ServiceResponse(success=True, data={
                'pdf_file': buffer,
                'filename': f"{report_type}_report_{datetime.now().date()}.pdf"
            })

        except Report.DoesNotExist:
            return ServiceResponse(success=False, error='Report not found')
        except Exception as e:
            return ServiceResponse(success=False, error=str(e))
