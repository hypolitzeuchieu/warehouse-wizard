from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date
from datetime import datetime
from datetime import timedelta
from decimal import Decimal
from typing import Dict
from typing import Union

from django.db.models import Count
from django.db.models import DecimalField
from django.db.models import ExpressionWrapper
from django.db.models import F
from django.db.models import Q
from django.db.models import Sum
from django.db.models.functions import TruncDay
from django.utils import timezone
from reports.models import Invoice
from reports.models import InvoiceLine
from reports.service.invoice_service import ServiceResponse
from stock.models import Product

logger = logging.getLogger(__name__)


class DashboardService:
    """
    Service for providing dashboard data with period-based aggregations.
    This service handles data calculations for revenue, profit, sales trends,
    and inventory status to be displayed on the dashboard.
    """

    @staticmethod
    def calculate_trend(current: float, previous: float) -> Dict[str, Union[str, float]]:
        if previous == 0:
            if current == 0:
                return {'status': 'stable', 'percentage': 0, 'direction': 'equal'}
            return {'status': 'up', 'percentage': 100, 'direction': 'up'}

        percentage = ((current - previous) / abs(previous)) * 100
        if abs(percentage) < 0.1:
            return {
                'status': 'stable',
                'percentage': round(abs(percentage), 1),
                'direction': 'equal'
            }

        direction = 'up' if percentage > 0 else 'down'
        return {
            'status': direction,
            'percentage': round(abs(percentage), 1),
            'direction': direction
        }

    @staticmethod
    def get_dashboard_stats(start_date, end_date) -> ServiceResponse:
        try:
            if not start_date or not end_date:
                today = date.today()
                start_date = today - timedelta(days=6)
                end_date = today

            start_date = start_date.date() if isinstance(start_date, datetime) else start_date
            end_date = end_date.date() if isinstance(end_date, datetime) else end_date

            delta_days = (end_date - start_date).days + 1
            previous_start = start_date - timedelta(days=delta_days)

            invoices = Invoice.objects.filter(
                created_at__date__range=[previous_start, end_date],
                status__in=['COMPLETED', 'CREDIT']
            ).select_related().prefetch_related('lines', 'lines__product')

            daily_data = defaultdict(DashboardService._initialize_daily_data)
            previous_daily_data = defaultdict(DashboardService._initialize_daily_data)

            for invoice in invoices:
                DashboardService._process_invoice(
                    invoice,
                    start_date,
                    end_date,
                    previous_start,
                    daily_data,
                    previous_daily_data
                )

            results = DashboardService._generate_daily_results(
                start_date, end_date, daily_data, previous_daily_data
            )

            return ServiceResponse(success=True, data=results)

        except Exception as e:
            logger.error(f"Dashboard error: {str(e)}", exc_info=True)
            return ServiceResponse(success=False, error=str(e))

    @staticmethod
    def _initialize_daily_data():
        return {'revenue': Decimal('0.00'), 'profit': Decimal('0.00'), 'orders': 0}

    @staticmethod
    def _process_invoice(
            invoice,
            start_date,
            end_date,
            previous_start,
            daily_data,
            previous_daily_data
    ):
        invoice_date = invoice.created_at.date()

        if start_date <= invoice_date <= end_date:
            data_dict = daily_data
            date_key = invoice_date
        else:
            data_dict = previous_daily_data
            days_from_previous_start = (invoice_date - previous_start).days
            date_key = start_date + timedelta(days=days_from_previous_start)
            if not (start_date <= date_key <= end_date):
                return

        profit = DashboardService._calculate_invoice_profit(invoice)
        data_dict[date_key]['revenue'] += invoice.total
        data_dict[date_key]['profit'] += profit
        data_dict[date_key]['orders'] += 1

    @staticmethod
    def _calculate_invoice_profit(invoice):
        profit = Decimal('0.00')
        for line in invoice.lines.all():
            if hasattr(line, 'product') and line.product and hasattr(
                    line.product, 'purchase_price'
            ):
                unit_price = line.unit_price or Decimal('0.00')
                purchase_price = line.product.purchase_price or Decimal('0.00')
                quantity = line.quantity or 0
                profit += (unit_price - purchase_price) * quantity
        return profit

    @staticmethod
    def _generate_daily_results(
            start_date,
            end_date,
            daily_data,
            previous_daily_data
    ):
        results = []
        current_day = start_date
        while current_day <= end_date:
            current_data = daily_data.get(
                current_day, DashboardService._initialize_daily_data()
            )
            previous_data = previous_daily_data.get(
                current_day, DashboardService._initialize_daily_data()
            )

            results.append({
                'date': current_day.strftime('%Y-%m-%dT00:00:00+00:00'),
                'revenue': float(current_data['revenue']),
                'profit': float(current_data['profit']),
                'orders': current_data['orders'],
                'trends': {
                    'revenue': DashboardService.calculate_trend(
                        float(current_data['revenue']), float(previous_data['revenue'])
                    ),
                    'profit': DashboardService.calculate_trend(
                        float(current_data['profit']), float(previous_data['profit'])
                    ),
                    'orders': DashboardService.calculate_trend(
                        float(current_data['orders']), float(previous_data['orders'])
                    )
                }
            })
            current_day += timedelta(days=1)
        return results

    @staticmethod
    def get_sales_data(start_date: date, end_date: date) -> ServiceResponse:
        try:
            tz = timezone.get_current_timezone()

            if not start_date or not end_date:
                today = date.today()
                start_date = today - timedelta(days=6)
                end_date = today

            # Conversion correcte avec make_aware
            start_datetime = timezone.make_aware(
                datetime.combine(start_date, datetime.min.time()), tz
            )
            end_datetime = timezone.make_aware(
                datetime.combine(end_date, datetime.max.time()), tz
            ) + timedelta(days=1)

            sales = (
                InvoiceLine.objects.filter(
                    invoice__created_at__range=(start_datetime, end_datetime)
                )
                .annotate(
                    day=TruncDay('invoice__created_at', tzinfo=tz),
                    status=F('invoice__status')
                )
                .values('day', 'status')
                .annotate(
                    revenue=Sum('line_total'),
                    profit=Sum(ExpressionWrapper(
                        (F('unit_price') - F('product__purchase_price')) * F('quantity'),
                        output_field=DecimalField()
                    )),
                    count=Count('id')
                )
                .order_by('day')
            )

            sales_map = defaultdict(lambda: {'completed': {}, 'credit': {}})
            for s in sales:
                day = s['day'].date()
                status_key = 'completed' if s['status'] == 'COMPLETED' else 'credit'
                sales_map[day][status_key] = {
                    'revenue': s['revenue'] or Decimal(0),
                    'profit': s['profit'] or Decimal(0),
                    'count': s['count']
                }

            series = []
            current_datetime = timezone.now().replace(
                year=start_date.year,
                month=start_date.month,
                day=start_date.day,
                hour=0, minute=0, second=0, microsecond=0
            )
            end_datetime_series = timezone.now().replace(
                year=end_date.year,
                month=end_date.month,
                day=end_date.day,
                hour=0, minute=0, second=0, microsecond=0
            )

            while current_datetime <= end_datetime_series:
                series.append(current_datetime.date())
                current_datetime += timedelta(days=1)

            result = []
            for day in series:
                data = sales_map.get(day, {})
                result.append({
                    'date': timezone.make_aware(
                        datetime.combine(day, datetime.min.time()),
                        tz
                    ).isoformat(),
                    'completed': {
                        'revenue': float(data.get('completed', {}).get('revenue', 0)),
                        'profit': float(data.get('completed', {}).get('profit', 0)),
                        'count': data.get('completed', {}).get('count', 0)
                    },
                    'credit': {
                        'revenue': float(data.get('credit', {}).get('revenue', 0)),
                        'profit': float(data.get('credit', {}).get('profit', 0)),
                        'count': data.get('credit', {}).get('count', 0)
                    }
                })

            return ServiceResponse(success=True, data=result)

        except Exception as e:
            logger.error(f"Sales data error: {str(e)}", exc_info=True)
            return ServiceResponse(success=False, error=str(e))

    @staticmethod
    def get_top_selling_products(start_date, end_date) -> ServiceResponse:

        try:
            if not start_date or not end_date:
                today = timezone.now().date()
                start_date = today - timedelta(days=today.weekday())
                end_date = start_date + timedelta(days=6)

            lines = InvoiceLine.objects.filter(
                invoice__status__in=['COMPLETED', 'CREDIT'],
                invoice__created_at__date__range=[start_date, end_date]
            )
            # Top products query
            top_products = (
                lines
                .values('product__id', 'product__name')
                .annotate(
                    sold=Sum('quantity'),
                    revenue=Sum('line_total'),
                    profit=Sum(ExpressionWrapper(
                        (F('unit_price') - F('product__purchase_price')) * F('quantity'),
                        output_field=DecimalField()
                    ))
                )
                .order_by('-revenue')[:10]
            )

            # Top categories query
            top_categories = (
                lines
                .values('product__category__name')
                .annotate(
                    sold=Sum('quantity'),
                    revenue=Sum('line_total'),
                    profit=Sum(ExpressionWrapper(
                        (F('unit_price') - F('product__purchase_price')) * F('quantity'),
                        output_field=DecimalField()
                    ))
                )
                .order_by('-revenue')[:5]
            )

            # Format results
            data = {
                'top_products': [
                    {
                        'name': p['product__name'],
                        'sold': int(p['sold'] or 0),
                        'revenue': float(p['revenue']),
                        'profit': float(p['profit']),
                        'margin': round((float(p['profit']) / float(p['revenue'])) * 100, 1)
                        if p['revenue'] and float(p['revenue']) > 0 and p['profit'] else 0
                    }
                    for p in top_products
                ],
                'top_categories': [
                    {
                        'name': c['product__category__name'],
                        'sold': int(c['sold'] or 0),
                        'revenue': float(c['revenue']),
                        'profit': float(c['profit']),
                        'margin': round((float(c['profit']) / float(c['revenue'])) * 100, 1)
                        if c['revenue'] and float(c['revenue']) > 0 and c['profit'] else 0
                    }
                    for c in top_categories
                ]
            }

            return ServiceResponse(success=True, data=data)

        except Exception as e:
            logger.error(f"Products data error: {str(e)}", exc_info=True)
            return ServiceResponse(success=False, error=str(e))

    @staticmethod
    def get_inventory_data() -> ServiceResponse:
        """
        Get inventory status data for dashboard.

        Returns:
            ServiceResponse with inventory statistics and alerts
        """
        try:
            # Stock status overview
            in_stock = Product.objects.filter(quantity__gt=F('min_quantity')).count()
            low_stock = Product.objects.filter(
                quantity__gt=0,
                quantity__lte=F('min_quantity')
            ).count()
            out_of_stock = Product.objects.filter(quantity=0).count()
            overstocked = Product.objects.filter(quantity__gt=F('min_quantity') * 5).count()

            stock_status = [
                {'name': 'In Stock', 'value': in_stock, 'color': '#4CAF50'},
                {'name': 'Low Stock', 'value': low_stock, 'color': '#FF9800'},
                {'name': 'Out of Stock', 'value': out_of_stock, 'color': '#F44336'}
            ]

            # Get detailed product stock data
            products = Product.objects.all().select_related('category')
            stock_data = []

            for product in products:
                status = 'normal'
                if product.quantity == 0:
                    status = 'out_of_stock'
                elif product.quantity <= product.min_quantity:
                    status = 'low_stock'
                elif product.quantity > (product.min_quantity * 2):
                    status = 'overstocked'

                stock_data.append({
                    'id': product.id,
                    'name': product.name,
                    'category': product.category.name,
                    'quantity': product.quantity,
                    'min_quantity': product.min_quantity,
                    'status': status,
                    'status_text': 'En stock' if product.quantity > product.min_quantity else
                    'Stock faible' if product.quantity > 0 else 'Rupture de stock'
                })

            # Alerts and statistics
            alerts = {
                'lowStock': low_stock,
                'outOfStock': out_of_stock,
                'overstocked': overstocked,
                'total_products': len(products),
                'critical': Product.objects.filter(
                    Q(quantity=0) |
                    Q(quantity__lt=F('min_quantity') * 0.5, quantity__gt=0)
                ).count()
            }

            data = {
                'stockStatus': stock_status,
                'stockData': stock_data,
                'alerts': alerts
            }

            return ServiceResponse(success=True, data=data)

        except Exception as e:
            logger.error(f"Error in get_inventory_data: {str(e)}", exc_info=True)
            return ServiceResponse(success=False, error=str(e))

    @staticmethod
    def get_recent_sales(limit: int = 10) -> ServiceResponse:
        try:
            # Get recent completed invoices with related data
            recent_invoices = (
                Invoice.objects.filter(Q(status='COMPLETED') | Q(status='CREDIT'))
                .prefetch_related('lines__product')
                .annotate(
                    total_items=Sum('lines__quantity'),
                    invoice_total=Sum('lines__line_total'),
                    profit=Sum(
                        ExpressionWrapper(
                            (F('lines__unit_price') - F(
                                'lines__product__purchase_price')) * F('lines__quantity'),
                            output_field=DecimalField()
                        )
                    )
                )
                .order_by('-created_at')[:limit]
            )

            result = []
            for invoice in recent_invoices:
                top_items = [
                    {
                        'name': line.product.name,
                        'quantity': line.quantity,
                        'total': float(line.line_total)
                    }
                    for line in invoice.lines.all()[:10]
                ]

                result.append({
                    'invoice_id': invoice.id,
                    'invoice_number': invoice.number,
                    'status': invoice.status,
                    'date': invoice.created_at.isoformat(),
                    'formatted_date': invoice.created_at.strftime('%d %b %Y %H:%M'),
                    'customer': invoice.client_name if invoice.client_name else 'Anonymous',
                    'total': float(invoice.invoice_total),
                    'profit': float(invoice.profit),
                    'margin': round((float(
                        invoice.profit) / float(invoice.invoice_total)) * 100, 1)
                    if invoice.invoice_total > 0 else 0,
                    'items': invoice.total_items,
                    'top_items': top_items
                })

            return ServiceResponse(success=True, data=result)

        except Exception as e:
            logger.error(f"Error in get_recent_sales: {str(e)}", exc_info=True)
            return ServiceResponse(success=False, error=str(e))
