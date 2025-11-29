"""Dashboard use cases."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from django.utils import timezone

from application.dto.dashboard_dto import (
    CashierDailyDataDTO,
    CashierInfoDTO,
    CashierStatisticsDTO,
    CategoryInfoDTO,
    CategoryStatisticsDTO,
    CustomerMetricsDTO,
    DailyMetricsDTO,
    DashboardDailyResponseDTO,
    DashboardSummaryDTO,
    ExpenseMetricsDTO,
    InventoryMetricsDTO,
    PeriodTotalsDTO,
    ProductDetailStatisticsDTO,
    ProductInfoDTO,
    ProductMarginDTO,
    ProductStatisticsDTO,
    ProfitMetricsDTO,
    RecentSaleDTO,
    RevenueMetricsDTO,
    SalesPerformanceDTO,
    SubCategoryInfoDTO,
    SubCategoryStatisticsDTO,
    TopCategoryDTO,
    TopCustomerDTO,
    TopProductDTO,
    TrendsDTO,
)
from domain.business.services import BusinessDomainService
from domain.dashboard.services import DashboardMetricsService
from domain.inventory.repositories import (
    CategoryRepository,
    ProductRepository,
    SubCategoryRepository,
)
from shared.exceptions.specific import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
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
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> None:
        """Initialize use case."""
        self.dashboard_metrics_service = dashboard_metrics_service
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id
        self.start_date = start_date
        self.end_date = end_date

    def _validate_and_normalize_dates(
        self,
    ) -> tuple[datetime, datetime]:
        """
        Validate and normalize date range. Defaults to current week if not provided.

        Returns:
            Tuple of (start_date, end_date)

        Raises:
            BadRequestError: If dates are invalid
        """
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Default to current week if dates not provided
        if not self.start_date and not self.end_date:
            week_start = today_start - timedelta(days=now.weekday())
            start_date = week_start
            end_date = now
        elif self.start_date and self.end_date:
            start_date = self.start_date
            end_date = self.end_date
        else:
            raise BadRequestError(
                detail="Both start_date and end_date must be provided, or neither",
                code="INVALID_DATE_RANGE",
            )

        # Normalize dates
        if timezone.is_naive(start_date):
            start_date = timezone.make_aware(start_date)
        if timezone.is_naive(end_date):
            end_date = timezone.make_aware(end_date)

        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        # Validate date range
        if start_date > end_date:
            raise BadRequestError(
                detail="start_date cannot be after end_date",
                code="INVALID_DATE_RANGE",
            )

        # Don't allow future dates
        if start_date > now:
            raise BadRequestError(
                detail="start_date cannot be in the future",
                code="INVALID_DATE_RANGE",
            )
        if end_date > now:
            end_date = now

        return start_date, end_date

    def execute(self) -> DashboardSummaryDTO:
        """Execute getting dashboard summary."""
        if not self.business_domain_service.is_user_owner(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="Only the business owner can access the dashboard",
                code="PERMISSION_DENIED",
            )

        # Validate and normalize dates
        start_date, end_date = self._validate_and_normalize_dates()

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
        top_products_data = self.dashboard_metrics_service.get_top_products(
            start_date=start_date, end_date=end_date, limit=10
        )

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
            period_start=start_date,
            period_end=end_date,
            revenue=revenue_metrics,
            expenses=expense_metrics,
            profit=profit_metrics,
            inventory=inventory_metrics,
            customers=customer_metrics,
            top_products=top_products,
            generated_at=timezone.now(),
        )


class GetDashboardDailyUseCase:
    """Use case for getting daily dashboard data with date range filtering."""

    def __init__(
        self,
        dashboard_metrics_service: DashboardMetricsService,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        recent_sales_limit: int = 10,
    ) -> None:
        """Initialize use case."""
        self.dashboard_metrics_service = dashboard_metrics_service
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id
        self.start_date = start_date
        self.end_date = end_date
        self.recent_sales_limit = recent_sales_limit

    def _validate_and_normalize_dates(
        self,
    ) -> tuple[datetime, datetime]:
        """
        Validate and normalize date range. Defaults to current week if not provided.

        Returns:
            Tuple of (start_date, end_date)

        Raises:
            ValidationError: If dates are invalid
        """
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if not self.start_date and not self.end_date:
            week_start = today_start - timedelta(days=now.weekday())
            start_date = week_start
            end_date = now
        elif self.start_date and self.end_date:
            start_date = self.start_date
            end_date = self.end_date
        else:
            raise BadRequestError(
                detail="Both start_date and end_date must be provided, or neither",
                code="INVALID_DATE_RANGE",
            )

        if timezone.is_naive(start_date):
            start_date = timezone.make_aware(start_date)
        if timezone.is_naive(end_date):
            end_date = timezone.make_aware(end_date)

        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        if start_date > end_date:
            raise BadRequestError(
                detail="start_date cannot be after end_date",
                code="INVALID_DATE_RANGE",
            )

        if start_date > now:
            raise BadRequestError(
                detail="start_date cannot be in the future",
                code="INVALID_DATE_RANGE",
            )
        if end_date > now:
            end_date = now

        if self.recent_sales_limit < 1 or self.recent_sales_limit > 100:
            raise BadRequestError(
                detail="recent_sales_limit must be between 1 and 100",
                code="INVALID_LIMIT",
            )

        return start_date, end_date

    def execute(self) -> DashboardDailyResponseDTO:
        """Execute getting daily dashboard data."""
        if not self.business_domain_service.is_user_owner(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="Only the business owner can access the dashboard",
                code="PERMISSION_DENIED",
            )

        start_date, end_date = self._validate_and_normalize_dates()

        daily_metrics_raw = self.dashboard_metrics_service.calculate_daily_metrics(
            start_date=start_date,
            end_date=end_date,
        )

        daily_metrics = self.dashboard_metrics_service.calculate_daily_profits(
            daily_metrics=daily_metrics_raw,
            start_date=start_date,
            end_date=end_date,
        )

        daily_data = [
            DailyMetricsDTO(
                date=dm["date"],
                complete_revenue=dm["complete_revenue"],
                credit_revenue=dm["credit_revenue"],
                total_revenue=dm["total_revenue"],
                profit=dm["profit"],
                gross_profit=dm["gross_profit"],
                net_profit=dm["net_profit"],
                total_sales=dm["total_sales"],
                total_expenses=dm["total_expenses"],
                credit_outstanding=dm["credit_outstanding"],
            )
            for dm in daily_metrics
        ]

        total_revenue = Decimal(sum(float(dm.total_revenue) for dm in daily_data))
        total_sales = sum(dm.total_sales for dm in daily_data)
        total_expenses = Decimal(sum(float(dm.total_expenses) for dm in daily_data))
        credit_outstanding = Decimal(sum(float(dm.credit_outstanding) for dm in daily_data))
        gross_profit = Decimal(sum(float(dm.gross_profit) for dm in daily_data))
        net_profit = Decimal(sum(float(dm.net_profit) for dm in daily_data))

        totals = PeriodTotalsDTO(
            total_revenue=total_revenue.quantize(Decimal("0.01")),
            total_sales=total_sales,
            credit_outstanding=credit_outstanding.quantize(Decimal("0.01")),
            total_expenses=total_expenses.quantize(Decimal("0.01")),
            gross_profit=gross_profit.quantize(Decimal("0.01")),
            net_profit=net_profit.quantize(Decimal("0.01")),
        )

        complete_revenue = Decimal(sum(float(dm.complete_revenue) for dm in daily_data))
        credit_revenue = Decimal(sum(float(dm.credit_revenue) for dm in daily_data))
        sales_performance = SalesPerformanceDTO(
            credit_revenue=credit_revenue.quantize(Decimal("0.01")),
            total_revenue=total_revenue.quantize(Decimal("0.01")),
            complete_revenue=complete_revenue.quantize(Decimal("0.01")),
            profit=net_profit.quantize(Decimal("0.01")),
        )

        top_products_raw = self.dashboard_metrics_service.get_top_products(
            start_date=start_date, end_date=end_date, limit=10
        )
        top_products = [
            TopProductDTO(
                product_id=p["product_id"],
                product_name=p["product_name"],
                total_sold=p["total_sold"],
                total_revenue=p["total_revenue"],
                quantity_available=p["quantity_available"],
            )
            for p in top_products_raw
        ]

        top_categories_raw = self.dashboard_metrics_service.get_top_categories(
            start_date=start_date,
            end_date=end_date,
            limit=10,
        )
        top_categories = [
            TopCategoryDTO(
                category_id=c["category_id"],
                category_name=c["category_name"],
                total_revenue=c["total_revenue"],
                total_quantity_sold=c["total_quantity_sold"],
                number_of_sales=c["number_of_sales"],
            )
            for c in top_categories_raw
        ]

        recent_sales_raw = self.dashboard_metrics_service.get_recent_sales(
            limit=self.recent_sales_limit
        )
        recent_sales = [
            RecentSaleDTO(
                invoice_id=s["invoice_id"],
                invoice_number=s["invoice_number"],
                customer_name=s["customer_name"],
                total=s["total"],
                status=s["status"],
                created_at=s["created_at"],
            )
            for s in recent_sales_raw
        ]

        product_stats_daily = self.dashboard_metrics_service.calculate_product_statistics(
            start_date=start_date,
            end_date=end_date,
            group_by="daily",
        )
        product_stats_weekly = self.dashboard_metrics_service.calculate_product_statistics(
            start_date=start_date,
            end_date=end_date,
            group_by="weekly",
        )

        product_statistics = {
            "daily": [
                ProductStatisticsDTO(
                    product_id=ps["product_id"],
                    product_name=ps["product_name"],
                    date=ps["date"],
                    quantity_sold=ps["quantity_sold"],
                    revenue=ps["revenue"],
                    cost=ps["cost"],
                    profit=ps["profit"],
                    margin_percentage=ps["margin_percentage"],
                )
                for ps in product_stats_daily
            ],
            "weekly": [
                ProductStatisticsDTO(
                    product_id=ps["product_id"],
                    product_name=ps["product_name"],
                    date=ps["date"],
                    quantity_sold=ps["quantity_sold"],
                    revenue=ps["revenue"],
                    cost=ps["cost"],
                    profit=ps["profit"],
                    margin_percentage=ps["margin_percentage"],
                )
                for ps in product_stats_weekly
            ],
        }

        product_margins_raw = self.dashboard_metrics_service.calculate_product_margins(
            start_date=start_date,
            end_date=end_date,
        )
        product_margins = [
            ProductMarginDTO(
                product_id=pm["product_id"],
                product_name=pm["product_name"],
                total_quantity_sold=pm["total_quantity_sold"],
                total_revenue=pm["total_revenue"],
                total_cost=pm["total_cost"],
                total_profit=pm["total_profit"],
                margin_percentage=pm["margin_percentage"],
            )
            for pm in product_margins_raw
        ]

        return DashboardDailyResponseDTO(
            business_id=self.business_id,
            period_start=start_date,
            period_end=end_date,
            totals=totals,
            daily_data=daily_data,
            sales_performance=sales_performance,
            top_products=top_products,
            top_categories=top_categories,
            recent_sales=recent_sales,
            product_statistics=product_statistics,
            product_margins=product_margins,
            generated_at=timezone.now(),
        )


class GetProductStatisticsUseCase:
    """Use case for getting detailed product statistics."""

    def __init__(
        self,
        dashboard_metrics_service: DashboardMetricsService,
        business_domain_service: BusinessDomainService,
        product_repository: ProductRepository,
        business_id: UUID,
        product_id: UUID,
        user_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> None:
        """Initialize use case."""
        self.dashboard_metrics_service = dashboard_metrics_service
        self.business_domain_service = business_domain_service
        self.product_repository = product_repository
        self.business_id = business_id
        self.product_id = product_id
        self.user_id = user_id
        self.start_date = start_date
        self.end_date = end_date

    def _validate_and_normalize_dates(
        self,
    ) -> tuple[datetime, datetime]:
        """Validate and normalize date range."""
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if not self.start_date and not self.end_date:
            week_start = today_start - timedelta(days=now.weekday())
            start_date = week_start
            end_date = now
        elif self.start_date and self.end_date:
            start_date = self.start_date
            end_date = self.end_date
        else:
            raise BadRequestError(
                detail="Both start_date and end_date must be provided, or neither",
                code="INVALID_DATE_RANGE",
            )

        if timezone.is_naive(start_date):
            start_date = timezone.make_aware(start_date)
        if timezone.is_naive(end_date):
            end_date = timezone.make_aware(end_date)

        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        if start_date > end_date:
            raise BadRequestError(
                detail="start_date cannot be after end_date",
                code="INVALID_DATE_RANGE",
            )

        if start_date > now:
            raise BadRequestError(
                detail="start_date cannot be in the future",
                code="INVALID_DATE_RANGE",
            )
        if end_date > now:
            end_date = now

        return start_date, end_date

    def _calculate_previous_period(
        self, start_date: datetime, end_date: datetime
    ) -> tuple[datetime, datetime]:
        """Calculate previous period of same duration."""
        duration = end_date - start_date
        previous_end = start_date - timedelta(seconds=1)
        previous_start = previous_end - duration
        return previous_start, previous_end

    def execute(self) -> ProductDetailStatisticsDTO:
        """Execute getting product statistics."""
        if not self.business_domain_service.is_user_owner(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="Only the business owner can access the dashboard",
                code="PERMISSION_DENIED",
            )

        # Validate product belongs to business
        product = self.product_repository.get_by_id(self.product_id)
        if not product or product.business_id != self.business_id:
            raise NotFoundError(
                detail="Product not found",
                code="PRODUCT_NOT_FOUND",
            )

        start_date, end_date = self._validate_and_normalize_dates()

        # Get current period statistics
        stats = self.dashboard_metrics_service.get_product_detail_statistics(
            product_id=self.product_id,
            start_date=start_date,
            end_date=end_date,
        )

        if not stats:
            raise NotFoundError(
                detail="Product statistics not found",
                code="STATISTICS_NOT_FOUND",
            )

        # Calculate previous period
        previous_start, previous_end = self._calculate_previous_period(start_date, end_date)

        # Get previous period statistics for trends
        previous_stats = self.dashboard_metrics_service.get_product_detail_statistics(
            product_id=self.product_id,
            start_date=previous_start,
            end_date=previous_end,
        )

        # Calculate trends
        trends = {}
        current_totals = stats["totals"]
        previous_totals = previous_stats.get("totals", {}) if previous_stats else {}

        for metric in ["total_revenue", "quantity_sold", "total_profit"]:
            current_value = Decimal(str(current_totals.get(metric, 0)))
            previous_value = Decimal(str(previous_totals.get(metric, 0)))

            trend_data = self.dashboard_metrics_service.calculate_trends(
                current_value=current_value,
                previous_value=previous_value,
                previous_period_start=previous_start,
                previous_period_end=previous_end,
            )

            trends[metric] = TrendsDTO(
                previous_period_start=trend_data["previous_period_start"],
                previous_period_end=trend_data["previous_period_end"],
                current_value=trend_data["current_value"],
                previous_value=trend_data["previous_value"],
                change_amount=trend_data["change_amount"],
                change_percentage=trend_data["change_percentage"],
                trend_direction=trend_data["trend_direction"],
            )

        # Convert daily data
        daily_data = [
            ProductStatisticsDTO(
                product_id=row["product_id"],
                product_name=row["product_name"],
                date=row["date"],
                quantity_sold=row["quantity_sold"],
                revenue=row["revenue"],
                cost=row["cost"],
                profit=row["profit"],
                margin_percentage=row["margin_percentage"],
            )
            for row in stats["daily_data"]
        ]

        # Convert top customers
        top_customers = [
            TopCustomerDTO(
                customer_id=row["customer_id"],
                customer_name=row["customer_name"],
                total_purchases=row["total_purchases"],
                total_revenue=row["total_revenue"],
            )
            for row in stats["top_customers"]
        ]

        return ProductDetailStatisticsDTO(
            product=ProductInfoDTO(
                product_id=stats["product"]["product_id"],
                product_name=stats["product"]["product_name"],
                category_id=stats["product"]["category_id"],
                category_name=stats["product"]["category_name"],
                subcategory_id=stats["product"]["subcategory_id"],
                subcategory_name=stats["product"]["subcategory_name"],
            ),
            period_start=start_date,
            period_end=end_date,
            totals=current_totals,
            daily_data=daily_data,
            trends=trends,
            top_customers=top_customers,
        )


class GetCategoryStatisticsUseCase:
    """Use case for getting category statistics."""

    def __init__(
        self,
        dashboard_metrics_service: DashboardMetricsService,
        business_domain_service: BusinessDomainService,
        category_repository: CategoryRepository,
        business_id: UUID,
        category_id: UUID,
        user_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> None:
        """Initialize use case."""
        self.dashboard_metrics_service = dashboard_metrics_service
        self.business_domain_service = business_domain_service
        self.category_repository = category_repository
        self.business_id = business_id
        self.category_id = category_id
        self.user_id = user_id
        self.start_date = start_date
        self.end_date = end_date

    def _validate_and_normalize_dates(
        self,
    ) -> tuple[datetime, datetime]:
        """Validate and normalize date range."""
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if not self.start_date and not self.end_date:
            week_start = today_start - timedelta(days=now.weekday())
            start_date = week_start
            end_date = now
        elif self.start_date and self.end_date:
            start_date = self.start_date
            end_date = self.end_date
        else:
            raise BadRequestError(
                detail="Both start_date and end_date must be provided, or neither",
                code="INVALID_DATE_RANGE",
            )

        if timezone.is_naive(start_date):
            start_date = timezone.make_aware(start_date)
        if timezone.is_naive(end_date):
            end_date = timezone.make_aware(end_date)

        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        if start_date > end_date:
            raise BadRequestError(
                detail="start_date cannot be after end_date",
                code="INVALID_DATE_RANGE",
            )

        if start_date > now:
            raise BadRequestError(
                detail="start_date cannot be in the future",
                code="INVALID_DATE_RANGE",
            )
        if end_date > now:
            end_date = now

        return start_date, end_date

    def _calculate_previous_period(
        self, start_date: datetime, end_date: datetime
    ) -> tuple[datetime, datetime]:
        """Calculate previous period of same duration."""
        duration = end_date - start_date
        previous_end = start_date - timedelta(seconds=1)
        previous_start = previous_end - duration
        return previous_start, previous_end

    def execute(self) -> CategoryStatisticsDTO:
        """Execute getting category statistics."""
        if not self.business_domain_service.is_user_owner(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="Only the business owner can access the dashboard",
                code="PERMISSION_DENIED",
            )

        # Validate category belongs to business
        category = self.category_repository.get_by_id(self.category_id)
        if not category or category.business_id != self.business_id:
            raise NotFoundError(
                detail="Category not found",
                code="CATEGORY_NOT_FOUND",
            )

        start_date, end_date = self._validate_and_normalize_dates()

        # Get current period statistics
        stats = self.dashboard_metrics_service.get_category_statistics(
            category_id=self.category_id,
            start_date=start_date,
            end_date=end_date,
        )

        if not stats:
            raise NotFoundError(
                detail="Category statistics not found",
                code="STATISTICS_NOT_FOUND",
            )

        # Calculate previous period
        previous_start, previous_end = self._calculate_previous_period(start_date, end_date)

        # Get previous period statistics for trends
        previous_stats = self.dashboard_metrics_service.get_category_statistics(
            category_id=self.category_id,
            start_date=previous_start,
            end_date=previous_end,
        )

        # Calculate trends
        trends = {}
        current_totals = stats["totals"]
        previous_totals = previous_stats.get("totals", {}) if previous_stats else {}

        for metric in ["total_revenue", "quantity_sold", "total_profit"]:
            current_value = Decimal(str(current_totals.get(metric, 0)))
            previous_value = Decimal(str(previous_totals.get(metric, 0)))

            trend_data = self.dashboard_metrics_service.calculate_trends(
                current_value=current_value,
                previous_value=previous_value,
                previous_period_start=previous_start,
                previous_period_end=previous_end,
            )

            trends[metric] = TrendsDTO(
                previous_period_start=trend_data["previous_period_start"],
                previous_period_end=trend_data["previous_period_end"],
                current_value=trend_data["current_value"],
                previous_value=trend_data["previous_value"],
                change_amount=trend_data["change_amount"],
                change_percentage=trend_data["change_percentage"],
                trend_direction=trend_data["trend_direction"],
            )

        # Convert top products
        top_products = [
            TopProductDTO(
                product_id=row["product_id"],
                product_name=row["product_name"],
                total_sold=row["total_sold"],
                total_revenue=row["total_revenue"],
                quantity_available=row["quantity_available"],
            )
            for row in stats["top_products"]
        ]

        return CategoryStatisticsDTO(
            category=CategoryInfoDTO(
                category_id=stats["category"]["category_id"],
                category_name=stats["category"]["category_name"],
            ),
            period_start=start_date,
            period_end=end_date,
            totals=current_totals,
            top_products=top_products,
            daily_data=stats["daily_data"],
            trends=trends,
        )


class GetSubCategoryStatisticsUseCase:
    """Use case for getting subcategory statistics."""

    def __init__(
        self,
        dashboard_metrics_service: DashboardMetricsService,
        business_domain_service: BusinessDomainService,
        subcategory_repository: SubCategoryRepository,
        business_id: UUID,
        subcategory_id: UUID,
        user_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> None:
        """Initialize use case."""
        self.dashboard_metrics_service = dashboard_metrics_service
        self.business_domain_service = business_domain_service
        self.subcategory_repository = subcategory_repository
        self.business_id = business_id
        self.subcategory_id = subcategory_id
        self.user_id = user_id
        self.start_date = start_date
        self.end_date = end_date

    def _validate_and_normalize_dates(
        self,
    ) -> tuple[datetime, datetime]:
        """Validate and normalize date range."""
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if not self.start_date and not self.end_date:
            week_start = today_start - timedelta(days=now.weekday())
            start_date = week_start
            end_date = now
        elif self.start_date and self.end_date:
            start_date = self.start_date
            end_date = self.end_date
        else:
            raise BadRequestError(
                detail="Both start_date and end_date must be provided, or neither",
                code="INVALID_DATE_RANGE",
            )

        if timezone.is_naive(start_date):
            start_date = timezone.make_aware(start_date)
        if timezone.is_naive(end_date):
            end_date = timezone.make_aware(end_date)

        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        if start_date > end_date:
            raise BadRequestError(
                detail="start_date cannot be after end_date",
                code="INVALID_DATE_RANGE",
            )

        if start_date > now:
            raise BadRequestError(
                detail="start_date cannot be in the future",
                code="INVALID_DATE_RANGE",
            )
        if end_date > now:
            end_date = now

        return start_date, end_date

    def _calculate_previous_period(
        self, start_date: datetime, end_date: datetime
    ) -> tuple[datetime, datetime]:
        """Calculate previous period of same duration."""
        duration = end_date - start_date
        previous_end = start_date - timedelta(seconds=1)
        previous_start = previous_end - duration
        return previous_start, previous_end

    def execute(self) -> SubCategoryStatisticsDTO:
        """Execute getting subcategory statistics."""
        if not self.business_domain_service.is_user_owner(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="Only the business owner can access the dashboard",
                code="PERMISSION_DENIED",
            )

        # Validate subcategory belongs to business
        subcategory = self.subcategory_repository.get_by_id(self.subcategory_id)
        if not subcategory or subcategory.business_id != self.business_id:
            raise NotFoundError(
                detail="Subcategory not found",
                code="SUBCATEGORY_NOT_FOUND",
            )

        start_date, end_date = self._validate_and_normalize_dates()

        # Get current period statistics
        stats = self.dashboard_metrics_service.get_subcategory_statistics(
            subcategory_id=self.subcategory_id,
            start_date=start_date,
            end_date=end_date,
        )

        if not stats:
            raise NotFoundError(
                detail="Subcategory statistics not found",
                code="STATISTICS_NOT_FOUND",
            )

        # Calculate previous period
        previous_start, previous_end = self._calculate_previous_period(start_date, end_date)

        # Get previous period statistics for trends
        previous_stats = self.dashboard_metrics_service.get_subcategory_statistics(
            subcategory_id=self.subcategory_id,
            start_date=previous_start,
            end_date=previous_end,
        )

        # Calculate trends
        trends = {}
        current_totals = stats["totals"]
        previous_totals = previous_stats.get("totals", {}) if previous_stats else {}

        for metric in ["total_revenue", "quantity_sold", "total_profit"]:
            current_value = Decimal(str(current_totals.get(metric, 0)))
            previous_value = Decimal(str(previous_totals.get(metric, 0)))

            trend_data = self.dashboard_metrics_service.calculate_trends(
                current_value=current_value,
                previous_value=previous_value,
                previous_period_start=previous_start,
                previous_period_end=previous_end,
            )

            trends[metric] = TrendsDTO(
                previous_period_start=trend_data["previous_period_start"],
                previous_period_end=trend_data["previous_period_end"],
                current_value=trend_data["current_value"],
                previous_value=trend_data["previous_value"],
                change_amount=trend_data["change_amount"],
                change_percentage=trend_data["change_percentage"],
                trend_direction=trend_data["trend_direction"],
            )

        # Convert top products
        top_products = [
            TopProductDTO(
                product_id=row["product_id"],
                product_name=row["product_name"],
                total_sold=row["total_sold"],
                total_revenue=row["total_revenue"],
                quantity_available=row["quantity_available"],
            )
            for row in stats["top_products"]
        ]

        return SubCategoryStatisticsDTO(
            subcategory=SubCategoryInfoDTO(
                subcategory_id=stats["subcategory"]["subcategory_id"],
                subcategory_name=stats["subcategory"]["subcategory_name"],
                category_id=stats["subcategory"]["category_id"],
                category_name=stats["subcategory"]["category_name"],
            ),
            period_start=start_date,
            period_end=end_date,
            totals=current_totals,
            top_products=top_products,
            daily_data=stats["daily_data"],
            trends=trends,
        )


class GetCashierStatisticsUseCase:
    """Use case for getting cashier statistics."""

    def __init__(
        self,
        dashboard_metrics_service: DashboardMetricsService,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        cashier_id: UUID,
        user_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> None:
        """Initialize use case."""
        self.dashboard_metrics_service = dashboard_metrics_service
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.cashier_id = cashier_id
        self.user_id = user_id
        self.start_date = start_date
        self.end_date = end_date

    def _validate_and_normalize_dates(
        self,
    ) -> tuple[datetime, datetime]:
        """Validate and normalize date range."""
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if not self.start_date and not self.end_date:
            week_start = today_start - timedelta(days=now.weekday())
            start_date = week_start
            end_date = now
        elif self.start_date and self.end_date:
            start_date = self.start_date
            end_date = self.end_date
        else:
            raise BadRequestError(
                detail="Both start_date and end_date must be provided, or neither",
                code="INVALID_DATE_RANGE",
            )

        if timezone.is_naive(start_date):
            start_date = timezone.make_aware(start_date)
        if timezone.is_naive(end_date):
            end_date = timezone.make_aware(end_date)

        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        if start_date > end_date:
            raise BadRequestError(
                detail="start_date cannot be after end_date",
                code="INVALID_DATE_RANGE",
            )

        if start_date > now:
            raise BadRequestError(
                detail="start_date cannot be in the future",
                code="INVALID_DATE_RANGE",
            )
        if end_date > now:
            end_date = now

        return start_date, end_date

    def _calculate_previous_period(
        self, start_date: datetime, end_date: datetime
    ) -> tuple[datetime, datetime]:
        """Calculate previous period of same duration."""
        duration = end_date - start_date
        previous_end = start_date - timedelta(seconds=1)
        previous_start = previous_end - duration
        return previous_start, previous_end

    def execute(self) -> CashierStatisticsDTO:
        """Execute getting cashier statistics."""
        if not self.business_domain_service.is_user_owner(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="Only the business owner can access the dashboard",
                code="PERMISSION_DENIED",
            )

        # Validate cashier is a member of the business
        if not self.business_domain_service.user_has_access(self.business_id, self.cashier_id):
            raise NotFoundError(
                detail="Cashier not found or not a member of this business",
                code="CASHIER_NOT_FOUND",
            )

        start_date, end_date = self._validate_and_normalize_dates()

        # Get current period statistics
        stats = self.dashboard_metrics_service.get_cashier_statistics(
            cashier_id=self.cashier_id,
            start_date=start_date,
            end_date=end_date,
        )

        if not stats:
            raise NotFoundError(
                detail="Cashier statistics not found",
                code="STATISTICS_NOT_FOUND",
            )

        # Calculate previous period
        previous_start, previous_end = self._calculate_previous_period(start_date, end_date)

        # Get previous period statistics for trends
        previous_stats = self.dashboard_metrics_service.get_cashier_statistics(
            cashier_id=self.cashier_id,
            start_date=previous_start,
            end_date=previous_end,
        )

        # Calculate trends
        trends = {}
        current_totals = stats["totals"]
        previous_totals = previous_stats.get("totals", {}) if previous_stats else {}

        for metric in ["total_sales", "total_revenue", "average_sale_value"]:
            current_value = Decimal(str(current_totals.get(metric, 0)))
            previous_value = Decimal(str(previous_totals.get(metric, 0)))

            trend_data = self.dashboard_metrics_service.calculate_trends(
                current_value=current_value,
                previous_value=previous_value,
                previous_period_start=previous_start,
                previous_period_end=previous_end,
            )

            trends[metric] = TrendsDTO(
                previous_period_start=trend_data["previous_period_start"],
                previous_period_end=trend_data["previous_period_end"],
                current_value=trend_data["current_value"],
                previous_value=trend_data["previous_value"],
                change_amount=trend_data["change_amount"],
                change_percentage=trend_data["change_percentage"],
                trend_direction=trend_data["trend_direction"],
            )

        # Get ranking
        ranking = self.dashboard_metrics_service.get_cashier_ranking(
            cashier_id=self.cashier_id,
            start_date=start_date,
            end_date=end_date,
        )

        # Convert daily data
        daily_data = [
            CashierDailyDataDTO(
                date=row["date"],
                total_sales=row["total_sales"],
                total_revenue=row["total_revenue"],
                total_quantity_sold=row["total_quantity_sold"],
                average_sale_value=row["average_sale_value"],
                customers_served=row["customers_served"],
            )
            for row in stats["daily_data"]
        ]

        return CashierStatisticsDTO(
            cashier=CashierInfoDTO(
                cashier_id=stats["cashier"]["cashier_id"],
                cashier_name=stats["cashier"]["cashier_name"],
                cashier_email=stats["cashier"]["cashier_email"],
                phone_number=stats["cashier"].get("phone_number"),
                avatar_url=stats["cashier"].get("avatar_url"),
                role=stats["cashier"].get("role", "unknown"),
                is_active=stats["cashier"].get("is_active", False),
                joined_at=stats["cashier"].get("joined_at", start_date),
                left_at=stats["cashier"].get("left_at"),
            ),
            period_start=start_date,
            period_end=end_date,
            totals=current_totals,
            lifetime_totals=stats.get("lifetime_totals", {}),
            daily_data=daily_data,
            trends=trends,
            ranking=ranking,
        )
