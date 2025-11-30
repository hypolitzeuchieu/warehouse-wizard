"""Dashboard repository implementations."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from django.db import models
from django.db.models import Count, Sum
from django.db.models.functions import TruncDay
from django.utils import timezone

from domain.dashboard.repositories import (
    DashboardCashierStatisticsRepository,
    DashboardCategoryStatisticsRepository,
    DashboardMetricsRepository,
    DashboardProductStatisticsRepository,
    DashboardSubCategoryStatisticsRepository,
)
from infrastructure.persistence.models.business_models import BusinessMember as BusinessMemberModel
from infrastructure.persistence.models.credit_models import Credit as CreditModel
from infrastructure.persistence.models.customer_models import Customer as CustomerModel
from infrastructure.persistence.models.finance_models import Expense as ExpenseModel
from infrastructure.persistence.models.finance_models import Payroll as PayrollModel
from infrastructure.persistence.models.inventory_models import (
    Category as CategoryModel,
)
from infrastructure.persistence.models.inventory_models import (
    Product as ProductModel,
)
from infrastructure.persistence.models.inventory_models import (
    SubCategory as SubCategoryModel,
)
from infrastructure.persistence.models.sales_models import Invoice as InvoiceModel
from infrastructure.persistence.models.sales_models import InvoiceLine as InvoiceLineModel
from infrastructure.persistence.models.user_models import RetailPulseUser as UserModel

logger = logging.getLogger(__name__)


class DashboardMetricsRepositoryImpl(DashboardMetricsRepository):
    """Django implementation of DashboardMetricsRepository."""

    def aggregate_revenue_metrics(
        self,
        business_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Decimal | int]:
        """Implement revenue aggregation using Django ORM."""
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=now.weekday())
        month_start = today_start.replace(day=1)
        year_start = today_start.replace(month=1, day=1)

        filter_start = start_date or year_start
        filter_end = end_date or now

        base_query = InvoiceModel.objects.filter(
            business_id=business_id,
            status="COMPLETED",
            is_archived=False,
            created_at__gte=filter_start,
            created_at__lte=filter_end,
        )

        total_stats = base_query.aggregate(
            total_revenue=Sum("total"),
            total_orders=Count("id"),
        )
        total_revenue = Decimal(str(total_stats["total_revenue"] or 0))
        total_orders = total_stats["total_orders"] or 0

        today_stats = base_query.filter(created_at__gte=today_start).aggregate(
            revenue_today=Sum("total"),
            orders_today=Count("id"),
        )
        revenue_today = Decimal(str(today_stats["revenue_today"] or 0))
        orders_today = today_stats["orders_today"] or 0

        week_stats = base_query.filter(created_at__gte=week_start).aggregate(
            revenue_this_week=Sum("total"),
            orders_this_week=Count("id"),
        )
        revenue_this_week = Decimal(str(week_stats["revenue_this_week"] or 0))
        orders_this_week = week_stats["orders_this_week"] or 0

        month_stats = base_query.filter(created_at__gte=month_start).aggregate(
            revenue_this_month=Sum("total"),
            orders_this_month=Count("id"),
        )
        revenue_this_month = Decimal(str(month_stats["revenue_this_month"] or 0))
        orders_this_month = month_stats["orders_this_month"] or 0

        year_stats = base_query.filter(created_at__gte=year_start).aggregate(
            revenue_this_year=Sum("total"),
        )
        revenue_this_year = Decimal(str(year_stats["revenue_this_year"] or 0))

        average_order_value = total_revenue / total_orders if total_orders > 0 else Decimal("0.00")

        logger.info(
            f"Revenue metrics calculated for business {business_id}: "
            f"total={total_revenue}, today={revenue_today}"
        )

        return {
            "total_revenue": total_revenue,
            "revenue_today": revenue_today,
            "revenue_this_week": revenue_this_week,
            "revenue_this_month": revenue_this_month,
            "revenue_this_year": revenue_this_year,
            "average_order_value": average_order_value,
            "total_orders": total_orders,
            "orders_today": orders_today,
            "orders_this_week": orders_this_week,
            "orders_this_month": orders_this_month,
        }

    def aggregate_expense_metrics(
        self,
        business_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Decimal]:
        """Implement expense aggregation using Django ORM."""
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=now.weekday())
        month_start = today_start.replace(day=1)
        year_start = today_start.replace(month=1, day=1)

        filter_start = start_date or year_start
        filter_end = end_date or now

        total_expenses = Decimal("0.00")
        expenses_today = Decimal("0.00")
        expenses_this_week = Decimal("0.00")
        expenses_this_month = Decimal("0.00")
        expenses_this_year = Decimal("0.00")
        salary_expenses = Decimal("0.00")
        other_expenses = Decimal("0.00")

        # Get expenses using SQL aggregations
        base_expense_query = ExpenseModel.objects.filter(
            business_id=business_id,
            created_at__gte=filter_start,
            created_at__lte=filter_end,
        )

        total_expense_stats = base_expense_query.aggregate(total=Sum("amount"))
        other_expenses = Decimal(str(total_expense_stats["total"] or 0))
        total_expenses += other_expenses

        today_expense = base_expense_query.filter(created_at__gte=today_start).aggregate(
            total=Sum("amount")
        )
        expenses_today += Decimal(str(today_expense["total"] or 0))

        week_expense = base_expense_query.filter(created_at__gte=week_start).aggregate(
            total=Sum("amount")
        )
        expenses_this_week += Decimal(str(week_expense["total"] or 0))

        month_expense = base_expense_query.filter(created_at__gte=month_start).aggregate(
            total=Sum("amount")
        )
        expenses_this_month += Decimal(str(month_expense["total"] or 0))

        year_expense = base_expense_query.filter(created_at__gte=year_start).aggregate(
            total=Sum("amount")
        )
        expenses_this_year += Decimal(str(year_expense["total"] or 0))

        base_payroll_query = PayrollModel.objects.filter(
            business_id=business_id,
            payment_date__gte=filter_start,
            payment_date__lte=filter_end,
        )

        total_payroll_stats = base_payroll_query.aggregate(total=Sum("net_amount"))
        salary_expenses = Decimal(str(total_payroll_stats["total"] or 0))
        total_expenses += salary_expenses

        today_payroll = base_payroll_query.filter(payment_date__gte=today_start).aggregate(
            total=Sum("net_amount")
        )
        expenses_today += Decimal(str(today_payroll["total"] or 0))

        week_payroll = base_payroll_query.filter(payment_date__gte=week_start).aggregate(
            total=Sum("net_amount")
        )
        expenses_this_week += Decimal(str(week_payroll["total"] or 0))

        month_payroll = base_payroll_query.filter(payment_date__gte=month_start).aggregate(
            total=Sum("net_amount")
        )
        expenses_this_month += Decimal(str(month_payroll["total"] or 0))

        year_payroll = base_payroll_query.filter(payment_date__gte=year_start).aggregate(
            total=Sum("net_amount")
        )
        expenses_this_year += Decimal(str(year_payroll["total"] or 0))

        logger.info(f"Expense metrics calculated for business {business_id}")

        return {
            "total_expenses": total_expenses,
            "expenses_today": expenses_today,
            "expenses_this_week": expenses_this_week,
            "expenses_this_month": expenses_this_month,
            "expenses_this_year": expenses_this_year,
            "salary_expenses": salary_expenses,
            "other_expenses": other_expenses,
        }

    def aggregate_daily_metrics(
        self,
        business_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Implement daily aggregation using TruncDay."""
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        daily_invoices = (
            InvoiceModel.objects.filter(
                business_id=business_id,
                is_archived=False,
                created_at__gte=start_date,
                created_at__lte=end_date,
            )
            .annotate(day=TruncDay("created_at"))
            .values("day", "status")
            .annotate(
                total_revenue=Sum("total"),
                count=Count("id"),
                credit_revenue=Sum("remaining_amount"),
            )
            .order_by("day")
        )

        daily_expenses = (
            ExpenseModel.objects.filter(
                business_id=business_id,
                created_at__gte=start_date,
                created_at__lte=end_date,
            )
            .annotate(day=TruncDay("created_at"))
            .values("day")
            .annotate(total_expenses=Sum("amount"))
            .order_by("day")
        )

        daily_payroll = (
            PayrollModel.objects.filter(
                business_id=business_id,
                payment_date__gte=start_date,
                payment_date__lte=end_date,
            )
            .annotate(day=TruncDay("payment_date"))
            .values("day")
            .annotate(total_payroll=Sum("net_amount"))
            .order_by("day")
        )

        daily_credits = (
            CreditModel.objects.filter(
                business_id=business_id,
                created_at__gte=start_date,
                created_at__lte=end_date,
            )
            .annotate(day=TruncDay("created_at"))
            .values("day")
            .annotate(credit_outstanding=Sum("remaining_amount"))
            .order_by("day")
        )

        daily_map: dict[date, dict[str, Decimal | int]] = {}

        current_date = start_date.date()
        end_date_only = end_date.date()
        while current_date <= end_date_only:
            daily_map[current_date] = {
                "complete_revenue": Decimal("0.00"),
                "credit_revenue": Decimal("0.00"),
                "total_revenue": Decimal("0.00"),
                "total_sales": 0,
                "total_expenses": Decimal("0.00"),
                "credit_outstanding": Decimal("0.00"),
            }
            current_date += timedelta(days=1)

        for row in daily_invoices:
            day = row["day"].date()
            status = row["status"]
            revenue = Decimal(str(row["total_revenue"] or 0))
            count = row["count"] or 0
            credit_rev = Decimal(str(row["credit_revenue"] or 0))

            if day not in daily_map:
                daily_map[day] = {
                    "complete_revenue": Decimal("0.00"),
                    "credit_revenue": Decimal("0.00"),
                    "total_revenue": Decimal("0.00"),
                    "total_sales": 0,
                    "total_expenses": Decimal("0.00"),
                    "credit_outstanding": Decimal("0.00"),
                }

            if status == "COMPLETED":
                daily_map[day]["complete_revenue"] += revenue
                daily_map[day]["total_revenue"] += revenue
            elif status == "CREDIT":
                daily_map[day]["credit_revenue"] += credit_rev
                daily_map[day]["total_revenue"] += revenue

            daily_map[day]["total_sales"] += count

        for row in daily_expenses:
            day = row["day"].date()
            expenses = Decimal(str(row["total_expenses"] or 0))
            if day in daily_map:
                daily_map[day]["total_expenses"] += expenses

        for row in daily_payroll:
            day = row["day"].date()
            payroll = Decimal(str(row["total_payroll"] or 0))
            if day in daily_map:
                daily_map[day]["total_expenses"] += payroll

        for row in daily_credits:
            day = row["day"].date()
            credit = Decimal(str(row["credit_outstanding"] or 0))
            if day in daily_map:
                daily_map[day]["credit_outstanding"] += credit

        result = []
        for day, metrics in sorted(daily_map.items()):
            day_datetime = datetime.combine(day, datetime.min.time())
            if timezone.is_naive(day_datetime):
                day_datetime = timezone.make_aware(day_datetime)
            result.append(
                {
                    "date": day_datetime,
                    "complete_revenue": Decimal(str(metrics["complete_revenue"])).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    ),
                    "credit_revenue": Decimal(str(metrics["credit_revenue"])).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    ),
                    "total_revenue": Decimal(str(metrics["total_revenue"])).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    ),
                    "total_sales": metrics["total_sales"],
                    "total_expenses": Decimal(str(metrics["total_expenses"])).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    ),
                    "credit_outstanding": Decimal(str(metrics["credit_outstanding"])).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    ),
                }
            )

        logger.info(f"Daily metrics calculated for {len(result)} days for business {business_id}")
        return result

    def aggregate_daily_profits(
        self,
        business_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Implement daily profit aggregation."""
        daily_cogs = (
            InvoiceLineModel.objects.filter(
                invoice__business_id=business_id,
                invoice__is_archived=False,
                invoice__created_at__gte=start_date,
                invoice__created_at__lte=end_date,
            )
            .select_related("product")
            .annotate(day=TruncDay("invoice__created_at"))
            .values("day")
            .annotate(
                total_cost=Sum(
                    models.F("product__purchase_price") * models.F("quantity"),
                    output_field=models.DecimalField(),
                )
            )
            .order_by("day")
        )

        cost_map: dict[date, Decimal] = {}
        for row in daily_cogs:
            day = row["day"].date()
            cost = Decimal(str(row["total_cost"] or 0))
            cost_map[day] = cost

        daily_metrics = self.aggregate_daily_metrics(business_id, start_date, end_date)

        result = []
        for day_data in daily_metrics:
            day_date = day_data["date"].date()
            total_revenue = day_data["total_revenue"]
            total_expenses = day_data["total_expenses"]
            cost = cost_map.get(day_date, Decimal("0.00"))

            gross_profit = total_revenue - cost
            net_profit = total_revenue - total_expenses

            day_data["gross_profit"] = gross_profit.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            day_data["net_profit"] = net_profit.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            day_data["profit"] = net_profit.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            result.append(day_data)

        return result

    def get_top_products(
        self,
        business_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Implement top products aggregation."""
        top_products_raw = (
            InvoiceLineModel.objects.filter(
                invoice__business_id=business_id,
                invoice__is_archived=False,
                invoice__status="COMPLETED",
                **(
                    {}
                    if start_date is None or end_date is None
                    else {
                        "invoice__created_at__gte": start_date,
                        "invoice__created_at__lte": end_date,
                    }
                ),
            )
            .select_related("product")
            .values("product_id", "product__name", "product__quantity")
            .annotate(
                total_sold=Sum("quantity"),
                total_revenue=Sum("line_total"),
            )
            .order_by("-total_revenue")[:limit]
        )

        top_products = []
        for row in top_products_raw:
            top_products.append(
                {
                    "product_id": row["product_id"],
                    "product_name": row["product__name"] or "Unknown",
                    "total_sold": row["total_sold"] or 0,
                    "total_revenue": Decimal(str(row["total_revenue"] or 0)).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    ),
                    "quantity_available": row["product__quantity"] or 0,
                }
            )

        logger.info(f"Top {len(top_products)} products calculated for business {business_id}")
        return top_products

    def get_top_categories(
        self,
        business_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Implement top categories aggregation."""
        if start_date is None or end_date is None:
            return []

        category_sales = (
            InvoiceLineModel.objects.filter(
                invoice__business_id=business_id,
                invoice__is_archived=False,
                invoice__status="COMPLETED",
                invoice__created_at__gte=start_date,
                invoice__created_at__lte=end_date,
            )
            .select_related("product__category")
            .values("product__category_id", "product__category__name")
            .annotate(
                total_revenue=Sum("line_total"),
                total_quantity=Sum("quantity"),
                sales_count=Count("invoice_id", distinct=True),
            )
            .order_by("-total_revenue")[:limit]
        )

        top_categories = []
        for row in category_sales:
            top_categories.append(
                {
                    "category_id": row["product__category_id"],
                    "category_name": row["product__category__name"] or "Unknown",
                    "total_revenue": Decimal(str(row["total_revenue"] or 0)).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    ),
                    "total_quantity_sold": row["total_quantity"] or 0,
                    "number_of_sales": row["sales_count"] or 0,
                }
            )

        logger.info(f"Top {len(top_categories)} categories calculated for business {business_id}")
        return top_categories

    def get_recent_sales(
        self,
        business_id: UUID,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Implement recent sales retrieval."""
        invoices = (
            InvoiceModel.objects.filter(business_id=business_id, is_archived=False)
            .only("id", "number", "customer_name", "total", "status", "created_at")
            .order_by("-created_at")[:limit]
        )

        recent_sales = []
        for invoice in invoices:
            recent_sales.append(
                {
                    "invoice_id": invoice.id,
                    "invoice_number": invoice.number,
                    "customer_name": invoice.customer_name,
                    "total": invoice.total,
                    "status": invoice.status,
                    "created_at": invoice.created_at,
                }
            )

        logger.info(f"Recent {len(recent_sales)} sales retrieved for business {business_id}")
        return recent_sales

    def get_inventory_metrics(
        self,
        business_id: UUID,
    ) -> dict[str, int | Decimal]:
        """Implement inventory metrics aggregation."""
        products_query = ProductModel.objects.filter(business_id=business_id)

        total_products = products_query.count()

        low_stock_products = products_query.filter(
            models.Q(quantity__lte=models.F("min_quantity"))
        ).count()

        expired_products = products_query.filter(is_expired=True).count()

        products_on_promotion = products_query.filter(on_promotion=True).count()

        inventory_value_stats = products_query.aggregate(
            total_value=Sum(models.F("purchase_price") * models.F("quantity"))
        )
        total_inventory_value = Decimal(str(inventory_value_stats["total_value"] or 0))

        logger.info(
            f"Inventory metrics calculated: total={total_products}, "
            f"low_stock={low_stock_products}, expired={expired_products}"
        )

        return {
            "total_products": total_products,
            "low_stock_products": low_stock_products,
            "expired_products": expired_products,
            "total_inventory_value": total_inventory_value,
            "products_on_promotion": products_on_promotion,
        }

    def get_customer_metrics(
        self,
        business_id: UUID,
    ) -> dict[str, int]:
        """Implement customer metrics aggregation."""
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=now.weekday())
        month_start = today_start.replace(day=1)

        customers_query = CustomerModel.objects.filter(business_id=business_id)

        total_customers = customers_query.count()
        new_customers_today = customers_query.filter(created_at__gte=today_start).count()
        new_customers_this_week = customers_query.filter(created_at__gte=week_start).count()
        new_customers_this_month = customers_query.filter(created_at__gte=month_start).count()

        active_threshold = now - timedelta(days=30)
        active_customers = (
            InvoiceModel.objects.filter(
                business_id=business_id,
                status="COMPLETED",
                is_archived=False,
                created_at__gte=active_threshold,
            )
            .exclude(customer_id__isnull=True)
            .values("customer_id")
            .distinct()
            .count()
        )

        logger.info(f"Customer metrics calculated for business {business_id}")

        return {
            "total_customers": total_customers,
            "new_customers_today": new_customers_today,
            "new_customers_this_week": new_customers_this_week,
            "new_customers_this_month": new_customers_this_month,
            "active_customers": active_customers,
        }

    def get_credit_metrics(
        self,
        business_id: UUID,
    ) -> dict[str, Decimal | int]:
        """Implement credit metrics aggregation."""
        credits = CreditModel.objects.filter(
            business_id=business_id,
            remaining_amount__gt=0,
        )

        overdue_credits = CreditModel.objects.filter(
            business_id=business_id,
            remaining_amount__gt=0,
            due_date__lt=timezone.now(),
        )

        total_credit_amount = sum(c.remaining_amount for c in credits)
        overdue_credit_amount = sum(c.remaining_amount for c in overdue_credits)
        total_credits = credits.count()

        return {
            "total_credit_amount": total_credit_amount,
            "overdue_credit_amount": overdue_credit_amount,
            "total_credits": total_credits,
        }

    def calculate_profit_metrics(
        self,
        business_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Decimal]:
        """Calculate profit metrics from revenue and expense metrics."""
        revenue_metrics = self.aggregate_revenue_metrics(business_id, start_date, end_date)
        expense_metrics = self.aggregate_expense_metrics(business_id, start_date, end_date)

        total_revenue = Decimal(str(revenue_metrics["total_revenue"]))
        total_expenses = expense_metrics["total_expenses"]

        total_profit = total_revenue - total_expenses
        profit_today = (
            Decimal(str(revenue_metrics["revenue_today"])) - expense_metrics["expenses_today"]
        )
        profit_this_week = (
            Decimal(str(revenue_metrics["revenue_this_week"]))
            - expense_metrics["expenses_this_week"]
        )
        profit_this_month = (
            Decimal(str(revenue_metrics["revenue_this_month"]))
            - expense_metrics["expenses_this_month"]
        )

        profit_margin = (
            (total_profit / total_revenue * 100) if total_revenue > 0 else Decimal("0.00")
        )

        logger.info(f"Profit metrics calculated: total_profit={total_profit}")

        return {
            "total_profit": total_profit,
            "profit_today": profit_today,
            "profit_this_week": profit_this_week,
            "profit_this_month": profit_this_month,
            "profit_margin_percentage": profit_margin,
        }

    def calculate_trends(
        self,
        current_value: Decimal,
        previous_value: Decimal,
        previous_period_start: datetime,
        previous_period_end: datetime,
    ) -> dict[str, Any]:
        """Calculate trends comparison between current and previous period."""
        change_amount = current_value - previous_value
        if previous_value > 0:
            change_percentage = (change_amount / previous_value) * 100
        else:
            change_percentage = Decimal("100.00") if current_value > 0 else Decimal("0.00")

        if change_percentage > Decimal("5.00"):
            trend_direction = "up"
        elif change_percentage < Decimal("-5.00"):
            trend_direction = "down"
        else:
            trend_direction = "stable"

        return {
            "previous_period_start": previous_period_start,
            "previous_period_end": previous_period_end,
            "current_value": current_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "previous_value": previous_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "change_amount": change_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "change_percentage": change_percentage.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            "trend_direction": trend_direction,
        }

    def get_business_overview_metrics(
        self,
        business_id: UUID,
    ) -> dict[str, Any]:
        """Get business overview metrics (lifetime)."""
        from infrastructure.persistence.models.business_models import Business as BusinessModel

        business = BusinessModel.objects.filter(id=business_id).first()
        business_created_at = business.created_at if business else timezone.now()

        total_customers = CustomerModel.objects.filter(business_id=business_id).count()

        total_members = BusinessMemberModel.objects.filter(business_id=business_id).count()
        active_members = BusinessMemberModel.objects.filter(
            business_id=business_id, is_active=True, left_at__isnull=True
        ).count()

        total_products = ProductModel.objects.filter(business_id=business_id).count()

        total_categories = CategoryModel.objects.filter(business_id=business_id).count()

        total_subcategories = SubCategoryModel.objects.filter(business_id=business_id).count()

        lifetime_revenue_stats = InvoiceModel.objects.filter(
            business_id=business_id,
            status="COMPLETED",
            is_archived=False,
        ).aggregate(
            total_revenue=Sum("total"),
            total_invoices=Count("id"),
        )
        lifetime_revenue = Decimal(str(lifetime_revenue_stats["total_revenue"] or 0))
        total_invoices_completed = lifetime_revenue_stats["total_invoices"] or 0

        lifetime_credit_stats = CreditModel.objects.filter(business_id=business_id).aggregate(
            total_credit=Sum("remaining_amount"),
        )
        lifetime_credit = Decimal(str(lifetime_credit_stats["total_credit"] or 0))

        total_invoices = InvoiceModel.objects.filter(
            business_id=business_id, is_archived=False
        ).count()

        total_invoices_credit = InvoiceModel.objects.filter(
            business_id=business_id,
            status="CREDIT",
            is_archived=False,
        ).count()

        average_invoice_value = (
            lifetime_revenue / total_invoices_completed
            if total_invoices_completed > 0
            else Decimal("0.00")
        )

        lifetime_expenses_stats = ExpenseModel.objects.filter(business_id=business_id).aggregate(
            total_expenses=Sum("amount")
        )

        lifetime_expenses = Decimal(str(lifetime_expenses_stats["total_expenses"] or 0))

        lifetime_payroll_stats = PayrollModel.objects.filter(business_id=business_id).aggregate(
            total_payroll=Sum("net_amount")
        )

        lifetime_expenses += Decimal(str(lifetime_payroll_stats["total_payroll"] or 0))

        lifetime_profit = lifetime_revenue - lifetime_expenses

        inventory_value_stats = ProductModel.objects.filter(business_id=business_id).aggregate(
            total_value=Sum(
                models.F("quantity") * models.F("purchase_price"),
                output_field=models.DecimalField(),
            )
        )
        total_inventory_value = Decimal(str(inventory_value_stats["total_value"] or 0))

        logger.info(
            f"Business overview metrics calculated for business {business_id}: "
            f"customers={total_customers}, members={total_members}, "
            f"products={total_products}, revenue={lifetime_revenue}"
        )

        return {
            "total_customers": total_customers,
            "total_members": total_members,
            "active_members": active_members,
            "total_products": total_products,
            "total_categories": total_categories,
            "total_subcategories": total_subcategories,
            "lifetime_revenue": lifetime_revenue,
            "lifetime_credit": lifetime_credit,
            "lifetime_profit": lifetime_profit,
            "lifetime_expenses": lifetime_expenses,
            "total_invoices": total_invoices,
            "total_invoices_completed": total_invoices_completed,
            "total_invoices_credit": total_invoices_credit,
            "average_invoice_value": average_invoice_value,
            "total_inventory_value": total_inventory_value,
            "business_created_at": business_created_at,
        }


