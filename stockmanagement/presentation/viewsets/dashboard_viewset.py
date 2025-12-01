"""Dashboard ViewSet for metrics and analytics."""

from __future__ import annotations

from decimal import Decimal

from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from application.use_cases.dashboard_use_cases import (
    GetCashierStatisticsUseCase,
    GetCategoryStatisticsUseCase,
    GetDashboardDailyUseCase,
    GetDashboardSummaryUseCase,
    GetProductStatisticsUseCase,
    GetSubCategoryStatisticsUseCase,
)
from domain.business.services import BusinessDomainService
from domain.dashboard.services import DashboardMetricsService
from infrastructure.persistence.repositories import (
    BusinessMemberRepositoryImpl,
    BusinessRepositoryImpl,
    CategoryRepositoryImpl,
    ProductRepositoryImpl,
    SubCategoryRepositoryImpl,
)
from infrastructure.persistence.repositories.dashboard_repositories import (
    DashboardCashierStatisticsRepositoryImpl,
    DashboardCategoryStatisticsRepositoryImpl,
    DashboardMetricsRepositoryImpl,
    DashboardProductStatisticsRepositoryImpl,
    DashboardSubCategoryStatisticsRepositoryImpl,
)
from presentation.serializers.dashboard_serializers import (
    CashierStatisticsQuerySerializer,
    CategoryStatisticsQuerySerializer,
    DashboardDailyQuerySerializer,
    DashboardSummaryQuerySerializer,
    ProductStatisticsQuerySerializer,
    SubCategoryStatisticsQuerySerializer,
)
from shared.views.base_viewset import BaseViewSet


