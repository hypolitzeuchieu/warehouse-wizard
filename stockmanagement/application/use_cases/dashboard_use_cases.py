"""Dashboard use cases."""

from __future__ import annotations

import logging
from datetime import timedelta
from uuid import UUID

from django.utils import timezone

from application.dto.dashboard_dto import (
    CustomerMetricsDTO,
    DashboardSummaryDTO,
    ExpenseMetricsDTO,
    InventoryMetricsDTO,
    ProfitMetricsDTO,
    RevenueMetricsDTO,
    TopProductDTO,
)
from domain.business.services import BusinessDomainService
from domain.dashboard.services import DashboardMetricsService
from shared.exceptions.specific import (
    ForbiddenError,
)

logger = logging.getLogger(__name__)


class GetDashboardSummaryUseCase:
    """Use case for getting complete dashboard summary."""

    def __init__(
        self,
        dashboard_metrics_service: DashboardMetricsService,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,
        period: str = "month",  # today, week, month, year
    ) -> None:
        """Initialize use case."""
        self.dashboard_metrics_service = dashboard_metrics_service
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id
        self.period = period

    def execute(self) -> DashboardSummaryDTO:
        """Execute getting dashboard summary."""
        # Check if user has access to business
        if not self.business_domain_service.user_has_access(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="You don't have access to this business",
                code="PERMISSION_DENIED",
            )

        # Calculate date range based on period
        now = timezone.now()
        start_date = None
        end_date = now

        if self.period == "today":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif self.period == "week":
            week_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            start_date = week_start - timedelta(days=now.weekday())
        elif self.period == "month":
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif self.period == "year":
            start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

        # Calculate all metrics
        revenue_metrics_data = self.dashboard_metrics_service.calculate_revenue_metrics(
            start_date=start_date,
            end_date=end_date,
        )
        expense_metrics_data = self.dashboard_metrics_service.calculate_expense_metrics(
            start_date=start_date,
            end_date=end_date,
        )
        profit_metrics_data = self.dashboard_metrics_service.calculate_profit_metrics(
            revenue_metrics=revenue_metrics_data,
            expense_metrics=expense_metrics_data,
        )
        inventory_metrics_data = self.dashboard_metrics_service.calculate_inventory_metrics()
        customer_metrics_data = self.dashboard_metrics_service.calculate_customer_metrics()
        top_products_data = self.dashboard_metrics_service.get_top_products(limit=10)

        # Convert to DTOs
        revenue_metrics = RevenueMetricsDTO(
            total_revenue=revenue_metrics_data["total_revenue"],
            revenue_today=revenue_metrics_data["revenue_today"],
            revenue_this_week=revenue_metrics_data["revenue_this_week"],
            revenue_this_month=revenue_metrics_data["revenue_this_month"],
            revenue_this_year=revenue_metrics_data["revenue_this_year"],
            average_order_value=revenue_metrics_data["average_order_value"],
            total_orders=revenue_metrics_data["total_orders"],
            orders_today=revenue_metrics_data["orders_today"],
            orders_this_week=revenue_metrics_data["orders_this_week"],
            orders_this_month=revenue_metrics_data["orders_this_month"],
        )

        expense_metrics = ExpenseMetricsDTO(
            total_expenses=expense_metrics_data["total_expenses"],
            expenses_today=expense_metrics_data["expenses_today"],
            expenses_this_week=expense_metrics_data["expenses_this_week"],
            expenses_this_month=expense_metrics_data["expenses_this_month"],
            expenses_this_year=expense_metrics_data["expenses_this_year"],
            salary_expenses=expense_metrics_data["salary_expenses"],
            other_expenses=expense_metrics_data["other_expenses"],
        )

        profit_metrics = ProfitMetricsDTO(
            total_profit=profit_metrics_data["total_profit"],
            profit_today=profit_metrics_data["profit_today"],
            profit_this_week=profit_metrics_data["profit_this_week"],
            profit_this_month=profit_metrics_data["profit_this_month"],
            profit_margin_percentage=profit_metrics_data["profit_margin_percentage"],
        )

        inventory_metrics = InventoryMetricsDTO(
            total_products=inventory_metrics_data["total_products"],
            low_stock_products=inventory_metrics_data["low_stock_products"],
            expired_products=inventory_metrics_data["expired_products"],
            total_inventory_value=inventory_metrics_data["total_inventory_value"],
            products_on_promotion=inventory_metrics_data["products_on_promotion"],
        )

        customer_metrics = CustomerMetricsDTO(
            total_customers=customer_metrics_data["total_customers"],
            new_customers_today=customer_metrics_data["new_customers_today"],
            new_customers_this_week=customer_metrics_data["new_customers_this_week"],
            new_customers_this_month=customer_metrics_data["new_customers_this_month"],
            active_customers=customer_metrics_data["active_customers"],
            total_credit_amount=customer_metrics_data["total_credit_amount"],
            overdue_credit_amount=customer_metrics_data["overdue_credit_amount"],
        )

        top_products = [
            TopProductDTO(
                product_id=p["product_id"],
                product_name=p["product_name"],
                total_sold=p["total_sold"],
                total_revenue=p["total_revenue"],
                quantity_available=p["quantity_available"],
            )
            for p in top_products_data
        ]

        return DashboardSummaryDTO(
            business_id=self.business_id,
            period=self.period,
            revenue=revenue_metrics,
            expenses=expense_metrics,
            profit=profit_metrics,
            inventory=inventory_metrics,
            customers=customer_metrics,
            top_products=top_products,
            generated_at=timezone.now(),
        )