class DashboardProductStatisticsRepositoryImpl(DashboardProductStatisticsRepository):
    """Django implementation of DashboardProductStatisticsRepository."""

    def get_product_statistics(
        self,
        business_id: UUID,
        product_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Implement product statistics aggregation."""
        try:
            product = ProductModel.objects.select_related("category", "subcategory").get(
                id=product_id, business_id=business_id
            )
        except ProductModel.DoesNotExist:
            logger.warning(f"Product {product_id} not found for business {business_id}")
            return {}

        invoice_lines = (
            InvoiceLineModel.objects.filter(
                product_id=product_id,
                invoice__business_id=business_id,
                invoice__is_archived=False,
                invoice__status="COMPLETED",
                invoice__created_at__gte=start_date,
                invoice__created_at__lte=end_date,
            )
            .annotate(period=TruncDay("invoice__created_at"))
            .values("period")
            .annotate(
                quantity_sold=Sum("quantity"),
                revenue=Sum("line_total"),
                cost=Sum(
                    models.F("product__purchase_price") * models.F("quantity"),
                    output_field=models.DecimalField(),
                ),
            )
            .order_by("period")
        )

        total_quantity = 0
        total_revenue = Decimal("0.00")
        total_cost = Decimal("0.00")
        number_of_sales = 0

        daily_data = []
        for row in invoice_lines:
            quantity = row["quantity_sold"] or 0
            revenue = Decimal(str(row["revenue"] or 0))
            cost = Decimal(str(row["cost"] or 0))
            profit = revenue - cost
            margin = (profit / revenue * 100) if revenue > 0 else Decimal("0.00")

            total_quantity += quantity
            total_revenue += revenue
            total_cost += cost
            number_of_sales += 1

            daily_data.append(
                {
                    "product_id": product_id,
                    "product_name": product.name,
                    "date": row["period"],
                    "quantity_sold": quantity,
                    "revenue": revenue.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    "cost": cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    "profit": profit.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    "margin_percentage": margin.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                }
            )

        total_profit = total_revenue - total_cost
        total_margin = (
            (total_profit / total_revenue * 100) if total_revenue > 0 else Decimal("0.00")
        )

        top_customers_raw = (
            InvoiceLineModel.objects.filter(
                product_id=product_id,
                invoice__business_id=business_id,
                invoice__is_archived=False,
                invoice__status="COMPLETED",
                invoice__created_at__gte=start_date,
                invoice__created_at__lte=end_date,
            )
            .values("invoice__customer_id", "invoice__customer_name")
            .annotate(
                total_purchases=Count("invoice_id", distinct=True),
                total_revenue=Sum("line_total"),
            )
            .order_by("-total_revenue")[:10]
        )

        top_customers = []
        for row in top_customers_raw:
            top_customers.append(
                {
                    "customer_id": row["invoice__customer_id"],
                    "customer_name": row["invoice__customer_name"] or "Walk-in Customer",
                    "total_purchases": row["total_purchases"] or 0,
                    "total_revenue": Decimal(str(row["total_revenue"] or 0)).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    ),
                }
            )

        return {
            "product": {
                "product_id": product.id,
                "product_name": product.name,
                "category_id": product.category_id,
                "category_name": product.category.name,
                "subcategory_id": product.subcategory_id,
                "subcategory_name": product.subcategory.name if product.subcategory else None,
            },
            "totals": {
                "total_revenue": total_revenue.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                "total_cost": total_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                "total_profit": total_profit.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                "margin_percentage": total_margin.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                "quantity_sold": total_quantity,
                "number_of_sales": number_of_sales,
            },
            "daily_data": daily_data,
            "top_customers": top_customers,
        }

    def calculate_product_margins(
        self,
        business_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Implement product margins calculation."""
        if start_date is None or end_date is None:
            return []

        product_margins = (
            InvoiceLineModel.objects.filter(
                invoice__business_id=business_id,
                invoice__is_archived=False,
                invoice__status="COMPLETED",
                invoice__created_at__gte=start_date,
                invoice__created_at__lte=end_date,
            )
            .select_related("product")
            .values("product_id", "product__name")
            .annotate(
                total_quantity_sold=Sum("quantity"),
                total_revenue=Sum("line_total"),
                total_cost=Sum(
                    models.F("product__purchase_price") * models.F("quantity"),
                    output_field=models.DecimalField(),
                ),
            )
            .order_by("-total_revenue")
        )

        result = []
        for row in product_margins:
            revenue = Decimal(str(row["total_revenue"] or 0))
            cost = Decimal(str(row["total_cost"] or 0))
            profit = revenue - cost
            margin = (profit / revenue * 100) if revenue > 0 else Decimal("0.00")

            result.append(
                {
                    "product_id": row["product_id"],
                    "product_name": row["product__name"] or "Unknown",
                    "total_quantity_sold": row["total_quantity_sold"] or 0,
                    "total_revenue": revenue.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    "total_cost": cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    "total_profit": profit.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    "margin_percentage": margin.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                }
            )

        logger.info(f"Product margins calculated for business {business_id}")
        return result


class DashboardCategoryStatisticsRepositoryImpl(DashboardCategoryStatisticsRepository):
    """Django implementation of DashboardCategoryStatisticsRepository."""

    def get_category_statistics(
        self,
        business_id: UUID,
        category_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Implement category statistics aggregation."""
        try:
            category = CategoryModel.objects.get(id=category_id, business_id=business_id)
        except CategoryModel.DoesNotExist:
            logger.warning(f"Category {category_id} not found for business {business_id}")
            return {}

        invoice_lines = (
            InvoiceLineModel.objects.filter(
                product__category_id=category_id,
                invoice__business_id=business_id,
                invoice__is_archived=False,
                invoice__status="COMPLETED",
                invoice__created_at__gte=start_date,
                invoice__created_at__lte=end_date,
            )
            .annotate(period=TruncDay("invoice__created_at"))
            .values("period")
            .annotate(
                quantity_sold=Sum("quantity"),
                revenue=Sum("line_total"),
                cost=Sum(
                    models.F("product__purchase_price") * models.F("quantity"),
                    output_field=models.DecimalField(),
                ),
            )
            .order_by("period")
        )

        total_quantity = 0
        total_revenue = Decimal("0.00")
        total_cost = Decimal("0.00")
        number_of_sales = 0

        daily_data = []
        for row in invoice_lines:
            quantity = row["quantity_sold"] or 0
            revenue = Decimal(str(row["revenue"] or 0))
            cost = Decimal(str(row["cost"] or 0))
            profit = revenue - cost

            total_quantity += quantity
            total_revenue += revenue
            total_cost += cost
            number_of_sales += 1

            daily_data.append(
                {
                    "date": row["period"],
                    "quantity_sold": quantity,
                    "revenue": revenue.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    "cost": cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    "profit": profit.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                }
            )

        total_profit = total_revenue - total_cost

        top_products_raw = (
            InvoiceLineModel.objects.filter(
                product__category_id=category_id,
                invoice__business_id=business_id,
                invoice__is_archived=False,
                invoice__status="COMPLETED",
                invoice__created_at__gte=start_date,
                invoice__created_at__lte=end_date,
            )
            .select_related("product")
            .values("product_id", "product__name", "product__quantity")
            .annotate(
                total_sold=Sum("quantity"),
                total_revenue=Sum("line_total"),
            )
            .order_by("-total_revenue")[:10]
        )

        top_products = []
        for row in top_products_raw:
            top_products.append(
                {
                    "product_id": row["product_id"],
                    "product_name": row["product__name"] or "Unknown",
                    "total_sold": row["total_sold"] or 0,
                    "total_revenue": Decimal(str(row["total_revenue"] or 0)).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    ),
                    "quantity_available": row["product__quantity"] or 0,
                }
            )

        return {
            "category": {
                "category_id": category.id,
                "category_name": category.name,
            },
            "totals": {
                "total_revenue": total_revenue.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                "total_cost": total_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                "total_profit": total_profit.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                "quantity_sold": total_quantity,
                "number_of_sales": number_of_sales,
            },
            "daily_data": daily_data,
            "top_products": top_products,
        }


class DashboardSubCategoryStatisticsRepositoryImpl(DashboardSubCategoryStatisticsRepository):
    """Django implementation of DashboardSubCategoryStatisticsRepository."""

    def get_subcategory_statistics(
        self,
        business_id: UUID,
        subcategory_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Implement subcategory statistics aggregation."""
        try:
            subcategory = SubCategoryModel.objects.select_related("category").get(
                id=subcategory_id, business_id=business_id
            )
        except SubCategoryModel.DoesNotExist:
            logger.warning(f"Subcategory {subcategory_id} not found for business {business_id}")
            return {}

        invoice_lines = (
            InvoiceLineModel.objects.filter(
                product__subcategory_id=subcategory_id,
                invoice__business_id=business_id,
                invoice__is_archived=False,
                invoice__status="COMPLETED",
                invoice__created_at__gte=start_date,
                invoice__created_at__lte=end_date,
            )
            .annotate(period=TruncDay("invoice__created_at"))
            .values("period")
            .annotate(
                quantity_sold=Sum("quantity"),
                revenue=Sum("line_total"),
                cost=Sum(
                    models.F("product__purchase_price") * models.F("quantity"),
                    output_field=models.DecimalField(),
                ),
            )
            .order_by("period")
        )

        total_quantity = 0
        total_revenue = Decimal("0.00")
        total_cost = Decimal("0.00")
        number_of_sales = 0

        daily_data = []
        for row in invoice_lines:
            quantity = row["quantity_sold"] or 0
            revenue = Decimal(str(row["revenue"] or 0))
            cost = Decimal(str(row["cost"] or 0))
            profit = revenue - cost

            total_quantity += quantity
            total_revenue += revenue
            total_cost += cost
            number_of_sales += 1

            daily_data.append(
                {
                    "date": row["period"],
                    "quantity_sold": quantity,
                    "revenue": revenue.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    "cost": cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    "profit": profit.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                }
            )

        total_profit = total_revenue - total_cost

        top_products_raw = (
            InvoiceLineModel.objects.filter(
                product__subcategory_id=subcategory_id,
                invoice__business_id=business_id,
                invoice__is_archived=False,
                invoice__status="COMPLETED",
                invoice__created_at__gte=start_date,
                invoice__created_at__lte=end_date,
            )
            .select_related("product")
            .values("product_id", "product__name", "product__quantity")
            .annotate(
                total_sold=Sum("quantity"),
                total_revenue=Sum("line_total"),
            )
            .order_by("-total_revenue")[:10]
        )

        top_products = []
        for row in top_products_raw:
            top_products.append(
                {
                    "product_id": row["product_id"],
                    "product_name": row["product__name"] or "Unknown",
                    "total_sold": row["total_sold"] or 0,
                    "total_revenue": Decimal(str(row["total_revenue"] or 0)).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    ),
                    "quantity_available": row["product__quantity"] or 0,
                }
            )

        return {
            "subcategory": {
                "subcategory_id": subcategory.id,
                "subcategory_name": subcategory.name,
                "category_id": subcategory.category_id,
                "category_name": subcategory.category.name,
            },
            "totals": {
                "total_revenue": total_revenue.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                "total_cost": total_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                "total_profit": total_profit.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                "quantity_sold": total_quantity,
                "number_of_sales": number_of_sales,
            },
            "daily_data": daily_data,
            "top_products": top_products,
        }


class DashboardCashierStatisticsRepositoryImpl(DashboardCashierStatisticsRepository):
    """Django implementation of DashboardCashierStatisticsRepository."""

    def get_cashier_statistics(
        self,
        business_id: UUID,
        cashier_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Implement cashier statistics aggregation."""
        has_invoices = InvoiceModel.objects.filter(
            business_id=business_id,
            cashier_id=cashier_id,
            is_archived=False,
            status="COMPLETED",
            created_at__gte=start_date,
            created_at__lte=end_date,
        ).exists()

        try:
            cashier = UserModel.objects.get(id=cashier_id)
            cashier_name = cashier.name or cashier.email or "Unknown"
            cashier_email = cashier.email or ""
            cashier_phone = cashier.phone_number
            cashier_avatar = cashier.avatar_url
        except UserModel.DoesNotExist:
            cashier_name = "Unknown"
            cashier_email = ""
            cashier_phone = None
            cashier_avatar = None

        try:
            business_member = BusinessMemberModel.objects.select_related("user").get(
                business_id=business_id, user_id=cashier_id
            )
            member_role = business_member.role
            member_is_active = business_member.is_active
            member_joined_at = business_member.joined_at
            member_left_at = business_member.left_at
        except BusinessMemberModel.DoesNotExist:
            member_role = "unknown"
            member_is_active = False
            member_joined_at = timezone.now()
            member_left_at = None

        if not has_invoices:
            return {
                "cashier": {
                    "cashier_id": cashier_id,
                    "cashier_name": cashier_name,
                    "cashier_email": cashier_email,
                    "phone_number": cashier_phone,
                    "avatar_url": cashier_avatar,
                    "role": member_role,
                    "is_active": member_is_active,
                    "joined_at": member_joined_at,
                    "left_at": member_left_at,
                },
                "totals": {
                    "total_sales": 0,
                    "total_revenue": Decimal("0.00"),
                    "average_sale_value": Decimal("0.00"),
                    "customers_served": 0,
                    "total_quantity_sold": 0,
                },
                "lifetime_totals": {
                    "total_sales": 0,
                    "total_revenue": Decimal("0.00"),
                    "average_sale_value": Decimal("0.00"),
                    "customers_served": 0,
                    "total_quantity_sold": 0,
                },
                "daily_data": [],
            }

        invoices_daily = (
            InvoiceModel.objects.filter(
                business_id=business_id,
                cashier_id=cashier_id,
                is_archived=False,
                status="COMPLETED",
                created_at__gte=start_date,
                created_at__lte=end_date,
            )
            .annotate(period=TruncDay("created_at"))
            .values("period")
            .annotate(
                total_sales=Count("id", distinct=True),
                total_revenue=Sum("total"),
                customers_served=Count("customer_id", distinct=True),
            )
            .order_by("period")
        )

        quantity_per_day = (
            InvoiceLineModel.objects.filter(
                invoice__business_id=business_id,
                invoice__cashier_id=cashier_id,
                invoice__is_archived=False,
                invoice__status="COMPLETED",
                invoice__created_at__gte=start_date,
                invoice__created_at__lte=end_date,
            )
            .annotate(period=TruncDay("invoice__created_at"))
            .values("period")
            .annotate(total_quantity=Sum("quantity"))
        )

        quantity_dict = {row["period"]: row["total_quantity"] or 0 for row in quantity_per_day}

        total_sales_count = 0
        total_revenue = Decimal("0.00")
        total_quantity_sold = 0

        total_customers_served_count = (
            InvoiceModel.objects.filter(
                business_id=business_id,
                cashier_id=cashier_id,
                is_archived=False,
                status="COMPLETED",
                created_at__gte=start_date,
                created_at__lte=end_date,
            )
            .exclude(customer_id__isnull=True)
            .values("customer_id")
            .distinct()
            .count()
        )

        daily_data = []
        for row in invoices_daily:
            period = row["period"]
            sales_count = row["total_sales"] or 0
            revenue = Decimal(str(row["total_revenue"] or 0))
            quantity = quantity_dict.get(period, 0)
            customers_count = row["customers_served"] or 0

            average_sale_value = revenue / sales_count if sales_count > 0 else Decimal("0.00")

            total_sales_count += sales_count
            total_revenue += revenue
            total_quantity_sold += quantity

            daily_data.append(
                {
                    "date": period,
                    "total_sales": sales_count,
                    "total_revenue": revenue.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    "total_quantity_sold": quantity,
                    "average_sale_value": average_sale_value.quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    ),
                    "customers_served": customers_count,
                }
            )

        average_sale_value = (
            total_revenue / total_sales_count if total_sales_count > 0 else Decimal("0.00")
        )

        lifetime_start_date = (
            member_joined_at if member_joined_at else timezone.now() - timedelta(days=365)
        )

        lifetime_stats = InvoiceModel.objects.filter(
            business_id=business_id,
            cashier_id=cashier_id,
            is_archived=False,
            status="COMPLETED",
            created_at__gte=lifetime_start_date,
        ).aggregate(
            total_sales=Count("id", distinct=True),
            total_revenue=Sum("total"),
            customers_served=Count("customer_id", distinct=True),
        )

        lifetime_total_quantity = (
            InvoiceLineModel.objects.filter(
                invoice__business_id=business_id,
                invoice__cashier_id=cashier_id,
                invoice__is_archived=False,
                invoice__status="COMPLETED",
                invoice__created_at__gte=lifetime_start_date,
            ).aggregate(total=Sum("quantity"))["total"]
            or 0
        )

        lifetime_total_sales = lifetime_stats["total_sales"] or 0
        lifetime_total_revenue = Decimal(str(lifetime_stats["total_revenue"] or 0))
        lifetime_customers_served = lifetime_stats["customers_served"] or 0
        lifetime_average_sale_value = (
            lifetime_total_revenue / lifetime_total_sales
            if lifetime_total_sales > 0
            else Decimal("0.00")
        )

        return {
            "cashier": {
                "cashier_id": cashier_id,
                "cashier_name": cashier_name,
                "cashier_email": cashier_email,
                "phone_number": cashier_phone,
                "avatar_url": cashier_avatar,
                "role": member_role,
                "is_active": member_is_active,
                "joined_at": member_joined_at,
                "left_at": member_left_at,
            },
            "totals": {
                "total_sales": total_sales_count,
                "total_revenue": total_revenue.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                "average_sale_value": average_sale_value.quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ),
                "customers_served": total_customers_served_count,
                "total_quantity_sold": total_quantity_sold,
            },
            "lifetime_totals": {
                "total_sales": lifetime_total_sales,
                "total_revenue": lifetime_total_revenue.quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ),
                "average_sale_value": lifetime_average_sale_value.quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ),
                "customers_served": lifetime_customers_served,
                "total_quantity_sold": lifetime_total_quantity,
            },
            "daily_data": daily_data,
        }

    def get_cashier_ranking(
        self,
        business_id: UUID,
        cashier_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> int | None:
        """Implement cashier ranking calculation."""
        cashier_revenue = InvoiceModel.objects.filter(
            business_id=business_id,
            cashier_id=cashier_id,
            is_archived=False,
            status="COMPLETED",
            created_at__gte=start_date,
            created_at__lte=end_date,
        ).aggregate(total=Sum("total"))["total"]

        if cashier_revenue is None:
            return None

        cashiers_with_higher_revenue = (
            InvoiceModel.objects.filter(
                business_id=business_id,
                is_archived=False,
                status="COMPLETED",
                created_at__gte=start_date,
                created_at__lte=end_date,
                cashier_id__isnull=False,
            )
            .exclude(cashier_id=cashier_id)
            .values("cashier_id")
            .annotate(total_revenue=Sum("total"))
            .filter(total_revenue__gt=cashier_revenue)
            .count()
        )

        return cashiers_with_higher_revenue + 1
