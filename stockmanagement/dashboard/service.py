from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal
from decimal import ROUND_DOWN

from django.db.models import Case
from django.db.models import DecimalField
from django.db.models import ExpressionWrapper
from django.db.models import F
from django.db.models import Sum
from django.db.models import Value
from django.db.models import When
from django.db.models.functions import Coalesce
from django.db.models.functions import TruncDay
from django.db.models.functions import TruncMonth
from django.db.models.functions import TruncWeek
from django.db.models.functions import TruncYear
from django.utils import timezone
from reports.models import Invoice
from reports.models import InvoiceLine
from reports.service import ServiceResponse
from stock.models import Product

logger = logging.getLogger(__name__)


class DashboardService:
    """
    Service for providing dashboard data with period-based aggregations.
    """

    @staticmethod
    def get_period_boundaries(period):
        """
        Calculate start and end dates based on the specified period.
        """
        today = timezone.now().date()

        if period == 'daily':
            start_date = today
            end_date = today
        elif period == 'weekly':
            start_date = today - timedelta(days=6)
            end_date = today
        elif period == 'monthly':
            start_date = today - timedelta(days=29)
            end_date = today
        elif period == 'yearly':
            start_date = today - timedelta(days=364)
            end_date = today
        else:
            start_date = today - timedelta(days=29)
            end_date = today

        return start_date, end_date

    @staticmethod
    def get_dashboard_stats(period='monthly'):
        """
        Get main KPI statistics for the dashboard.
        """
        try:
            start_date, end_date = DashboardService.get_period_boundaries(period)

            # Calculate previous period for comparison
            period_length = (end_date - start_date).days + 1
            previous_end = start_date - timedelta(days=1)
            previous_start = previous_end - timedelta(days=period_length - 1)

            # Current period revenue
            current_invoices = Invoice.objects.filter(
                created_at__date__range=[start_date, end_date],
                status__in=['COMPLETED', 'CREDIT']
            )
            current_revenue = current_invoices.aggregate(
                total=Sum('total'))['total'] or Decimal('0.00')

            # Previous period revenue
            previous_invoices = Invoice.objects.filter(
                created_at__date__range=[previous_start, previous_end],
                status__in=['COMPLETED', 'CREDIT']
            )
            previous_revenue = previous_invoices.aggregate(
                total=Sum('total'))['total'] or Decimal('0.00')

            # Calculate revenue change
            revenue_change = 0
            if previous_revenue > 0:
                revenue_change = ((current_revenue - previous_revenue
                                   ) / previous_revenue) * 100

            # Current period orders
            current_orders_count = current_invoices.count()

            # Previous period orders
            previous_orders_count = previous_invoices.count()

            # Calculate orders change
            orders_change = 0
            if previous_orders_count > 0:
                orders_change = ((current_orders_count - previous_orders_count
                                  ) / previous_orders_count) * 100

            # Average order value
            current_avg_order = Decimal('0.00')
            if current_orders_count > 0:
                current_avg_order = (current_revenue / current_orders_count).quantize(
                    Decimal('0.001'), rounding=ROUND_DOWN)

            previous_avg_order = Decimal('0.00')
            if previous_orders_count > 0:
                previous_avg_order = (previous_revenue / previous_orders_count).quantize(
                    Decimal('0.001'), rounding=ROUND_DOWN)

            # Calculate average order change
            avg_order_change = 0
            if previous_avg_order > 0:
                avg_order_change = ((current_avg_order - previous_avg_order
                                     ) / previous_avg_order) * 100

            # Unique client names (as a proxy for customers)
            current_customers = current_invoices.values('client_name').distinct().count()
            previous_customers = previous_invoices.values('client_name').distinct().count()

            # Calculate customers change
            customers_change = 0
            if previous_customers > 0:
                customers_change = ((current_customers - previous_customers
                                     ) / previous_customers) * 100

            return ServiceResponse(success=True, data={
                'revenue': {
                    'value': float(current_revenue),
                    'change': round(revenue_change, 1),
                    'period': period
                },
                'orders': {
                    'value': current_orders_count,
                    'change': round(orders_change, 1),
                    'period': period
                },
                'averageOrderValue': {
                    'value': float(current_avg_order),
                    'change': round(avg_order_change, 1),
                    'period': period
                },
                'customers': {
                    'value': current_customers,
                    'change': round(customers_change, 1),
                    'period': period
                }
            })

        except Exception as e:
            logger.error(f"Error in get_dashboard_stats: {str(e)}")
            return ServiceResponse(success=False, error=str(e))

    @staticmethod
    def get_sales_data(period='monthly'):
        """
        Fetch dashboard sales data:
        - Sales over time
        - Recent sales
        - Sales by category
        - Monthly revenue
        """
        try:
            start_date, end_date = DashboardService.get_period_boundaries(period)
            trunc_mapping = {
                'daily': TruncDay,
                'weekly': TruncWeek,
                'monthly': TruncMonth,
                'yearly': TruncYear,
            }
            if period not in trunc_mapping:
                return ServiceResponse(success=False, error='Invalid period')

            trunc_function = trunc_mapping[period]

            invoice_qs = Invoice.objects.filter(
                created_at__date__range=[start_date, end_date],
                status__in=['COMPLETED', 'CREDIT']
            )

            invoice_ids = invoice_qs.values_list('id', flat=True)

            invoice_line_qs = InvoiceLine.objects.filter(invoice_id__in=invoice_ids)

            # SALES OVER TIME (From InvoiceLine)
            sales_lines = invoice_line_qs.select_related('product', 'invoice').annotate(
                period=trunc_function('invoice__created_at'),
                status=F('invoice__status')
            ).values('period').annotate(
                sales=Sum('line_total'),
                completed_profit=Sum(
                    Case(
                        When(
                            invoice__status='COMPLETED',
                            then=ExpressionWrapper(
                                F('quantity') * (
                                        F('unit_price') - F('product__purchase_price')),
                                output_field=DecimalField(max_digits=15, decimal_places=3)
                            )
                        ),
                        default=Value(0),
                        output_field=DecimalField(max_digits=15, decimal_places=2)
                    )
                ),
                credit_amount=Sum(
                    Case(
                        When(
                            invoice__status='CREDIT',
                            then=ExpressionWrapper(
                                F('quantity') * (
                                        F('unit_price') - F('product__purchase_price')),
                                output_field=DecimalField(max_digits=15, decimal_places=3)
                            )
                        ),
                        default=Value(0),
                        output_field=DecimalField(max_digits=15, decimal_places=2)
                    )
                )
            ).order_by('period')

            formatted_sales = []
            for entry in sales_lines:
                period_label = DashboardService.format_period_label(entry['period'], period)

                completed_profit = float(entry['completed_profit'] or 0)
                credit_amount = float(entry['credit_amount'] or 0)

                sale_entry = {
                    'period': period_label,
                    'sales': float(entry['sales']),
                    'profit': completed_profit,
                    'credit_profit': abs(credit_amount)
                }

                formatted_sales.append(sale_entry)

            # RECENT SALES
            recent_sales = invoice_qs.order_by('-created_at')[:10]

            formatted_recent_sales = []
            for invoice in recent_sales:
                formatted_recent_sales.append({
                    'id': str(invoice.id),
                    'customerName': invoice.client_name or 'Anonymous',
                    'amount': float(invoice.total),
                    'date': invoice.created_at.isoformat(),
                })

            # SALES BY CATEGORY
            sales_by_category = invoice_line_qs.select_related('product__category').values(
                'product__category__id',
                'product__category__name'
            ).annotate(
                value=Sum(
                    'line_total',
                    output_field=DecimalField(max_digits=15, decimal_places=2)
                )
            ).order_by('-value')

            formatted_categories = []
            for category in sales_by_category:
                if category['product__category__name']:
                    formatted_categories.append({
                        'name': category['product__category__name'],
                        'value': float(category['value']),
                    })

            # MONTHLY REVENUE (Total)
            monthly_revenue = invoice_line_qs.annotate(
                month=TruncMonth('invoice__created_at')
            ).values('month').annotate(
                revenue=Sum('line_total')
            ).order_by('month')

            formatted_monthly_revenue = []
            for entry in monthly_revenue:
                formatted_monthly_revenue.append({
                    'month': entry['month'].strftime('%b'),
                    'revenue': float(entry['revenue'])
                })

            credit_invoices = Invoice.objects.filter(
                created_at__date__range=[start_date, end_date],
                status='CREDIT'
            )
            pending_payment_data = credit_invoices.aggregate(
                pending_payment=Coalesce(
                    Sum('_remaining_amount',
                        output_field=DecimalField(max_digits=15, decimal_places=2)),
                    Value(Decimal('0.00'))
                )
            )
            pending_payment = float(pending_payment_data['pending_payment'] or 0.00)
            return ServiceResponse(success=True, data={
                'salesOverTime': formatted_sales,
                'recentSales': formatted_recent_sales,
                'salesByCategory': formatted_categories,
                'monthlyRevenue': formatted_monthly_revenue,
                'globalPendingPayment': pending_payment,
            })

        except Exception as e:
            logger.error(f"Error in get_sales_data: {str(e)}")
            return ServiceResponse(success=False, error=str(e))

    @staticmethod
    def get_products_data(period='monthly'):
        """
        Get product performance data.
        """
        try:
            start_date, end_date = DashboardService.get_period_boundaries(period)

            # Top selling products
            invoice_lines_qs = InvoiceLine.objects.filter(
                invoice__created_at__date__range=[start_date, end_date],
                invoice__status__in=['COMPLETED', 'CREDIT']
            )

            top_products = invoice_lines_qs.values(
                'product__name'
            ).annotate(
                sold=Sum('quantity'),
                revenue=Sum('line_total')
            ).order_by('-sold')[:5]

            formatted_top_products = []

            for i, product in enumerate(top_products):
                formatted_top_products.append({
                    'name': product['product__name'],
                    'sold': product['sold'],
                    'revenue': float(product['revenue']),
                })

            # Product performance for bar chart
            product_performance = invoice_lines_qs.values(
                'product__name'
            ).annotate(
                value=Sum('quantity')
            ).order_by('-value')[:5]

            formatted_performance = []
            for i, product in enumerate(product_performance):
                formatted_performance.append({
                    'name': product['product__name'],
                    'value': product['value'],
                })

            return ServiceResponse(success=True, data={
                'topProducts': formatted_top_products,
                'productPerformance': formatted_performance
            })

        except Exception as e:
            logger.error(f"Error in get_products_data: {str(e)}")
            return ServiceResponse(success=False, error=str(e))

    @staticmethod
    def get_inventory_data():
        """
        Get inventory status data.
        """
        try:
            # Stock status overview
            in_stock = Product.objects.filter(quantity__gt=F('min_quantity')).count()
            low_stock = Product.objects.filter(
                quantity__gt=0,
                quantity__lte=F('min_quantity')
            ).count()
            out_of_stock = Product.objects.filter(quantity=0).count()

            stock_status = [
                {'name': 'In Stock', 'value': in_stock},
                {'name': 'Low Stock', 'value': low_stock},
                {'name': 'Out of Stock', 'value': out_of_stock}
            ]

            # Stock data by product
            products = Product.objects.all()
            stock_data = []

            for product in products:
                stock_data.append({
                    'name': product.name,
                    'inStock': product.quantity if
                    product.quantity > product.min_quantity else 0,
                    'lowStock': product.quantity
                    if 0 < product.quantity <= product.min_quantity else 0,
                    'outOfStock': 'Empty stock' if product.quantity == 0 else 'In stock'
                })

            # Stock alerts
            alerts = {
                'lowStock': low_stock,
                'outOfStock': out_of_stock,
                'overstocked': Product.objects.filter(
                    quantity__gt=F('min_quantity') * 2).count()
            }

            return ServiceResponse(success=True, data={
                'stockStatus': stock_status,
                'stockData': stock_data,
                'alerts': alerts
            })

        except Exception as e:
            logger.error(f"Error in get_inventory_data: {str(e)}")
            return ServiceResponse(success=False, error=str(e))

    @staticmethod
    def format_period_label(date, period):
        """
        Format date label based on period type.
        """
        if period == 'daily':
            return date.strftime('%d %b')
        elif period == 'weekly':
            return f"Week {date.strftime('%U')}"
        elif period == 'monthly':
            return date.strftime('%b')
        elif period == 'yearly':
            return date.strftime('%Y')
        else:
            return date.strftime('%b')
