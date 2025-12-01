"""Dashboard domain services for metrics calculations."""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from domain.dashboard.repositories import (
    DashboardCashierStatisticsRepository,
    DashboardCategoryStatisticsRepository,
    DashboardMetricsRepository,
    DashboardProductStatisticsRepository,
    DashboardSubCategoryStatisticsRepository,
)

logger = logging.getLogger(__name__)


class DashboardMetricsService:
    """Service for calculating dashboard metrics."""

    def __init__(
        self,
        metrics_repository: DashboardMetricsRepository,
        product_statistics_repository: DashboardProductStatisticsRepository,
        category_statistics_repository: DashboardCategoryStatisticsRepository,
        subcategory_statistics_repository: DashboardSubCategoryStatisticsRepository,
        cashier_statistics_repository: DashboardCashierStatisticsRepository,
        business_id: UUID,
    ) -> None:
        """Initialize dashboard metrics service."""
        self.metrics_repository = metrics_repository
        self.product_statistics_repository = product_statistics_repository
        self.category_statistics_repository = category_statistics_repository
        self.subcategory_statistics_repository = subcategory_statistics_repository
        self.cashier_statistics_repository = cashier_statistics_repository
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
        return self.metrics_repository.aggregate_revenue_metrics(
            business_id=self.business_id,
            start_date=start_date,
            end_date=end_date,
        )

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
        return self.metrics_repository.aggregate_expense_metrics(
            business_id=self.business_id,
            start_date=start_date,
            end_date=end_date,
        )

    def calculate_profit_metrics(
        self,
        revenue_metrics: dict[str, Decimal | int] | None = None,
        expense_metrics: dict[str, Decimal] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Decimal]:
        """
        Calculate profit metrics from revenue and expense metrics.

        Args:
            revenue_metrics: Revenue metrics dictionary (optional, will be fetched if not provided)
            expense_metrics: Expense metrics dictionary (optional, will be fetched if not provided)
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)

        Returns:
            Dictionary with profit metrics
        """
        return self.metrics_repository.calculate_profit_metrics(
            business_id=self.business_id,
            start_date=start_date,
            end_date=end_date,
        )

    def calculate_inventory_metrics(self) -> dict[str, int | Decimal]:
        """
        Calculate inventory metrics for a business.

        Returns:
            Dictionary with inventory metrics
        """
        return self.metrics_repository.get_inventory_metrics(business_id=self.business_id)

    def calculate_customer_metrics(self) -> dict[str, int | Decimal]:
        """
        Calculate customer metrics for a business.

        Returns:
            Dictionary with customer metrics
        """
        customer_metrics = self.metrics_repository.get_customer_metrics(
            business_id=self.business_id
        )
        credit_metrics = self.metrics_repository.get_credit_metrics(business_id=self.business_id)

        return {
            **customer_metrics,
            "total_credit_amount": credit_metrics["total_credit_amount"],
            "overdue_credit_amount": credit_metrics["overdue_credit_amount"],
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
        return self.metrics_repository.get_top_products(
            business_id=self.business_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

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
        return self.metrics_repository.aggregate_daily_metrics(
            business_id=self.business_id,
            start_date=start_date,
            end_date=end_date,
        )

    def calculate_daily_profits(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Calculate gross and net profits for each day.

        Args:
            daily_metrics: List of daily metrics from calculate_daily_metrics (optional, will be fetched if not provided)
            start_date: Start date (required if daily_metrics not provided)
            end_date: End date (required if daily_metrics not provided)

        Returns:
            List of daily metrics with profit calculations
        """
        if start_date is None or end_date is None:
            raise ValueError(
                "start_date and end_date are required when daily_metrics is not provided"
            )

        return self.metrics_repository.aggregate_daily_profits(
            business_id=self.business_id,
            start_date=start_date,
            end_date=end_date,
        )

    def get_top_categories(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 10,
    ) -> list[dict[str, UUID | str | Decimal | int]]:
        """
        Get top categories by revenue.

        Args:
            start_date: Start date (optional)
            end_date: End date (optional)
            limit: Number of top categories to return

        Returns:
            List of top categories with sales data
        """
        return self.metrics_repository.get_top_categories(
            business_id=self.business_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

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
        return self.metrics_repository.get_recent_sales(
            business_id=self.business_id,
            limit=limit,
        )

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
            group_by: "daily" or "weekly" (not used anymore, kept for compatibility)

        Returns:
            List of product statistics
        """
        # Note: This method is kept for backward compatibility
        # The actual implementation uses daily aggregation from the repository
        return self.product_statistics_repository.calculate_product_margins(
            business_id=self.business_id,
            start_date=start_date,
            end_date=end_date,
        )

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
        return self.product_statistics_repository.calculate_product_margins(
            business_id=self.business_id,
            start_date=start_date,
            end_date=end_date,
        )

    def calculate_trends(
        self,
        current_value: Decimal,
        previous_value: Decimal,
        previous_period_start: datetime,
        previous_period_end: datetime,
    ) -> dict[str, Any]:
        """
        Calculate trends comparison between current and previous period.

        Args:
            current_value: Current period value
            previous_value: Previous period value
            previous_period_start: Previous period start date
            previous_period_end: Previous period end date

        Returns:
            Dictionary with trends data
        """
        return self.metrics_repository.calculate_trends(
            current_value=current_value,
            previous_value=previous_value,
            previous_period_start=previous_period_start,
            previous_period_end=previous_period_end,
        )

    def get_product_detail_statistics(
        self,
        product_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """
        Get detailed statistics for a specific product.

        Args:
            product_id: Product ID
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary with product statistics
        """
        return self.product_statistics_repository.get_product_statistics(
            business_id=self.business_id,
            product_id=product_id,
            start_date=start_date,
            end_date=end_date,
        )

    def get_category_statistics(
        self,
        category_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """
        Get statistics for a specific category.

        Args:
            category_id: Category ID
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary with category statistics
        """
        return self.category_statistics_repository.get_category_statistics(
            business_id=self.business_id,
            category_id=category_id,
            start_date=start_date,
            end_date=end_date,
        )

    def get_subcategory_statistics(
        self,
        subcategory_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """
        Get statistics for a specific subcategory.

        Args:
            subcategory_id: Subcategory ID
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary with subcategory statistics
        """
        return self.subcategory_statistics_repository.get_subcategory_statistics(
            business_id=self.business_id,
            subcategory_id=subcategory_id,
            start_date=start_date,
            end_date=end_date,
        )

    def get_cashier_statistics(
        self,
        cashier_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """
        Get statistics for a specific cashier.

        Args:
            cashier_id: Cashier user ID
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary with cashier statistics
        """
        return self.cashier_statistics_repository.get_cashier_statistics(
            business_id=self.business_id,
            cashier_id=cashier_id,
            start_date=start_date,
            end_date=end_date,
        )

    def get_cashier_ranking(
        self,
        cashier_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> int | None:
        """
        Get cashier ranking among all cashiers in the business.

        Args:
            cashier_id: Cashier user ID
            start_date: Start date
            end_date: End date

        Returns:
            Rank (1-based) or None if cashier not found
        """
        return self.cashier_statistics_repository.get_cashier_ranking(
            business_id=self.business_id,
            cashier_id=cashier_id,
            start_date=start_date,
            end_date=end_date,
        )

    def get_business_overview_metrics(self) -> dict[str, Any]:
        """
        Get business overview metrics (lifetime, not period-dependent).

        Returns:
            Dictionary with business overview metrics
        """
        return self.metrics_repository.get_business_overview_metrics(business_id=self.business_id)
