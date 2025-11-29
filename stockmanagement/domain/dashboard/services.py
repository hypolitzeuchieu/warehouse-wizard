"""Dashboard domain services for metrics calculations."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from django.db import models
from django.db.models import Count, Sum
from django.db.models.functions import TruncDay, TruncWeek
from django.utils import timezone

from domain.credit.repositories import CreditRepository
from domain.finance.repositories import ExpenseRepository, PayrollRepository
from domain.inventory.repositories import ProductRepository
from domain.sales.entities import InvoiceStatus
from domain.sales.repositories import InvoiceLineRepository, InvoiceRepository
from infrastructure.persistence.models.credit_models import Credit as CreditModel
from infrastructure.persistence.models.finance_models import Expense as ExpenseModel
from infrastructure.persistence.models.finance_models import Payroll as PayrollModel
from infrastructure.persistence.models.sales_models import Invoice as InvoiceModel
from infrastructure.persistence.models.sales_models import InvoiceLine as InvoiceLineModel

logger = logging.getLogger(__name__)


class DashboardMetricsService:
    """Service for calculating dashboard metrics."""

    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        invoice_line_repository: InvoiceLineRepository,
        product_repository: ProductRepository,
        credit_repository: CreditRepository,
        business_id: UUID,
        expense_repository: ExpenseRepository | None = None,
        payroll_repository: PayrollRepository | None = None,
    ) -> None:
        """Initialize dashboard metrics service."""
        self.invoice_repository = invoice_repository
        self.invoice_line_repository = invoice_line_repository
        self.product_repository = product_repository
        self.credit_repository = credit_repository
        self.expense_repository = expense_repository
        self.payroll_repository = payroll_repository
        self.business_id = business_id

    def calculate_revenue_metrics(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Decimal | int]:
        """
        Calculate revenue metrics for a business.

        Args:
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)

        Returns:
            Dictionary with revenue metrics
        """
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=now.weekday())
        month_start = today_start.replace(day=1)
        year_start = today_start.replace(month=1, day=1)

        # Get all completed invoices
        invoices = self.invoice_repository.get_by_business(
            business_id=self.business_id,
            status=InvoiceStatus.COMPLETED,
            start_date=start_date or year_start,
            end_date=end_date or now,
            limit=10000,  # Large limit to get all
        )

        total_revenue = Decimal("0.00")
        revenue_today = Decimal("0.00")
        revenue_this_week = Decimal("0.00")
        revenue_this_month = Decimal("0.00")
        revenue_this_year = Decimal("0.00")
        total_orders = 0
        orders_today = 0
        orders_this_week = 0
        orders_this_month = 0

        for invoice in invoices:
            invoice_date = invoice.created_at
            total_revenue += invoice.total
            total_orders += 1

            if invoice_date >= today_start:
                revenue_today += invoice.total
                orders_today += 1

            if invoice_date >= week_start:
                revenue_this_week += invoice.total
                orders_this_week += 1

            if invoice_date >= month_start:
                revenue_this_month += invoice.total
                orders_this_month += 1

            if invoice_date >= year_start:
                revenue_this_year += invoice.total

        average_order_value = total_revenue / total_orders if total_orders > 0 else Decimal("0.00")

        logger.info(
            f"Revenue metrics calculated for business {self.business_id}: "
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

    def calculate_expense_metrics(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Decimal]:
        """
        Calculate expense metrics for a business.

        Args:
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)

        Returns:
            Dictionary with expense metrics
        """
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=now.weekday())
        month_start = today_start.replace(day=1)
        year_start = today_start.replace(month=1, day=1)

        total_expenses = Decimal("0.00")
        expenses_today = Decimal("0.00")
        expenses_this_week = Decimal("0.00")
        expenses_this_month = Decimal("0.00")
        expenses_this_year = Decimal("0.00")
        salary_expenses = Decimal("0.00")
        other_expenses = Decimal("0.00")

        # Get expenses if repository is available
        if self.expense_repository:
            expenses = self.expense_repository.get_by_business(
                business_id=self.business_id,
                start_date=start_date or year_start,
                end_date=end_date or now,
                limit=10000,
            )

            for expense in expenses:
                expense_date = expense.created_at
                total_expenses += expense.amount
                other_expenses += expense.amount

                if expense_date >= today_start:
                    expenses_today += expense.amount
                if expense_date >= week_start:
                    expenses_this_week += expense.amount
                if expense_date >= month_start:
                    expenses_this_month += expense.amount
                if expense_date >= year_start:
                    expenses_this_year += expense.amount

        # Get payroll expenses if repository is available
        if self.payroll_repository:
            payrolls = self.payroll_repository.get_by_business(
                business_id=self.business_id,
                start_date=start_date or year_start,
                end_date=end_date or now,
                limit=10000,
            )

            for payroll in payrolls:
                payroll_date = payroll.payment_date
                salary_expenses += payroll.net_amount
                total_expenses += payroll.net_amount

                if payroll_date >= today_start:
                    expenses_today += payroll.net_amount
                if payroll_date >= week_start:
                    expenses_this_week += payroll.net_amount
                if payroll_date >= month_start:
                    expenses_this_month += payroll.net_amount
                if payroll_date >= year_start:
                    expenses_this_year += payroll.net_amount

        logger.info(f"Expense metrics calculated for business {self.business_id}")

        return {
            "total_expenses": total_expenses,
            "expenses_today": expenses_today,
            "expenses_this_week": expenses_this_week,
            "expenses_this_month": expenses_this_month,
            "expenses_this_year": expenses_this_year,
            "salary_expenses": salary_expenses,
            "other_expenses": other_expenses,
        }

    def calculate_profit_metrics(
        self,
        revenue_metrics: dict[str, Decimal | int],
        expense_metrics: dict[str, Decimal],
    ) -> dict[str, Decimal]:
        """
        Calculate profit metrics from revenue and expense metrics.

        Args:
            revenue_metrics: Revenue metrics dictionary
            expense_metrics: Expense metrics dictionary

        Returns:
            Dictionary with profit metrics
        """
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

    def calculate_inventory_metrics(self) -> dict[str, int | Decimal]:
        """
        Calculate inventory metrics for a business.

        Returns:
            Dictionary with inventory metrics
        """
        products = self.product_repository.get_by_business(business_id=self.business_id)

        total_products = len(products)
        low_stock_products = sum(1 for p in products if p.is_low_stock())
        expired_products = sum(1 for p in products if p.is_expired)
        products_on_promotion = sum(1 for p in products if p.on_promotion)

        # Calculate total inventory value (purchase_price * quantity)
        total_inventory_value = sum(p.purchase_price * p.quantity for p in products)

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

    def calculate_customer_metrics(self) -> dict[str, int | Decimal]:
        """
        Calculate customer metrics for a business.

        Returns:
            Dictionary with customer metrics
        """
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=now.weekday())
        month_start = today_start.replace(day=1)

        # Get credits for the business
        credits = self.credit_repository.get_by_business(
            business_id=self.business_id,
            overdue_only=False,
            limit=10000,
        )

        overdue_credits = self.credit_repository.get_by_business(
            business_id=self.business_id,
            overdue_only=True,
            limit=10000,
        )

        total_credit_amount = sum(c.remaining_amount for c in credits)
        overdue_credit_amount = sum(c.remaining_amount for c in overdue_credits)

        # Get customers for the business
        from domain.customer.repositories import CustomerRepository
        from infrastructure.persistence.repositories import CustomerRepositoryImpl

        customer_repository: CustomerRepository = CustomerRepositoryImpl()
        customers = customer_repository.get_by_business(business_id=self.business_id, limit=10000)

        total_customers = len(customers)
        new_customers_today = sum(1 for c in customers if c.created_at >= today_start)
        new_customers_this_week = sum(1 for c in customers if c.created_at >= week_start)
        new_customers_this_month = sum(1 for c in customers if c.created_at >= month_start)

        # Active customers are those who made purchases in the last 30 days
        # TODO: Implement with purchase history to determine active customers
        # active_threshold = now - timedelta(days=30)  # Will be used when implementing purchase history
        active_customers = total_customers  # Placeholder

        logger.info(f"Customer metrics calculated for business {self.business_id}")

        return {
            "total_customers": total_customers,
            "new_customers_today": new_customers_today,
            "new_customers_this_week": new_customers_this_week,
            "new_customers_this_month": new_customers_this_month,
            "active_customers": active_customers,
            "total_credit_amount": total_credit_amount,
            "overdue_credit_amount": overdue_credit_amount,
        }

    def get_top_products(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 10,
    ) -> list[dict[str, UUID | str | int | Decimal]]:
        """
        Get top selling products by revenue.

        Args:
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)
            limit: Number of top products to return

        Returns:
            List of top products with sales data
        """
        # Get all invoice lines for the business
        invoices = self.invoice_repository.get_by_business(
            business_id=self.business_id,
            status=InvoiceStatus.COMPLETED,
            start_date=start_date,
            end_date=end_date,
            limit=10000,
        )

        product_sales: dict[UUID, dict[str, int | Decimal]] = {}

        for invoice in invoices:
            lines = self.invoice_line_repository.get_by_invoice(invoice.id)
            for line in lines:
                if line.product_id not in product_sales:
                    product_sales[line.product_id] = {
                        "total_sold": 0,
                        "total_revenue": Decimal("0.00"),
                    }

                product_sales[line.product_id]["total_sold"] += line.quantity
                product_sales[line.product_id]["total_revenue"] += line.line_total

        # Get product details and sort by revenue
        top_products: list[dict[str, UUID | str | int | Decimal]] = []
        for product_id, sales_data in sorted(
            product_sales.items(),
            key=lambda x: x[1]["total_revenue"],
            reverse=True,
        )[:limit]:
            product = self.product_repository.get_by_id(product_id)
            if product:
                top_products.append(
                    {
                        "product_id": product_id,
                        "product_name": product.name,
                        "total_sold": sales_data["total_sold"],
                        "total_revenue": sales_data["total_revenue"],
                        "quantity_available": product.quantity,
                    }
                )

        logger.info(f"Top {len(top_products)} products calculated for business {self.business_id}")

        return top_products

    def calculate_daily_metrics(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """
        Calculate daily metrics for a date range using optimized database queries.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of daily metrics dictionaries
        """
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        daily_invoices = (
            InvoiceModel.objects.filter(
                business_id=self.business_id,
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
                business_id=self.business_id,
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
                business_id=self.business_id,
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
                business_id=self.business_id,
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

        logger.info(
            f"Daily metrics calculated for {len(result)} days for business {self.business_id}"
        )
        return result

    def calculate_daily_profits(
        self,
        daily_metrics: list[dict[str, Any]],
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """
        Calculate gross and net profits for each day.

        Args:
            daily_metrics: List of daily metrics from calculate_daily_metrics
            start_date: Start date
            end_date: End date

        Returns:
            List of daily metrics with profit calculations
        """
        daily_cogs = (
            InvoiceLineModel.objects.filter(
                invoice__business_id=self.business_id,
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

    def get_top_categories(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: int = 10,
    ) -> list[dict[str, UUID | str | Decimal | int]]:
        """
        Get top categories by revenue.

        Args:
            start_date: Start date
            end_date: End date
            limit: Number of top categories to return

        Returns:
            List of top categories with sales data
        """
        category_sales = (
            InvoiceLineModel.objects.filter(
                invoice__business_id=self.business_id,
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

        logger.info(
            f"Top {len(top_categories)} categories calculated for business {self.business_id}"
        )
        return top_categories

    def get_recent_sales(
        self,
        limit: int = 10,
    ) -> list[dict[str, UUID | int | str | Decimal | datetime]]:
        """
        Get recent sales (invoices).

        Args:
            limit: Number of recent sales to return

        Returns:
            List of recent sales
        """
        invoices = InvoiceModel.objects.filter(
            business_id=self.business_id, is_archived=False
        ).order_by("-created_at")[:limit]

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

        logger.info(f"Recent {len(recent_sales)} sales retrieved for business {self.business_id}")
        return recent_sales

    def calculate_product_statistics(
        self,
        start_date: datetime,
        end_date: datetime,
        group_by: str = "daily",
    ) -> list[dict[str, UUID | str | datetime | Decimal | int]]:
        """
        Calculate product statistics grouped by day or week.

        Args:
            start_date: Start date
            end_date: End date
            group_by: "daily" or "weekly"

        Returns:
            List of product statistics
        """

        trunc_func = (
            TruncDay("invoice__created_at")
            if group_by == "daily"
            else TruncWeek("invoice__created_at")
        )

        product_stats = (
            InvoiceLineModel.objects.filter(
                invoice__business_id=self.business_id,
                invoice__is_archived=False,
                invoice__created_at__gte=start_date,
                invoice__created_at__lte=end_date,
            )
            .select_related("product")
            .annotate(period=trunc_func)
            .values("product_id", "product__name", "period")
            .annotate(
                quantity_sold=Sum("quantity"),
                revenue=Sum("line_total"),
                cost=Sum(
                    models.F("product__purchase_price") * models.F("quantity"),
                    output_field=models.DecimalField(),
                ),
            )
            .order_by("period", "-revenue")
        )

        result = []
        for row in product_stats:
            revenue = Decimal(str(row["revenue"] or 0))
            cost = Decimal(str(row["cost"] or 0))
            profit = revenue - cost
            margin = (profit / revenue * 100) if revenue > 0 else Decimal("0.00")

            result.append(
                {
                    "product_id": row["product_id"],
                    "product_name": row["product__name"] or "Unknown",
                    "date": row["period"],
                    "quantity_sold": row["quantity_sold"] or 0,
                    "revenue": revenue.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    "cost": cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    "profit": profit.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    "margin_percentage": margin.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                }
            )

        logger.info(f"Product statistics calculated ({group_by}) for business {self.business_id}")
        return result

    def calculate_product_margins(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, UUID | str | Decimal | int]]:
        """
        Calculate product margins (aggregated).

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            List of product margins
        """
        product_margins = (
            InvoiceLineModel.objects.filter(
                invoice__business_id=self.business_id,
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

        logger.info(f"Product margins calculated for business {self.business_id}")
        return result
