from __future__ import annotations

import calendar
import logging
from datetime import date
from datetime import timedelta
from decimal import Decimal
from typing import Any
from typing import Dict
from typing import List
from typing import Union

from django.core.cache import cache
from django.db.models import Avg
from django.db.models import Count
from django.db.models import DecimalField
from django.db.models import ExpressionWrapper
from django.db.models import F
from django.db.models import Q
from django.db.models import Sum
from django.db.models.functions import TruncDay
from django.db.models.functions import TruncMonth
from django.db.models.functions import TruncWeek
from django.db.models.functions import TruncYear
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

    CACHE_TIMEOUT = 3600  # 1 hour cache timeout

    # Périodes valides
    VALID_PERIODS = ['daily', 'weekly', 'monthly', 'yearly']

    @staticmethod
    def get_period_boundaries(period: str) -> Dict[str, Dict[str, date]]:
        """
        Calculate start and end dates for current and previous periods.

        Args:
            period: Type of period ('daily', 'weekly', 'monthly', 'yearly')

        Returns:
            Dictionary with current and previous period boundaries
        """
        today = timezone.now().date()
        data = {'current': {}, 'previous': {}}

        if period == 'daily':
            data['current'] = {'start': today, 'end': today}
            prev_day = today - timedelta(days=1)
            data['previous'] = {'start': prev_day, 'end': prev_day}

        elif period == 'weekly':
            start = today - timedelta(days=today.weekday())
            data['current'] = {'start': start, 'end': start + timedelta(days=6)}

            prev_start = start - timedelta(days=7)
            data['previous'] = {'start': prev_start, 'end': prev_start + timedelta(days=6)}

        elif period == 'monthly':
            start = today.replace(day=1)
            last_day = calendar.monthrange(today.year, today.month)[1]
            data['current'] = {'start': start, 'end': start.replace(day=last_day)}

            if today.month == 1:
                prev_start = date(today.year - 1, 12, 1)
                prev_end = date(today.year - 1, 12, 31)
            else:
                prev_month = today.month - 1
                prev_year = today.year
                prev_last_day = calendar.monthrange(prev_year, prev_month)[1]
                prev_start = date(prev_year, prev_month, 1)
                prev_end = date(prev_year, prev_month, prev_last_day)

            data['previous'] = {'start': prev_start, 'end': prev_end}

        elif period == 'yearly':
            data['current'] = {
                'start': date(today.year, 1, 1),
                'end': date(today.year, 12, 31)
            }
            data['previous'] = {
                'start': date(today.year - 1, 1, 1),
                'end': date(today.year - 1, 12, 31)
            }

        return data

    @staticmethod
    def generate_period_series(
            start_date: date, end_date: date, period: str
    ) -> List[Dict[str, Any]]:
        """
        Generate a series of time periods between start_date and end_date.

        Args:
            start_date: Start date of the range
            end_date: End date of the range
            period: Type of period ('daily', 'weekly', 'monthly', 'yearly')

        Returns:
            List of period objects with period date and formatted label
        """
        series = []
        current = start_date

        if period == 'daily':
            while current <= end_date:
                series.append({
                    'period': current,
                    'label': current.strftime('%d %b')
                })
                current += timedelta(days=1)

        elif period == 'weekly':
            # Ensure we start from Monday
            current = current - timedelta(days=current.weekday())
            while current <= end_date:
                series.append({
                    'period': current,
                    'label': f"Sem {current.strftime('%W')}"
                })
                current += timedelta(days=7)

        elif period == 'monthly':
            current = current.replace(day=1)
            while current <= end_date:
                series.append({
                    'period': current,
                    'label': current.strftime('%b %Y')
                })
                # Next month
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)

        elif period == 'yearly':
            current = current.replace(month=1, day=1)
            while current <= end_date:
                series.append({
                    'period': current,
                    'label': current.strftime('%Y')
                })
                current = current.replace(year=current.year + 1)

        if not series:
            return [{
                'period': start_date,
                'label': 'Aucune donnée',
                'zero_data': True
            }]

        return series

    @staticmethod
    def calculate_trend(current: float, previous: float) -> Dict[str, Union[str, float]]:
        """
        Calculate trend between current and previous values.

        Args:
            current: Current period value
            previous: Previous period value

        Returns:
            Dictionary with trend status, percentage and direction
        """
        # Handle edge cases
        if previous == 0:
            if current == 0:
                return {
                    'status': 'stable',
                    'percentage': 0,
                    'direction': 'equal'
                }
            else:
                return {
                    'status': 'up',
                    'percentage': 100,
                    'direction': 'up'
                }

        # Calculate percentage change
        percentage = ((current - previous) / abs(previous)) * 100

        # Determine trend direction
        if abs(percentage) < 0.1:
            status = 'stable'
            direction = 'equal'
        else:
            status = 'up' if percentage > 0 else 'down'
            direction = status

        return {
            'status': status,
            'percentage': round(abs(percentage), 1),
            'direction': direction
        }

    @staticmethod
    def get_dashboard_stats(period: str = 'monthly') -> ServiceResponse:
        """
        Get main KPI statistics for the dashboard.

        Args:
            period: Time period for aggregation ('daily', 'weekly', 'monthly', 'yearly')

        Returns:
            ServiceResponse with aggregated statistics data
        """
        try:
            if period not in DashboardService.VALID_PERIODS:
                return ServiceResponse(
                    success=False,
                    error=f"Invalid period: {period}."
                )

            cache_key = f'dashboard_stats_{period}_{timezone.now().date()}'
            cached_data = cache.get(cache_key)
            if cached_data:
                return ServiceResponse(success=True, data=cached_data)

            periods = DashboardService.get_period_boundaries(period)
            current = periods['current']
            previous = periods['previous']

            # Current period invoices
            current_completed = Invoice.objects.filter(
                status='COMPLETED',
                created_at__date__range=[current['start'], current['end']]
            )
            current_credit = Invoice.objects.filter(
                status='CREDIT',
                created_at__date__range=[current['start'], current['end']]
            )

            # Previous period invoices
            previous_completed = Invoice.objects.filter(
                status='COMPLETED',
                created_at__date__range=[previous['start'], previous['end']]
            )
            previous_credit = Invoice.objects.filter(
                status='CREDIT',
                created_at__date__range=[previous['start'], previous['end']]
            )

            # Current period revenue
            current_completed_revenue = InvoiceLine.objects.filter(
                invoice__in=current_completed
            ).aggregate(total=Sum('line_total'))['total'] or Decimal('0.00')

            current_credit_revenue = InvoiceLine.objects.filter(
                invoice__in=current_credit
            ).aggregate(total=Sum('line_total'))['total'] or Decimal('0.00')

            current_advance_paid = current_credit.aggregate(
                total=Sum('advance_paid'))['total'] or Decimal('0.00')

            current_remaining = current_credit.aggregate(
                total=Sum('_remaining_amount'))['total'] or Decimal('0.00')

            # Current period profit
            current_profit = InvoiceLine.objects.filter(
                invoice__in=current_completed
            ).aggregate(
                profit=Sum(ExpressionWrapper(
                    (F('unit_price') - F('product__purchase_price')) * F('quantity'),
                    output_field=DecimalField()
                ))
            )['profit'] or Decimal('0.00')

            current_credit_profit = InvoiceLine.objects.filter(
                invoice__in=current_credit
            ).aggregate(
                profit=Sum(ExpressionWrapper(
                    (F('unit_price') - F('product__purchase_price')) * F('quantity'),
                    output_field=DecimalField()
                ))
            )['profit'] or Decimal('0.00')

            # Previous period revenue
            previous_completed_revenue = InvoiceLine.objects.filter(
                invoice__in=previous_completed
            ).aggregate(total=Sum('line_total'))['total'] or Decimal('0.00')

            previous_credit_revenue = InvoiceLine.objects.filter(
                invoice__in=previous_credit
            ).aggregate(total=Sum('line_total'))['total'] or Decimal('0.00')

            # Previous period profit
            previous_profit = InvoiceLine.objects.filter(
                invoice__in=previous_completed
            ).aggregate(
                profit=Sum(ExpressionWrapper(
                    (F('unit_price') - F('product__purchase_price')) * F('quantity'),
                    output_field=DecimalField()
                ))
            )['profit'] or Decimal('0.00')

            previous_credit_profit = InvoiceLine.objects.filter(
                invoice__in=previous_credit
            ).aggregate(
                profit=Sum(ExpressionWrapper(
                    (F('unit_price') - F('product__purchase_price')) * F('quantity'),
                    output_field=DecimalField()
                ))
            )['profit'] or Decimal('0.00')

            # Calculate net values (completed - credits)
            current_net_revenue = current_completed_revenue - current_credit_revenue
            previous_net_revenue = previous_completed_revenue - previous_credit_revenue

            current_net_profit = current_profit - current_credit_profit
            previous_net_profit = previous_profit - previous_credit_profit

            # Calculate trends
            revenue_trend = DashboardService.calculate_trend(
                float(current_net_revenue),
                float(previous_net_revenue)
            )

            profit_trend = DashboardService.calculate_trend(
                float(current_net_profit),
                float(previous_net_profit)
            )

            orders_trend = DashboardService.calculate_trend(
                current_completed.count(),
                previous_completed.count()
            )

            data = {
                'revenue': {
                    'total': float(current_net_revenue),
                    'completed': float(current_completed_revenue),
                    'credit': {
                        'total': float(current_credit_revenue),
                        'advance_paid': float(current_advance_paid),
                        'to_collect': float(current_remaining),
                        'count': current_credit.count()
                    },
                    'advance_paid': float(current_advance_paid),
                    'outstanding': float(current_remaining),
                    'trend': revenue_trend
                },
                'profit': {
                    'total': float(current_net_profit),
                    'completed': float(current_profit),
                    'credit': float(current_credit_profit),
                    'trend': profit_trend
                },
                'orders': {
                    'total': current_completed.count() + current_credit.count(),
                    'completed': current_completed.count(),
                    'credit': current_credit.count(),
                    'trend': orders_trend
                }
            }

            cache.set(cache_key, data, DashboardService.CACHE_TIMEOUT)
            return ServiceResponse(success=True, data=data)

        except Exception as e:
            logger.error(f"Error in get_dashboard_stats: {str(e)}", exc_info=True)
            return ServiceResponse(success=False, error=str(e))

    @staticmethod
    def get_sales_data(period: str = 'monthly') -> ServiceResponse:
        """
        Fetch dashboard sales data for time series visualization.

        Args:
            period: Time period for aggregation ('daily', 'weekly', 'monthly', 'yearly')

        Returns:
            ServiceResponse with sales data aggregated by period
        """
        try:
            cache_key = f'sales_data_{period}_{timezone.now().date()}'
            cached_data = cache.get(cache_key)
            if cached_data:
                return ServiceResponse(success=True, data=cached_data)

            periods = DashboardService.get_period_boundaries(period)
            series = DashboardService.generate_period_series(
                periods['current']['start'],
                periods['current']['end'],
                period
            )

            trunc_func = {
                'daily': TruncDay,
                'weekly': TruncWeek,
                'monthly': TruncMonth,
                'yearly': TruncYear
            }.get(period, TruncDay)

            # Fetch data with appropriate time truncation
            completed_data = (
                InvoiceLine.objects.filter(
                    invoice__status='COMPLETED',
                    invoice__created_at__date__range=[
                        periods['current']['start'],
                        periods['current']['end']
                    ]
                )
                .annotate(period=trunc_func('invoice__created_at'))
                .values('period')
                .annotate(
                    revenue=Sum('line_total'),
                    profit=Sum(ExpressionWrapper(
                        (F('unit_price') - F('product__purchase_price')) * F('quantity'),
                        output_field=DecimalField()
                    )),
                    count=Count('id')
                )
            )

            credit_data = (
                InvoiceLine.objects.filter(
                    invoice__status='CREDIT',
                    invoice__created_at__date__range=[
                        periods['current']['start'],
                        periods['current']['end']
                    ]
                )
                .annotate(period=trunc_func('invoice__created_at'))
                .values('period')
                .annotate(
                    revenue=Sum('line_total'),
                    profit=Sum(ExpressionWrapper(
                        (F('unit_price') - F('product__purchase_price')) * F('quantity'),
                        output_field=DecimalField()
                    )),
                    count=Count('id')
                )
            )

            # Format results for each period in the series
            result = []
            for entry in series:
                period_date = entry['period']
                period_label = entry['label']

                # Match completed data for this period
                completed = next(
                    (x for x in completed_data if x['period'].date() == period_date),
                    {'revenue': Decimal('0.00'), 'profit': Decimal('0.00'), 'count': 0}
                )

                # Match credit data for this period
                credit = next(
                    (x for x in credit_data if x['period'].date() == period_date),
                    {'revenue': Decimal('0.00'), 'profit': Decimal('0.00'), 'count': 0}
                )

                # Calculate net values and add to result
                result.append({
                    'period': period_label,
                    'date': period_date.isoformat(),
                    'completed': {
                        'revenue': float(completed['revenue']),
                        'profit': float(completed['profit']),
                        'count': completed['count']
                    },
                    'credit': {
                        'revenue': float(credit['revenue']),
                        'profit': float(credit['profit']),
                        'count': credit['count']
                    },
                    'total': {
                        'revenue': float(completed['revenue'] - credit['revenue']),
                        'profit': float(completed['profit'] - credit['profit']),
                        'count': completed['count'] + credit['count']
                    }
                })

            cache.set(cache_key, result, DashboardService.CACHE_TIMEOUT)
            return ServiceResponse(success=True, data=result)

        except Exception as e:
            logger.error(f"Sales data error: {str(e)}", exc_info=True)
            return ServiceResponse(success=False, error=str(e))

    @staticmethod
    def get_products_data(period: str = 'monthly') -> ServiceResponse:
        """
        Get product performance data for the dashboard.

        Args:
            period: Time period for aggregation ('daily', 'weekly', 'monthly', 'yearly')

        Returns:
            ServiceResponse with top products and categories data
        """
        try:
            cache_key = f'products_data_{period}_{timezone.now().date()}'
            cached_data = cache.get(cache_key)
            if cached_data:
                return ServiceResponse(success=True, data=cached_data)

            periods = DashboardService.get_period_boundaries(period)

            # Top products query
            top_products = (
                InvoiceLine.objects.filter(
                    invoice__status='COMPLETED',
                    invoice__created_at__date__range=[
                        periods['current']['start'],
                        periods['current']['end']
                    ]
                )
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
                InvoiceLine.objects.filter(
                    invoice__status='COMPLETED',
                    invoice__created_at__date__range=[
                        periods['current']['start'],
                        periods['current']['end']
                    ]
                )
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
                        'sold': p['sold'],
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
                        'sold': c['sold'],
                        'revenue': float(c['revenue']),
                        'profit': float(c['profit']),
                        'margin': round((float(c['profit']) / float(c['revenue'])) * 100, 1)
                        if c['revenue'] and float(c['revenue']) > 0 and c['profit'] else 0
                    }
                    for c in top_categories
                ]
            }

            cache.set(cache_key, data, DashboardService.CACHE_TIMEOUT)
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
            cache_key = f'inventory_data_{timezone.now().date()}'
            cached_data = cache.get(cache_key)
            if cached_data:
                return ServiceResponse(success=True, data=cached_data)

            # Stock status overview
            in_stock = Product.objects.filter(quantity__gt=F('min_quantity')).count()
            low_stock = Product.objects.filter(
                quantity__gt=0,
                quantity__lte=F('min_quantity')
            ).count()
            out_of_stock = Product.objects.filter(quantity=0).count()
            overstocked = Product.objects.filter(quantity__gt=F('min_quantity') * 2).count()

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

            cache.set(cache_key, data, DashboardService.CACHE_TIMEOUT)
            return ServiceResponse(success=True, data=data)

        except Exception as e:
            logger.error(f"Error in get_inventory_data: {str(e)}", exc_info=True)
            return ServiceResponse(success=False, error=str(e))

    @staticmethod
    def invalidate_cache():
        """
        Invalidate all dashboard cache keys.
        Should be called after significant data changes.
        """
        try:
            today = timezone.now().date()
            for period in DashboardService.VALID_PERIODS:
                cache.delete(f'dashboard_stats_{period}_{today}')
                cache.delete(f'sales_data_{period}_{today}')
                cache.delete(f'products_data_{period}_{today}')

            cache.delete(f'inventory_data_{today}')
            return ServiceResponse(success=True, data={'Cache invalidated successfully'})
        except Exception as e:
            logger.error(f"Error invalidating cache: {str(e)}", exc_info=True)
            return ServiceResponse(success=False, error=str(e))

    @staticmethod
    def get_recent_sales(limit: int = 10) -> ServiceResponse:
        try:
            cache_key = f'recent_sales_{limit}_{timezone.now().date()}'
            cached_data = cache.get(cache_key)
            if cached_data:
                return ServiceResponse(success=True, data=cached_data)

            # Get recent completed invoices with related data
            recent_invoices = (
                Invoice.objects.filter(status='COMPLETED')
                .prefetch_related('lines', 'lines__product')
                .order_by('-created_at')[:limit]
            )

            result = []
            for invoice in recent_invoices:
                invoice_total = sum(line.line_total for line in invoice.lines.all())
                profit = sum(
                    (line.unit_price - line.product.purchase_price) * line.quantity
                    for line in invoice.lines.all()
                )
                item_count = sum(line.quantity for line in invoice.lines.all())
                top_items = [
                    {
                        'name': line.product.name,
                        'quantity': line.quantity,
                        'total': float(line.line_total)
                    }
                    for line in invoice.lines.all()[:3]
                ]

                result.append({
                    'invoice_id': invoice.id,
                    'invoice_number': invoice.number,
                    'date': invoice.created_at.isoformat(),
                    'formatted_date': invoice.created_at.strftime('%d %b %Y %H:%M'),
                    'customer': invoice.client_name if invoice.client_name else 'Anonymous',
                    'total': float(invoice_total),
                    'profit': float(profit),
                    'margin': round((float(profit) / float(
                        invoice_total)) * 100, 1) if invoice_total > 0 else 0,
                    'items': item_count,
                    'top_items': top_items
                })

            cache.set(cache_key, result, DashboardService.CACHE_TIMEOUT)
            return ServiceResponse(success=True, data=result)

        except Exception as e:
            logger.error(f"Error in get_recent_sales: {str(e)}", exc_info=True)
            return ServiceResponse(success=False, error=str(e))

    @staticmethod
    def get_top_selling_products(period: str = 'monthly', limit: int = 10) -> ServiceResponse:
        try:
            if period not in DashboardService.VALID_PERIODS:
                return ServiceResponse(
                    success=False,
                    error=f"Invalid period: {period}."
                )

            cache_key = f'top_selling_products_{period}_{limit}_{timezone.now().date()}'
            cached_data = cache.get(cache_key)
            if cached_data:
                return ServiceResponse(success=True, data=cached_data)

            periods = DashboardService.get_period_boundaries(period)

            # Get top selling products by quantity
            top_products = (
                InvoiceLine.objects.filter(
                    invoice__status='COMPLETED',
                    invoice__created_at__date__range=[
                        periods['current']['start'],
                        periods['current']['end']
                    ]
                )
                .values('product__id', 'product__name', 'product__category__name')
                .annotate(
                    total_sold=Sum('quantity'),
                    revenue=Sum('line_total'),
                    profit=Sum(ExpressionWrapper(
                        (F('unit_price') - F('product__purchase_price')) * F('quantity'),
                        output_field=DecimalField()
                    )),
                    avg_price=Avg('unit_price'),
                    sale_count=Count('invoice', distinct=True)
                )
                .order_by('-total_sold')[:limit]
            )

            previous_period_data = (
                InvoiceLine.objects.filter(
                    invoice__status='COMPLETED',
                    invoice__created_at__date__range=[
                        periods['previous']['start'],
                        periods['previous']['end']
                    ]
                )
                .values('product__id')
                .annotate(
                    total_sold=Sum('quantity')
                )
            )

            # Create lookup dictionary for previous period
            prev_data_lookup = {
                item['product__id']: item['total_sold']
                for item in previous_period_data
            }

            # Format results with trend calculations
            result = []
            for product in top_products:
                product_id = product['product__id']
                current_sold = product['total_sold']
                previous_sold = prev_data_lookup.get(product_id, 0)

                # Calculate trend
                trend = DashboardService.calculate_trend(
                    float(current_sold),
                    float(previous_sold)
                )

                result.append({
                    'id': product_id,
                    'name': product['product__name'],
                    'category': product['product__category__name'],
                    'quantity_sold': current_sold,
                    'revenue': float(product['revenue']),
                    'profit': float(product['profit']),
                    'margin': round((float(product['profit']) / float(
                        product['revenue'])) * 100, 1) if product['revenue'] and float(
                        product['revenue']) > 0 else 0,
                    'avg_price': float(product['avg_price']),
                    'sale_count': product['sale_count'],
                    'trend': trend
                })

            cache.set(cache_key, result, DashboardService.CACHE_TIMEOUT)
            return ServiceResponse(success=True, data=result)

        except Exception as e:
            logger.error(f"Error in get_top_selling_products: {str(e)}", exc_info=True)
            return ServiceResponse(success=False, error=str(e))
