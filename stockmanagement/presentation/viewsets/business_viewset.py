"""Business ViewSet using DDD architecture with use cases."""

from __future__ import annotations

from uuid import UUID

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from application.dto.business_list_filter_dto import BusinessListFilterDTO
from application.dto.business_member_list_filter_dto import BusinessMemberListFilterDTO
from application.use_cases.business_use_cases import (
    AddBusinessMemberUseCase,
    CreateBusinessUseCase,
    DeleteBusinessUseCase,
    GetBusinessUseCase,
    ListBusinessesUseCase,
    ListBusinessMembersUseCase,
    RemoveBusinessMemberUseCase,
    UpdateBusinessUseCase,
)
from domain.business.services import BusinessDomainService
from infrastructure.persistence.repositories import (
    BusinessMemberRepositoryImpl,
    BusinessRepositoryImpl,
    UserRepositoryImpl,
)
from presentation.serializers.business_serializers import (
    BusinessCreateSerializer,
    BusinessMemberCreateSerializer,
    BusinessMemberSerializer,
    BusinessResponseSerializer,
    BusinessUpdateSerializer,
)
from shared.views.base_viewset import BaseViewSet


class BusinessViewSet(BaseViewSet):
    """ViewSet for business management using DDD architecture."""

    permission_classes = [IsAuthenticated]

    def _get_business_domain_service(self) -> BusinessDomainService:
        """Get business domain service instance."""
        return BusinessDomainService(
            business_repository=BusinessRepositoryImpl(),
            business_member_repository=BusinessMemberRepositoryImpl(),
        )

    @swagger_auto_schema(
        operation_summary="List businesses",
        operation_description="Get all businesses for the authenticated user (owned or member).",
        responses={200: "List of businesses", 401: "Unauthorized"},
        tags=["Business"],
    )
    def list(self, request: Request) -> Response:
        """List all businesses for the authenticated user."""
        try:
            filter_payload = self.parse_list_filters(
                request,
                search_fields=["name", "unique_name"],
                order_fields=["name", "created_at", "updated_at"],
                filter_definitions={
                    "name": {"type": "string", "max_length": 255},
                    "is_active": {"type": "boolean"},
                },
            )
            filter_dto = BusinessListFilterDTO.from_payload(filter_payload)

            use_case = ListBusinessesUseCase(
                business_repository=BusinessRepositoryImpl(),
                business_member_repository=BusinessMemberRepositoryImpl(),
                user_id=request.user.id,
            )
            businesses = use_case.execute()

            if filter_dto.is_active is not None:
                businesses = [
                    business
                    for business in businesses
                    if business.is_active == filter_dto.is_active
                ]

            businesses = self.apply_filtering_to_items(
                businesses,
                filter_payload,
                name_fields=["name", "unique_name"],
            )

            return self.paginated_response(
                request=request,
                queryset=businesses,
                serializer_class=BusinessResponseSerializer,
                message="Businesses retrieved successfully",
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Create business",
        operation_description="Create a new business. User becomes OWNER automatically.",
        request_body=BusinessCreateSerializer,
        responses={
            201: BusinessResponseSerializer,
            400: "Bad Request",
            401: "Unauthorized",
        },
        tags=["Business"],
    )
    def create(self, request: Request) -> Response:
        """Create a new business."""
        serializer = BusinessCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            dto = serializer.to_dto()
            use_case = CreateBusinessUseCase(
                business_repository=BusinessRepositoryImpl(),
                user_repository=UserRepositoryImpl(),
                owner_id=request.user.id,
            )
            business_dto = use_case.execute(dto)
            business_data = BusinessResponseSerializer.from_dto(business_dto)

            user = UserRepositoryImpl().get_by_id(request.user.id)

            business_data["user"] = {
                "id": str(user.id),
                "email": user.email or "",
                "name": user.name,
                "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            }

            return self.success(
                message="Business created successfully. Your role has been updated to OWNER.",
                data=business_data,
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get business",
        operation_description="Get business details by ID.",
        responses={
            200: BusinessResponseSerializer,
            403: "Permission denied",
            404: "Business not found",
        },
        tags=["Business"],
    )
    def retrieve(self, request: Request, pk: UUID) -> Response:
        """Get business by ID."""
        try:
            business_domain_service = self._get_business_domain_service()
            use_case = GetBusinessUseCase(
                business_repository=BusinessRepositoryImpl(),
                business_domain_service=business_domain_service,
                business_id=pk,
                user_id=request.user.id,
            )
            business_dto = use_case.execute()

            members_use_case = ListBusinessMembersUseCase(
                business_member_repository=BusinessMemberRepositoryImpl(),
                business_domain_service=business_domain_service,
                user_repository=UserRepositoryImpl(),
                business_id=pk,
                user_id=request.user.id,
                include_inactive=True,
            )
            members = members_use_case.execute()

            business_data = BusinessResponseSerializer.from_dto(
                business_dto,
                members=members,
            )

            return self.success(
                message="Business retrieved successfully",
                data=business_data,
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Update business",
        operation_description="Update business details. Only owner and managers can update.",
        request_body=BusinessUpdateSerializer,
        responses={
            200: BusinessResponseSerializer,
            403: "Permission denied",
            404: "Business not found",
        },
        tags=["Business"],
    )
    def update(self, request: Request, pk: UUID) -> Response:
        """Update business."""
        serializer = BusinessUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            dto = serializer.to_dto()
            use_case = UpdateBusinessUseCase(
                business_repository=BusinessRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=pk,
                user_id=request.user.id,
            )
            business_dto = use_case.execute(dto)

            business_data = BusinessResponseSerializer.from_dto(business_dto)

            return self.success(
                message="Business updated successfully",
                data=business_data,
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Delete business",
        operation_description="Delete a business. Only owner can delete.",
        responses={200: "Business deleted", 403: "Permission denied", 404: "Business not found"},
        tags=["Business"],
    )
    def destroy(self, request: Request, pk: UUID) -> Response:
        """Delete business."""
        try:
            use_case = DeleteBusinessUseCase(
                business_repository=BusinessRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=pk,
                user_id=request.user.id,
            )
            use_case.execute()

            return self.success(
                message="Business deleted successfully",
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Add business member",
        operation_description="Add a member to the business. Only owner and managers can add members.",
        request_body=BusinessMemberCreateSerializer,
        responses={
            201: BusinessMemberSerializer,
            400: "Validation error",
            403: "Permission denied",
        },
        tags=["Business"],
    )
    @action(detail=True, methods=["post"], url_path="members")
    def add_member(self, request: Request, pk: UUID) -> Response:
        """Add a member to the business."""
        serializer = BusinessMemberCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            dto = serializer.to_dto()
            use_case = AddBusinessMemberUseCase(
                business_repository=BusinessRepositoryImpl(),
                business_member_repository=BusinessMemberRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=pk,
                user_id=request.user.id,
            )
            member_dto = use_case.execute(dto)

            member_data = BusinessMemberSerializer.from_dto(member_dto)

            return self.success(
                message="Business member added successfully",
                data=member_data,
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        method="get",
        operation_summary="List business members",
        operation_description=(
            "List all members of a business with pagination support. Only users with access to "
            "the business can view members."
        ),
        manual_parameters=[
            openapi.Parameter(
                name="page",
                in_=openapi.IN_QUERY,
                description="Page number (defaults to 1).",
                type=openapi.TYPE_INTEGER,
            ),
            openapi.Parameter(
                name="page_size",
                in_=openapi.IN_QUERY,
                description="Number of records per page (defaults to 20, max 1000).",
                type=openapi.TYPE_INTEGER,
            ),
            openapi.Parameter(
                name="include_inactive",
                in_=openapi.IN_QUERY,
                description="Include inactive members when set to true.",
                type=openapi.TYPE_BOOLEAN,
            ),
        ],
        responses={
            200: "List of business members",
            400: "Bad Request",
            403: "Permission denied",
            404: "Business not found",
        },
        tags=["Business"],
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="members/list",
        url_name="list-members",
    )
    def list_members(self, request: Request, pk: UUID) -> Response:
        """List members of the business."""
        try:
            filter_payload = self.parse_list_filters(
                request,
                search_fields=["user.name", "user.email"],
                order_fields=["joined_at", "role", "created_at"],
                default_order_field="joined_at",
                filter_definitions={
                    "include_inactive": {"type": "boolean"},
                    "role": {
                        "type": "enum",
                        "choices": ["owner", "manager", "cashier", "stock_keeper", "delivery"],
                    },
                    "name": {"type": "string", "max_length": 255},
                },
            )
            filter_payload["filters"]["business_id"] = pk
            filter_dto = BusinessMemberListFilterDTO.from_payload(filter_payload)

            use_case = ListBusinessMembersUseCase(
                business_member_repository=BusinessMemberRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                user_repository=UserRepositoryImpl(),
                business_id=pk,
                user_id=request.user.id,
                include_inactive=filter_dto.include_inactive,
            )
            members = use_case.execute()

            if filter_dto.role:
                members = [member for member in members if member.role == filter_dto.role]

            members = self.apply_filtering_to_items(
                members,
                filter_payload,
                name_fields=["user.name"],
            )

            return self.paginated_response(
                request=request,
                queryset=members,
                serializer_class=BusinessMemberSerializer,
                message="Business members retrieved successfully",
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Remove business member",
        operation_description="Remove a member from the business. Only owner and managers can remove members.",
        responses={200: "Member removed", 403: "Permission denied", 404: "Member not found"},
        tags=["Business"],
    )
    @action(detail=True, methods=["delete"], url_path="members/(?P<member_id>[^/.]+)")
    def remove_member(self, request: Request, pk: UUID, member_id: UUID) -> Response:
        """Remove a member from the business."""
        try:
            use_case = RemoveBusinessMemberUseCase(
                business_member_repository=BusinessMemberRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=pk,
                user_id=request.user.id,
            )
            use_case.execute(member_id)

            return self.success(
                message="Business member removed successfully",
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Scan QR code",
        operation_description="Scan QR code to get business information.",
        request_body=None,
        responses={
            200: BusinessResponseSerializer,
            400: "Invalid QR code",
            404: "Business not found",
        },
        tags=["Business"],
    )
    @action(detail=False, methods=["post"], url_path="scan-qr")
    def scan_qr_code(self, request: Request) -> Response:
        """Scan QR code to get business information."""
        try:
            qr_data = request.data.get("qr_data") or request.data.get("qr_code")
            if not qr_data:
                return self.error(
                    message="QR code data is required",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="MISSING_QR_DATA",
                )

            from shared.services.qr_code_service import QRCodeService

            qr_service = QRCodeService()
            parsed_data = qr_service.scan_qr_code(qr_data)

            business_id = parsed_data["business_id"]

            # Get business details
            use_case = GetBusinessUseCase(
                business_repository=BusinessRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=business_id,
                user_id=request.user.id,
            )
            business_dto = use_case.execute()

            business_data = BusinessResponseSerializer.from_dto(business_dto)

            return self.success(
                message="Business retrieved from QR code",
                data=business_data,
                status_code=status.HTTP_200_OK,
            )
        except ValueError as e:
            return self.error(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_QR_CODE",
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get dashboard summary",
        operation_description="Get complete dashboard summary with all metrics for a business.",
        responses={200: "Dashboard summary", 403: "Permission denied"},
        tags=["Business"],
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="dashboard",
    )
    def get_dashboard(self, request: Request, pk: UUID) -> Response:
        """Get dashboard summary for a business."""
        try:
            from application.use_cases.dashboard_use_cases import GetDashboardSummaryUseCase
            from domain.dashboard.services import DashboardMetricsService
            from infrastructure.persistence.repositories import (
                CreditRepositoryImpl,
                ExpenseRepositoryImpl,
                InvoiceLineRepositoryImpl,
                InvoiceRepositoryImpl,
                PayrollRepositoryImpl,
                ProductRepositoryImpl,
            )

            # Check if user has access to business
            if not self._get_business_domain_service().user_has_access(pk, request.user.id):
                return self.error(
                    message="You don't have access to this business",
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="PERMISSION_DENIED",
                )

            from shared.security.query_params_validator import QueryParamsValidator

            # Get and validate period from query params
            period = QueryParamsValidator.validate_enum(
                request.query_params.get("period", "month"),
                allowed_values=["day", "week", "month", "year"],
                param_name="period",
            )

            # Create dashboard metrics service
            metrics_service = DashboardMetricsService(
                invoice_repository=InvoiceRepositoryImpl(),
                invoice_line_repository=InvoiceLineRepositoryImpl(),
                product_repository=ProductRepositoryImpl(),
                credit_repository=CreditRepositoryImpl(),
                business_id=pk,
                expense_repository=ExpenseRepositoryImpl(),
                payroll_repository=PayrollRepositoryImpl(),
            )

            use_case = GetDashboardSummaryUseCase(
                dashboard_metrics_service=metrics_service,
                business_domain_service=self._get_business_domain_service(),
                business_id=pk,
                user_id=request.user.id,
                period=period,
            )
            dashboard_dto = use_case.execute()

            return self.success(
                message="Dashboard summary retrieved successfully",
                data={
                    "business_id": str(dashboard_dto.business_id),
                    "period": dashboard_dto.period,
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
                    "generated_at": dashboard_dto.generated_at.isoformat(),
                },
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)
