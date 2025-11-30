"""Dashboard domain repositories (interfaces)."""

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


class DashboardMetricsRepository(ABC):
    """Repository for dashboard metrics aggregations."""

    @abstractmethod
    def aggregate_revenue_metrics(
        self,
        business_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Decimal | int]:
        """
        Aggregate revenue metrics for a business.

        Returns:
            {
                "total_revenue": Decimal,
                "total_orders": int,
                "revenue_today": Decimal,
                "orders_today": int,
                "revenue_this_week": Decimal,
                "orders_this_week": int,
                "revenue_this_month": Decimal,
                "orders_this_month": int,
                "revenue_this_year": Decimal,
                "average_order_value": Decimal,
            }
        """
        pass

    @abstractmethod
    def aggregate_expense_metrics(
        self,
        business_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Decimal]:
        """
        Aggregate expense metrics for a business.

        Returns:
            {
                "total_expenses": Decimal,
                "expenses_today": Decimal,
                "expenses_this_week": Decimal,
                "expenses_this_month": Decimal,
                "expenses_this_year": Decimal,
                "salary_expenses": Decimal,
                "other_expenses": Decimal,
            }
        """
        pass

    @abstractmethod
    def aggregate_daily_metrics(
        self,
        business_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """
        Get daily aggregated invoice metrics.

        Returns:
            [
                {
                    "date": datetime,
                    "total_revenue": Decimal,
                    "total_sales": int,
                    "credit_revenue": Decimal,
                    "complete_revenue": Decimal,
                },
                ...
            ]
        """
        pass

    @abstractmethod
    def aggregate_daily_profits(
        self,
        business_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """
        Get daily profit metrics.

        Returns:
            [
                {
                    "date": datetime,
                    "gross_profit": Decimal,
                    "net_profit": Decimal,
                },
                ...
            ]
        """
        pass

    @abstractmethod
    def get_top_products(
        self,
        business_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get top products by revenue.

        Returns:
            [
                {
                    "product_id": UUID,
                    "product_name": str,
                    "total_revenue": Decimal,
                    "total_quantity_sold": int,
                },
                ...
            ]
        """
        pass

    @abstractmethod
    def get_top_categories(
        self,
        business_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get top categories by revenue.

        Returns:
            [
                {
                    "category_id": UUID,
                    "category_name": str,
                    "total_revenue": Decimal,
                },
                ...
            ]
        """
        pass

    @abstractmethod
    def get_recent_sales(
        self,
        business_id: UUID,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get recent completed sales.

        Returns:
            [
                {
                    "invoice_id": UUID,
                    "invoice_number": int,
                    "customer_name": str | None,
                    "total": Decimal,
                    "created_at": datetime,
                },
                ...
            ]
        """
        pass

    @abstractmethod
    def get_inventory_metrics(
        self,
        business_id: UUID,
    ) -> dict[str, int | Decimal]:
        """
        Get inventory metrics.

        Returns:
            {
                "total_products": int,
                "low_stock_products": int,
                "out_of_stock_products": int,
                "total_inventory_value": Decimal,
            }
        """
        pass

    @abstractmethod
    def get_customer_metrics(
        self,
        business_id: UUID,
    ) -> dict[str, int]:
        """
        Get customer metrics.

        Returns:
            {
                "total_customers": int,
                "new_customers": int,
                "active_customers": int,
            }
        """
        pass

    @abstractmethod
    def get_credit_metrics(
        self,
        business_id: UUID,
    ) -> dict[str, Decimal | int]:
        """
        Get credit metrics.

        Returns:
            {
                "total_credit_amount": Decimal,
                "overdue_credit_amount": Decimal,
                "total_credits": int,
            }
        """
        pass

    @abstractmethod
    def calculate_profit_metrics(
        self,
        business_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Decimal]:
        """
        Calculate profit metrics.

        Returns:
            {
                "total_profit": Decimal,
                "profit_today": Decimal,
                "profit_this_week": Decimal,
                "profit_this_month": Decimal,
                "profit_margin_percentage": Decimal,
            }
        """
        pass

    @abstractmethod
    def calculate_trends(
        self,
        current_value: Decimal,
        previous_value: Decimal,
        previous_period_start: datetime,
        previous_period_end: datetime,
    ) -> dict[str, Any]:
        """
        Calculate trends comparison.

        Returns:
            {
                "previous_period_start": datetime,
                "previous_period_end": datetime,
                "current_value": Decimal,
                "previous_value": Decimal,
                "change_amount": Decimal,
                "change_percentage": Decimal,
                "trend_direction": str,
            }
        """
        pass


class DashboardProductStatisticsRepository(ABC):
    """Repository for product statistics aggregations."""

    @abstractmethod
    def get_product_statistics(
        self,
        business_id: UUID,
        product_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """
        Get detailed product statistics.

        Returns:
            {
                "product": {
                    "product_id": UUID,
                    "product_name": str,
                    "category_id": UUID,
                    "category_name": str,
                    "subcategory_id": UUID | None,
                    "subcategory_name": str | None,
                },
                "totals": {
                    "total_revenue": Decimal,
                    "quantity_sold": int,
                    "total_cost": Decimal,
                    "total_profit": Decimal,
                    "margin_percentage": Decimal,
                },
                "daily_data": list[dict],
                "top_customers": list[dict],
            }
        """
        pass

    @abstractmethod
    def calculate_product_margins(
        self,
        business_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Calculate product margins.

        Returns:
            [
                {
                    "product_id": UUID,
                    "product_name": str,
                    "total_revenue": Decimal,
                    "total_cost": Decimal,
                    "total_profit": Decimal,
                    "margin_percentage": Decimal,
                },
                ...
            ]
        """
        pass


class DashboardCategoryStatisticsRepository(ABC):
    """Repository for category statistics aggregations."""

    @abstractmethod
    def get_category_statistics(
        self,
        business_id: UUID,
        category_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """
        Get category statistics.

        Returns:
            {
                "category": {
                    "category_id": UUID,
                    "category_name": str,
                },
                "totals": {
                    "total_revenue": Decimal,
                    "total_quantity_sold": int,
                },
                "daily_data": list[dict],
                "top_products": list[dict],
            }
        """
        pass


class DashboardSubCategoryStatisticsRepository(ABC):
    """Repository for subcategory statistics aggregations."""

    @abstractmethod
    def get_subcategory_statistics(
        self,
        business_id: UUID,
        subcategory_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """
        Get subcategory statistics.

        Returns:
            {
                "subcategory": {
                    "subcategory_id": UUID,
                    "subcategory_name": str,
                    "category_id": UUID,
                    "category_name": str,
                },
                "totals": {
                    "total_revenue": Decimal,
                    "total_quantity_sold": int,
                },
                "daily_data": list[dict],
                "top_products": list[dict],
            }
        """
        pass


class DashboardCashierStatisticsRepository(ABC):
    """Repository for cashier statistics aggregations."""

    @abstractmethod
    def get_cashier_statistics(
        self,
        business_id: UUID,
        cashier_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """
        Get cashier statistics.

        Returns:
            {
                "cashier": {
                    "cashier_id": UUID,
                    "cashier_name": str,
                    "cashier_email": str,
                    "phone_number": str | None,
                    "avatar_url": str | None,
                    "role": str,
                    "is_active": bool,
                    "joined_at": datetime,
                    "left_at": datetime | None,
                },
                "totals": {
                    "total_sales": int,
                    "total_revenue": Decimal,
                    "average_sale_value": Decimal,
                    "customers_served": int,
                    "total_quantity_sold": int,
                },
                "lifetime_totals": {
                    "total_sales": int,
                    "total_revenue": Decimal,
                    "average_sale_value": Decimal,
                    "customers_served": int,
                    "total_quantity_sold": int,
                },
                "daily_data": list[dict],
            }
        """
        pass

    @abstractmethod
    def get_cashier_ranking(
        self,
        business_id: UUID,
        cashier_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> int | None:
        """
        Get cashier ranking (1-based) or None if not found.

        Returns:
            Rank (1 = best) or None
        """
        pass