class DashboardViewSet(BaseViewSet):
    """ViewSet for dashboard metrics and analytics."""

    permission_classes = [IsAuthenticated]

    def _get_business_domain_service(self) -> BusinessDomainService:
        """Get business domain service instance."""
        return BusinessDomainService(
            business_repository=BusinessRepositoryImpl(),
            business_member_repository=BusinessMemberRepositoryImpl(),
        )

    @swagger_auto_schema(
        operation_summary="Get dashboard summary",
        operation_description="Get complete dashboard summary with all metrics for a business.",
        query_serializer=DashboardSummaryQuerySerializer,
        responses={200: "Dashboard summary", 400: "Bad Request", 403: "Permission denied"},
        tags=["Dashboard"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="summary",
    )
    def get_summary(self, request: Request) -> Response:
        """Get dashboard summary for a business."""
        try:
            # Validate query parameters
            query_serializer = DashboardSummaryQuerySerializer(data=request.query_params)
            if not query_serializer.is_valid():
                return self.handle_validation_error(query_serializer)

            business_id = query_serializer.validated_data["business_id"]
            start_date = query_serializer.validated_data.get("start_date")
            end_date = query_serializer.validated_data.get("end_date")

            if not self._get_business_domain_service().is_user_owner(business_id, request.user.id):
                return self.error(
                    message="Only the business owner can access the dashboard",
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="PERMISSION_DENIED",
                )

            # Create dashboard metrics service
            metrics_service = DashboardMetricsService(
                metrics_repository=DashboardMetricsRepositoryImpl(),
                product_statistics_repository=DashboardProductStatisticsRepositoryImpl(),
                category_statistics_repository=DashboardCategoryStatisticsRepositoryImpl(),
                subcategory_statistics_repository=DashboardSubCategoryStatisticsRepositoryImpl(),
                cashier_statistics_repository=DashboardCashierStatisticsRepositoryImpl(),
                business_id=business_id,
            )

            use_case = GetDashboardSummaryUseCase(
                dashboard_metrics_service=metrics_service,
                business_domain_service=self._get_business_domain_service(),
                business_id=business_id,
                user_id=request.user.id,
                start_date=start_date,
                end_date=end_date,
            )
            dashboard_dto = use_case.execute()

            return self.success(
                message="Dashboard summary retrieved successfully",
                data={
                    "business_id": str(dashboard_dto.business_id),
                    "period": {
                        "start_date": dashboard_dto.period_start.isoformat(),
                        "end_date": dashboard_dto.period_end.isoformat(),
                    },
                    "revenue": {
                        "total_revenue": str(dashboard_dto.revenue.total_revenue),
                        "revenue_today": str(dashboard_dto.revenue.revenue_today),
                        "revenue_this_week": str(dashboard_dto.revenue.revenue_this_week),
                        "revenue_this_month": str(dashboard_dto.revenue.revenue_this_month),
                        "revenue_this_year": str(dashboard_dto.revenue.revenue_this_year),
                        "average_order_value": str(dashboard_dto.revenue.average_order_value),
                        "total_orders": dashboard_dto.revenue.total_orders,
                        "orders_today": dashboard_dto.revenue.orders_today,
                        "orders_this_week": dashboard_dto.revenue.orders_this_week,
                        "orders_this_month": dashboard_dto.revenue.orders_this_month,
                    },
                    "expenses": {
                        "total_expenses": str(dashboard_dto.expenses.total_expenses),
                        "expenses_today": str(dashboard_dto.expenses.expenses_today),
                        "expenses_this_week": str(dashboard_dto.expenses.expenses_this_week),
                        "expenses_this_month": str(dashboard_dto.expenses.expenses_this_month),
                        "expenses_this_year": str(dashboard_dto.expenses.expenses_this_year),
                        "salary_expenses": str(dashboard_dto.expenses.salary_expenses),
                        "other_expenses": str(dashboard_dto.expenses.other_expenses),
                    },
                    "profit": {
                        "total_profit": str(dashboard_dto.profit.total_profit),
                        "profit_today": str(dashboard_dto.profit.profit_today),
                        "profit_this_week": str(dashboard_dto.profit.profit_this_week),
                        "profit_this_month": str(dashboard_dto.profit.profit_this_month),
                        "profit_margin_percentage": str(
                            dashboard_dto.profit.profit_margin_percentage
                        ),
                    },
                    "inventory": {
                        "total_products": dashboard_dto.inventory.total_products,
                        "low_stock_products": dashboard_dto.inventory.low_stock_products,
                        "expired_products": dashboard_dto.inventory.expired_products,
                        "total_inventory_value": str(dashboard_dto.inventory.total_inventory_value),
                        "products_on_promotion": dashboard_dto.inventory.products_on_promotion,
                    },
                    "customers": {
                        "total_customers": dashboard_dto.customers.total_customers,
                        "new_customers_today": dashboard_dto.customers.new_customers_today,
                        "new_customers_this_week": dashboard_dto.customers.new_customers_this_week,
                        "new_customers_this_month": dashboard_dto.customers.new_customers_this_month,
                        "active_customers": dashboard_dto.customers.active_customers,
                        "total_credit_amount": str(dashboard_dto.customers.total_credit_amount),
                        "overdue_credit_amount": str(dashboard_dto.customers.overdue_credit_amount),
                    },
                    "top_products": [
                        {
                            "product_id": str(p.product_id),
                            "product_name": p.product_name,
                            "total_sold": p.total_sold,
                            "total_revenue": str(p.total_revenue),
                            "quantity_available": p.quantity_available,
                        }
                        for p in dashboard_dto.top_products
                    ],
                    "overview": {
                        "total_customers": dashboard_dto.overview.total_customers,
                        "total_members": dashboard_dto.overview.total_members,
                        "active_members": dashboard_dto.overview.active_members,
                        "total_products": dashboard_dto.overview.total_products,
                        "total_categories": dashboard_dto.overview.total_categories,
                        "total_subcategories": dashboard_dto.overview.total_subcategories,
                        "lifetime_revenue": str(dashboard_dto.overview.lifetime_revenue),
                        "lifetime_credit": str(dashboard_dto.overview.lifetime_credit),
                        "lifetime_profit": str(dashboard_dto.overview.lifetime_profit),
                        "lifetime_expenses": str(dashboard_dto.overview.lifetime_expenses),
                        "total_invoices": dashboard_dto.overview.total_invoices,
                        "total_invoices_completed": dashboard_dto.overview.total_invoices_completed,
                        "total_invoices_credit": dashboard_dto.overview.total_invoices_credit,
                        "average_invoice_value": str(dashboard_dto.overview.average_invoice_value),
                        "total_inventory_value": str(dashboard_dto.overview.total_inventory_value),
                        "business_created_at": dashboard_dto.overview.business_created_at.isoformat(),
                    },
                    "generated_at": dashboard_dto.generated_at.isoformat(),
                },
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get daily dashboard data",
        operation_description=(
            "Get daily dashboard data with date range filtering. "
            "If start_date and end_date are not provided, defaults to current week. "
            "Returns data grouped by day with all metrics (revenue, sales, expenses, profits, etc.)."
        ),
        query_serializer=DashboardDailyQuerySerializer,
        responses={200: "Daily dashboard data", 400: "Bad Request", 403: "Permission denied"},
        tags=["Dashboard"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="insights",
    )
    def get_daily(self, request: Request) -> Response:
        """Get daily dashboard data for a business."""
        try:
            # Validate query parameters
            query_serializer = DashboardDailyQuerySerializer(data=request.query_params)
            if not query_serializer.is_valid():
                return self.handle_validation_error(query_serializer)

            business_id = query_serializer.validated_data["business_id"]
            start_date = query_serializer.validated_data.get("start_date")
            end_date = query_serializer.validated_data.get("end_date")
            recent_sales_limit = query_serializer.validated_data.get("recent_sales_limit", 10)

            if not self._get_business_domain_service().is_user_owner(business_id, request.user.id):
                return self.error(
                    message="Only the business owner can access the dashboard",
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="PERMISSION_DENIED",
                )

            # Create dashboard metrics service
            metrics_service = DashboardMetricsService(
                metrics_repository=DashboardMetricsRepositoryImpl(),
                product_statistics_repository=DashboardProductStatisticsRepositoryImpl(),
                category_statistics_repository=DashboardCategoryStatisticsRepositoryImpl(),
                subcategory_statistics_repository=DashboardSubCategoryStatisticsRepositoryImpl(),
                cashier_statistics_repository=DashboardCashierStatisticsRepositoryImpl(),
                business_id=business_id,
            )

            use_case = GetDashboardDailyUseCase(
                dashboard_metrics_service=metrics_service,
                business_domain_service=self._get_business_domain_service(),
                business_id=business_id,
                user_id=request.user.id,
                start_date=start_date,
                end_date=end_date,
                recent_sales_limit=recent_sales_limit,
            )
            dashboard_dto = use_case.execute()

            # Format response
            return self.success(
                message="Daily dashboard data retrieved successfully",
                data={
                    "business_id": str(dashboard_dto.business_id),
                    "period": {
                        "start_date": dashboard_dto.period_start.isoformat(),
                        "end_date": dashboard_dto.period_end.isoformat(),
                    },
                    "totals": {
                        "total_revenue": str(dashboard_dto.totals.total_revenue),
                        "total_sales": dashboard_dto.totals.total_sales,
                        "credit_outstanding": str(dashboard_dto.totals.credit_outstanding),
                        "total_expenses": str(dashboard_dto.totals.total_expenses),
                        "gross_profit": str(dashboard_dto.totals.gross_profit),
                        "net_profit": str(dashboard_dto.totals.net_profit),
                    },
                    "daily_data": [
                        {
                            "date": dm.date.isoformat(),
                            "complete_revenue": str(dm.complete_revenue),
                            "credit_revenue": str(dm.credit_revenue),
                            "total_revenue": str(dm.total_revenue),
                            "profit": str(dm.profit),
                            "gross_profit": str(dm.gross_profit),
                            "net_profit": str(dm.net_profit),
                            "total_sales": dm.total_sales,
                            "total_expenses": str(dm.total_expenses),
                            "credit_outstanding": str(dm.credit_outstanding),
                        }
                        for dm in dashboard_dto.daily_data
                    ],
                    "sales_performance": {
                        "credit_revenue": str(dashboard_dto.sales_performance.credit_revenue),
                        "total_revenue": str(dashboard_dto.sales_performance.total_revenue),
                        "complete_revenue": str(dashboard_dto.sales_performance.complete_revenue),
                        "profit": str(dashboard_dto.sales_performance.profit),
                    },
                    "top_products": [
                        {
                            "product_id": str(p.product_id),
                            "product_name": p.product_name,
                            "total_sold": p.total_sold,
                            "total_revenue": str(p.total_revenue),
                            "quantity_available": p.quantity_available,
                        }
                        for p in dashboard_dto.top_products
                    ],
                    "top_categories": [
                        {
                            "category_id": str(c.category_id),
                            "category_name": c.category_name,
                            "total_revenue": str(c.total_revenue),
                            "total_quantity_sold": c.total_quantity_sold,
                            "number_of_sales": c.number_of_sales,
                        }
                        for c in dashboard_dto.top_categories
                    ],
                    "recent_sales": [
                        {
                            "invoice_id": str(s.invoice_id),
                            "invoice_number": s.invoice_number,
                            "customer_name": s.customer_name,
                            "total": str(s.total),
                            "status": s.status,
                            "created_at": s.created_at.isoformat(),
                        }
                        for s in dashboard_dto.recent_sales
                    ],
                    "product_statistics": {
                        "daily": [
                            {
                                "product_id": str(ps.product_id),
                                "product_name": ps.product_name,
                                "date": ps.date.isoformat(),
                                "quantity_sold": ps.quantity_sold,
                                "revenue": str(ps.revenue),
                                "cost": str(ps.cost),
                                "profit": str(ps.profit),
                                "margin_percentage": str(ps.margin_percentage),
                            }
                            for ps in dashboard_dto.product_statistics["daily"]
                        ],
                        "weekly": [
                            {
                                "product_id": str(ps.product_id),
                                "product_name": ps.product_name,
                                "date": ps.date.isoformat(),
                                "quantity_sold": ps.quantity_sold,
                                "revenue": str(ps.revenue),
                                "cost": str(ps.cost),
                                "profit": str(ps.profit),
                                "margin_percentage": str(ps.margin_percentage),
                            }
                            for ps in dashboard_dto.product_statistics["weekly"]
                        ],
                    },
                    "product_margins": [
                        {
                            "product_id": str(pm.product_id),
                            "product_name": pm.product_name,
                            "total_quantity_sold": pm.total_quantity_sold,
                            "total_revenue": str(pm.total_revenue),
                            "total_cost": str(pm.total_cost),
                            "total_profit": str(pm.total_profit),
                            "margin_percentage": str(pm.margin_percentage),
                        }
                        for pm in dashboard_dto.product_margins
                    ],
                    "generated_at": dashboard_dto.generated_at.isoformat(),
                },
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get product statistics",
        operation_description=(
            "Get detailed statistics for a specific product including daily breakdown, "
            "trends, and top customers. Filtered by start_date and end_date."
        ),
        query_serializer=ProductStatisticsQuerySerializer,
        responses={
            200: "Product statistics",
            400: "Bad Request",
            403: "Permission denied",
            404: "Not found",
        },
        tags=["Dashboard"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="products/statistics",
    )
    def get_product_statistics(self, request: Request) -> Response:
        """Get detailed statistics for a specific product."""
        try:
            query_serializer = ProductStatisticsQuerySerializer(data=request.query_params)
            if not query_serializer.is_valid():
                return self.handle_validation_error(query_serializer)

            business_id = query_serializer.validated_data["business_id"]
            product_uuid = query_serializer.validated_data["product_id"]
            start_date = query_serializer.validated_data.get("start_date")
            end_date = query_serializer.validated_data.get("end_date")

            if not self._get_business_domain_service().is_user_owner(business_id, request.user.id):
                return self.error(
                    message="Only the business owner can access the dashboard",
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="PERMISSION_DENIED",
                )

            metrics_service = DashboardMetricsService(
                metrics_repository=DashboardMetricsRepositoryImpl(),
                product_statistics_repository=DashboardProductStatisticsRepositoryImpl(),
                category_statistics_repository=DashboardCategoryStatisticsRepositoryImpl(),
                subcategory_statistics_repository=DashboardSubCategoryStatisticsRepositoryImpl(),
                cashier_statistics_repository=DashboardCashierStatisticsRepositoryImpl(),
                business_id=business_id,
            )

            use_case = GetProductStatisticsUseCase(
                dashboard_metrics_service=metrics_service,
                business_domain_service=self._get_business_domain_service(),
                product_repository=ProductRepositoryImpl(),
                business_id=business_id,
                product_id=product_uuid,
                user_id=request.user.id,
                start_date=start_date,
                end_date=end_date,
            )
            stats_dto = use_case.execute()

            return self.success(
                message="Product statistics retrieved successfully",
                data={
                    "product": {
                        "product_id": str(stats_dto.product.product_id),
                        "product_name": stats_dto.product.product_name,
                        "category_id": str(stats_dto.product.category_id),
                        "category_name": stats_dto.product.category_name,
                        "subcategory_id": (
                            str(stats_dto.product.subcategory_id)
                            if stats_dto.product.subcategory_id
                            else None
                        ),
                        "subcategory_name": stats_dto.product.subcategory_name,
                    },
                    "period": {
                        "start_date": stats_dto.period_start.isoformat(),
                        "end_date": stats_dto.period_end.isoformat(),
                    },
                    "totals": {
                        k: str(v) if isinstance(v, Decimal) else v
                        for k, v in stats_dto.totals.items()
                    },
                    "daily_data": [
                        {
                            "product_id": str(d.product_id),
                            "product_name": d.product_name,
                            "date": d.date.isoformat(),
                            "quantity_sold": d.quantity_sold,
                            "revenue": str(d.revenue),
                            "cost": str(d.cost),
                            "profit": str(d.profit),
                            "margin_percentage": str(d.margin_percentage),
                        }
                        for d in stats_dto.daily_data
                    ],
                    "trends": {
                        k: {
                            "previous_period": {
                                "start_date": v.previous_period_start.isoformat(),
                                "end_date": v.previous_period_end.isoformat(),
                            },
                            "current_value": str(v.current_value),
                            "previous_value": str(v.previous_value),
                            "change_amount": str(v.change_amount),
                            "change_percentage": str(v.change_percentage),
                            "trend_direction": v.trend_direction,
                        }
                        for k, v in stats_dto.trends.items()
                    },
                    "top_customers": [
                        {
                            "customer_id": str(c.customer_id) if c.customer_id else None,
                            "customer_name": c.customer_name,
                            "total_purchases": c.total_purchases,
                            "total_revenue": str(c.total_revenue),
                        }
                        for c in stats_dto.top_customers
                    ],
                },
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get category statistics",
        operation_description=(
            "Get detailed statistics for a specific category including daily breakdown, "
            "trends, and top products. Filtered by start_date and end_date."
        ),
        query_serializer=CategoryStatisticsQuerySerializer,
        responses={
            200: "Category statistics",
            400: "Bad Request",
            403: "Permission denied",
            404: "Not found",
        },
        tags=["Dashboard"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="categories/statistics",
    )
    def get_category_statistics(self, request: Request) -> Response:
        """Get detailed statistics for a specific category."""
        try:
            query_serializer = CategoryStatisticsQuerySerializer(data=request.query_params)
            if not query_serializer.is_valid():
                return self.handle_validation_error(query_serializer)

            business_id = query_serializer.validated_data["business_id"]
            category_id = query_serializer.validated_data["category_id"]
            start_date = query_serializer.validated_data.get("start_date")
            end_date = query_serializer.validated_data.get("end_date")

            if not self._get_business_domain_service().is_user_owner(business_id, request.user.id):
                return self.error(
                    message="Only the business owner can access the dashboard",
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="PERMISSION_DENIED",
                )

            metrics_service = DashboardMetricsService(
                metrics_repository=DashboardMetricsRepositoryImpl(),
                product_statistics_repository=DashboardProductStatisticsRepositoryImpl(),
                category_statistics_repository=DashboardCategoryStatisticsRepositoryImpl(),
                subcategory_statistics_repository=DashboardSubCategoryStatisticsRepositoryImpl(),
                cashier_statistics_repository=DashboardCashierStatisticsRepositoryImpl(),
                business_id=business_id,
            )

            use_case = GetCategoryStatisticsUseCase(
                dashboard_metrics_service=metrics_service,
                business_domain_service=self._get_business_domain_service(),
                category_repository=CategoryRepositoryImpl(),
                business_id=business_id,
                category_id=category_id,
                user_id=request.user.id,
                start_date=start_date,
                end_date=end_date,
            )
            stats_dto = use_case.execute()

            return self.success(
                message="Category statistics retrieved successfully",
                data={
                    "category": {
                        "category_id": str(stats_dto.category.category_id),
                        "category_name": stats_dto.category.category_name,
                    },
                    "period": {
                        "start_date": stats_dto.period_start.isoformat(),
                        "end_date": stats_dto.period_end.isoformat(),
                    },
                    "totals": {
                        k: str(v) if isinstance(v, Decimal) else v
                        for k, v in stats_dto.totals.items()
                    },
                    "top_products": [
                        {
                            "product_id": str(p.product_id),
                            "product_name": p.product_name,
                            "total_sold": p.total_sold,
                            "total_revenue": str(p.total_revenue),
                            "quantity_available": p.quantity_available,
                        }
                        for p in stats_dto.top_products
                    ],
                    "daily_data": [
                        {
                            "date": d["date"].isoformat(),
                            "quantity_sold": d["quantity_sold"],
                            "revenue": str(d["revenue"]),
                            "cost": str(d["cost"]),
                            "profit": str(d["profit"]),
                        }
                        for d in stats_dto.daily_data
                    ],
                    "trends": {
                        k: {
                            "previous_period": {
                                "start_date": v.previous_period_start.isoformat(),
                                "end_date": v.previous_period_end.isoformat(),
                            },
                            "current_value": str(v.current_value),
                            "previous_value": str(v.previous_value),
                            "change_amount": str(v.change_amount),
                            "change_percentage": str(v.change_percentage),
                            "trend_direction": v.trend_direction,
                        }
                        for k, v in stats_dto.trends.items()
                    },
                },
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get subcategory statistics",
        operation_description=(
            "Get detailed statistics for a specific subcategory including daily breakdown, "
            "trends, and top products. Filtered by start_date and end_date."
        ),
        query_serializer=SubCategoryStatisticsQuerySerializer,
        responses={
            200: "Subcategory statistics",
            400: "Bad Request",
            403: "Permission denied",
            404: "Not found",
        },
        tags=["Dashboard"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="subcategories/statistics",
    )
    def get_subcategory_statistics(self, request: Request) -> Response:
        """Get detailed statistics for a specific subcategory."""
        try:
            query_serializer = SubCategoryStatisticsQuerySerializer(data=request.query_params)
            if not query_serializer.is_valid():
                return self.handle_validation_error(query_serializer)

            business_id = query_serializer.validated_data["business_id"]
            subcategory_id = query_serializer.validated_data["subcategory_id"]
            start_date = query_serializer.validated_data.get("start_date")
            end_date = query_serializer.validated_data.get("end_date")

            if not self._get_business_domain_service().is_user_owner(business_id, request.user.id):
                return self.error(
                    message="Only the business owner can access the dashboard",
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="PERMISSION_DENIED",
                )

            metrics_service = DashboardMetricsService(
                metrics_repository=DashboardMetricsRepositoryImpl(),
                product_statistics_repository=DashboardProductStatisticsRepositoryImpl(),
                category_statistics_repository=DashboardCategoryStatisticsRepositoryImpl(),
                subcategory_statistics_repository=DashboardSubCategoryStatisticsRepositoryImpl(),
                cashier_statistics_repository=DashboardCashierStatisticsRepositoryImpl(),
                business_id=business_id,
            )

            use_case = GetSubCategoryStatisticsUseCase(
                dashboard_metrics_service=metrics_service,
                business_domain_service=self._get_business_domain_service(),
                subcategory_repository=SubCategoryRepositoryImpl(),
                business_id=business_id,
                subcategory_id=subcategory_id,
                user_id=request.user.id,
                start_date=start_date,
                end_date=end_date,
            )
            stats_dto = use_case.execute()

            return self.success(
                message="Subcategory statistics retrieved successfully",
                data={
                    "subcategory": {
                        "subcategory_id": str(stats_dto.subcategory.subcategory_id),
                        "subcategory_name": stats_dto.subcategory.subcategory_name,
                        "category_id": str(stats_dto.subcategory.category_id),
                        "category_name": stats_dto.subcategory.category_name,
                    },
                    "period": {
                        "start_date": stats_dto.period_start.isoformat(),
                        "end_date": stats_dto.period_end.isoformat(),
                    },
                    "totals": {
                        k: str(v) if isinstance(v, Decimal) else v
                        for k, v in stats_dto.totals.items()
                    },
                    "top_products": [
                        {
                            "product_id": str(p.product_id),
                            "product_name": p.product_name,
                            "total_sold": p.total_sold,
                            "total_revenue": str(p.total_revenue),
                            "quantity_available": p.quantity_available,
                        }
                        for p in stats_dto.top_products
                    ],
                    "daily_data": [
                        {
                            "date": d["date"].isoformat(),
                            "quantity_sold": d["quantity_sold"],
                            "revenue": str(d["revenue"]),
                            "cost": str(d["cost"]),
                            "profit": str(d["profit"]),
                        }
                        for d in stats_dto.daily_data
                    ],
                    "trends": {
                        k: {
                            "previous_period": {
                                "start_date": v.previous_period_start.isoformat(),
                                "end_date": v.previous_period_end.isoformat(),
                            },
                            "current_value": str(v.current_value),
                            "previous_value": str(v.previous_value),
                            "change_amount": str(v.change_amount),
                            "change_percentage": str(v.change_percentage),
                            "trend_direction": v.trend_direction,
                        }
                        for k, v in stats_dto.trends.items()
                    },
                },
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get cashier statistics",
        operation_description=(
            "Get detailed statistics for a specific cashier including daily breakdown, "
            "trends, and ranking. Filtered by start_date and end_date."
        ),
        query_serializer=CashierStatisticsQuerySerializer,
        responses={
            200: "Cashier statistics",
            400: "Bad Request",
            403: "Permission denied",
            404: "Not found",
        },
        tags=["Dashboard"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="cashiers/statistics",
    )
    def get_cashier_statistics(self, request: Request) -> Response:
        """Get detailed statistics for a specific cashier."""
        try:
            query_serializer = CashierStatisticsQuerySerializer(data=request.query_params)
            if not query_serializer.is_valid():
                return self.handle_validation_error(query_serializer)

            business_id = query_serializer.validated_data["business_id"]
            cashier_id = query_serializer.validated_data["cashier_id"]
            start_date = query_serializer.validated_data.get("start_date")
            end_date = query_serializer.validated_data.get("end_date")

            if not self._get_business_domain_service().is_user_owner(business_id, request.user.id):
                return self.error(
                    message="Only the business owner can access the dashboard",
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="PERMISSION_DENIED",
                )

            metrics_service = DashboardMetricsService(
                metrics_repository=DashboardMetricsRepositoryImpl(),
                product_statistics_repository=DashboardProductStatisticsRepositoryImpl(),
                category_statistics_repository=DashboardCategoryStatisticsRepositoryImpl(),
                subcategory_statistics_repository=DashboardSubCategoryStatisticsRepositoryImpl(),
                cashier_statistics_repository=DashboardCashierStatisticsRepositoryImpl(),
                business_id=business_id,
            )

            use_case = GetCashierStatisticsUseCase(
                dashboard_metrics_service=metrics_service,
                business_domain_service=self._get_business_domain_service(),
                business_id=business_id,
                cashier_id=cashier_id,
                user_id=request.user.id,
                start_date=start_date,
                end_date=end_date,
            )
            stats_dto = use_case.execute()

            return self.success(
                message="Cashier statistics retrieved successfully",
                data={
                    "cashier": {
                        "cashier_id": str(stats_dto.cashier.cashier_id),
                        "cashier_name": stats_dto.cashier.cashier_name,
                        "cashier_email": stats_dto.cashier.cashier_email,
                        "phone_number": stats_dto.cashier.phone_number,
                        "avatar_url": stats_dto.cashier.avatar_url,
                        "role": stats_dto.cashier.role,
                        "is_active": stats_dto.cashier.is_active,
                        "joined_at": stats_dto.cashier.joined_at.isoformat(),
                        "left_at": (
                            stats_dto.cashier.left_at.isoformat()
                            if stats_dto.cashier.left_at
                            else None
                        ),
                    },
                    "period": {
                        "start_date": stats_dto.period_start.isoformat(),
                        "end_date": stats_dto.period_end.isoformat(),
                    },
                    "totals": {
                        k: str(v) if isinstance(v, Decimal) else v
                        for k, v in stats_dto.totals.items()
                    },
                    "lifetime_totals": {
                        k: str(v) if isinstance(v, Decimal) else v
                        for k, v in stats_dto.lifetime_totals.items()
                    },
                    "daily_data": [
                        {
                            "date": d.date.isoformat(),
                            "total_sales": d.total_sales,
                            "total_revenue": str(d.total_revenue),
                            "total_quantity_sold": d.total_quantity_sold,
                            "average_sale_value": str(d.average_sale_value),
                            "customers_served": d.customers_served,
                        }
                        for d in stats_dto.daily_data
                    ],
                    "trends": {
                        k: {
                            "previous_period": {
                                "start_date": v.previous_period_start.isoformat(),
                                "end_date": v.previous_period_end.isoformat(),
                            },
                            "current_value": str(v.current_value),
                            "previous_value": str(v.previous_value),
                            "change_amount": str(v.change_amount),
                            "change_percentage": str(v.change_percentage),
                            "trend_direction": v.trend_direction,
                        }
                        for k, v in stats_dto.trends.items()
                    },
                    "ranking": stats_dto.ranking,
                },
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)
