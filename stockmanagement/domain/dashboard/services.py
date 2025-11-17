"""Dashboard domain services for metrics calculations."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from django.utils import timezone

from domain.credit.repositories import CreditRepository
from domain.finance.repositories import ExpenseRepository, PayrollRepository
from domain.inventory.repositories import ProductRepository
from domain.sales.entities import InvoiceStatus
from domain.sales.repositories import InvoiceLineRepository, InvoiceRepository

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

    def get_top_products(self, limit: int = 10) -> list[dict[str, UUID | str | int | Decimal]]:
        """
        Get top selling products by revenue.

        Args:
            limit: Number of top products to return

        Returns:
            List of top products with sales data
        """
        # Get all invoice lines for the business
        invoices = self.invoice_repository.get_by_business(
            business_id=self.business_id,
            status=InvoiceStatus.COMPLETED,
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
