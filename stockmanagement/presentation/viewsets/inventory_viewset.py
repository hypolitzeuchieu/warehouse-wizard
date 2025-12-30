"""Inventory ViewSet for stock movements and inventory analysis."""

from __future__ import annotations

from uuid import UUID

from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from application.use_cases.alert_use_cases import (
    CheckExpiredProductsUseCase as CheckExpiredProductsUseCaseFromAlert,
)
from application.use_cases.alert_use_cases import CheckLowStockProductsUseCase
from application.use_cases.inventory_use_cases import (
    CheckExpiredProductsUseCase as ListExpiredProductsUseCase,
)
from application.use_cases.inventory_use_cases import (
    CreateCategoryUseCase,
    CreateSubCategoryUseCase,
    GetLowStockProductsUseCase,
    ListCategoriesUseCase,
    ListSubCategoriesUseCase,
    RecordStockMovementUseCase,
)
from domain.business.services import BusinessDomainService
from domain.inventory.services import InventoryDomainService
from domain.notifications.services import NotificationDomainService
from infrastructure.persistence.repositories import (
    BusinessMemberRepositoryImpl,
    BusinessRepositoryImpl,
    CategoryRepositoryImpl,
    NotificationRepositoryImpl,
    ProductRepositoryImpl,
    StockMovementRepositoryImpl,
    SubCategoryRepositoryImpl,
)
from presentation.serializers.inventory_serializers import (
    CategoryCreateSerializer,
    CategoryResponseSerializer,
    ExpiredProductSerializer,
    LowStockProductSerializer,
    StockMovementCreateSerializer,
    StockMovementResponseSerializer,
    SubCategoryCreateSerializer,
    SubCategoryResponseSerializer,
)
from shared.permissions.business_permissions import IsBusinessActive
from shared.views.base_viewset import BaseViewSet


class InventoryViewSet(BaseViewSet):
    """ViewSet for inventory management (stock movements and analysis)."""

    permission_classes = [IsAuthenticated, IsBusinessActive]

    def _get_business_domain_service(self) -> BusinessDomainService:
        """Get business domain service instance."""
        return BusinessDomainService(
            business_repository=BusinessRepositoryImpl(),
            business_member_repository=BusinessMemberRepositoryImpl(),
        )

    def _get_inventory_domain_service(self) -> InventoryDomainService:
        """Get inventory domain service instance."""
        return InventoryDomainService(
            product_repository=ProductRepositoryImpl(),
            stock_movement_repository=StockMovementRepositoryImpl(),
        )

    def _get_notification_domain_service(self) -> NotificationDomainService:
        """Get notification domain service instance."""
        return NotificationDomainService(
            notification_repository=NotificationRepositoryImpl(),
            business_repository=BusinessRepositoryImpl(),
            business_member_repository=BusinessMemberRepositoryImpl(),
        )

    @swagger_auto_schema(
        operation_summary="List categories",
        operation_description="List categories for a business.",
        operation_id="inventory_list_categories",
        responses={
            200: CategoryResponseSerializer(many=True),
            403: "Permission denied",
            404: "Business not found",
            400: "Validation error",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Inventory - Categories"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="businesses/(?P<business_id>[^/.]+)/categories",
        url_name="category-list",
    )
    def list_categories(self, request: Request, business_id: UUID) -> Response:
        """List categories for a business."""
        try:
            filter_payload = self.parse_list_filters(
                request,
                search_fields=["name"],
                order_fields=["name", "created_at", "updated_at"],
                filter_definitions={
                    "name": {"type": "string", "max_length": 100},
                },
            )
            use_case = ListCategoriesUseCase(
                category_repository=CategoryRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=business_id,
                user_id=request.user.id,
            )
            categories = use_case.execute()
            categories = self.apply_filtering_to_items(
                categories,
                filter_payload,
                name_fields=["name"],
            )
            return self.paginated_response(
                request=request,
                queryset=categories,
                serializer_class=CategoryResponseSerializer,
                message="Categories retrieved successfully",
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Create category",
        operation_description="Create a category within a business.",
        operation_id="inventory_create_category",
        request_body=CategoryCreateSerializer,
        responses={
            201: CategoryResponseSerializer,
            400: "Validation error",
            403: "Permission denied",
            404: "Business not found",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Inventory - Categories"],
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="businesses/(?P<business_id>[^/.]+)/categories",
        url_name="category-create",
    )
    def create_category(self, request: Request, business_id: UUID) -> Response:
        """Create a category."""
        serializer = CategoryCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            dto = serializer.to_dto()
            use_case = CreateCategoryUseCase(
                category_repository=CategoryRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=business_id,
                user_id=request.user.id,
            )
            category_dto = use_case.execute(dto)
            return self.success(
                message="Category created successfully",
                data=CategoryResponseSerializer.from_dto(category_dto),
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="List subcategories",
        operation_description="List subcategories for a category.",
        operation_id="inventory_list_subcategories",
        responses={
            200: SubCategoryResponseSerializer(many=True),
            403: "Permission denied",
            404: "Category not found",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Inventory - SubCategories"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="categories/(?P<category_id>[^/.]+)/subcategories",
        url_name="subcategory-list",
    )
    def list_subcategories(self, request: Request, category_id: UUID) -> Response:
        """List subcategories for a category."""
        try:
            filter_payload = self.parse_list_filters(
                request,
                search_fields=["name"],
                order_fields=["name", "created_at", "updated_at"],
                filter_definitions={
                    "name": {"type": "string", "max_length": 100},
                },
            )
            use_case = ListSubCategoriesUseCase(
                subcategory_repository=SubCategoryRepositoryImpl(),
                category_repository=CategoryRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                category_id=category_id,
                user_id=request.user.id,
            )
            subcategories = use_case.execute()
            subcategories = self.apply_filtering_to_items(
                subcategories,
                filter_payload,
                name_fields=["name"],
            )
            return self.paginated_response(
                request=request,
                queryset=subcategories,
                serializer_class=SubCategoryResponseSerializer,
                message="Subcategories retrieved successfully",
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Create subcategory",
        operation_description="Create a subcategory within a business.",
        operation_id="inventory_create_subcategory",
        request_body=SubCategoryCreateSerializer,
        responses={
            201: SubCategoryResponseSerializer,
            400: "Validation error",
            403: "Permission denied",
            404: "Category not found",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Inventory - SubCategories"],
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="businesses/(?P<business_id>[^/.]+)/subcategories",
        url_name="subcategory-create",
    )
    def create_subcategory(self, request: Request, business_id: UUID) -> Response:
        """Create subcategory."""
        serializer = SubCategoryCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            dto = serializer.to_dto()
            use_case = CreateSubCategoryUseCase(
                subcategory_repository=SubCategoryRepositoryImpl(),
                category_repository=CategoryRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=business_id,
                user_id=request.user.id,
            )
            subcategory_dto = use_case.execute(dto)
            return self.success(
                message="Subcategory created successfully",
                data=SubCategoryResponseSerializer.from_dto(subcategory_dto),
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get low stock products",
        operation_description="Get all products with low stock for a business.",
        operation_id="inventory_get_low_stock_products",
        responses={
            200: LowStockProductSerializer(many=True),
            403: "Permission denied",
            404: "Business not found",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Inventory"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="(?P<business_id>[^/.]+)/products/low-stock",
        url_name="low-stock",
    )
    def get_low_stock_products(self, request: Request, business_id: UUID) -> Response:
        """Get low stock products."""
        try:
            use_case = GetLowStockProductsUseCase(
                inventory_domain_service=self._get_inventory_domain_service(),
                business_id=business_id,
            )
            products = use_case.execute()

            data = [
                LowStockProductSerializer.from_dto(product_dto)
                for product_dto in products
            ]

            return self.success(
                message="Low stock products retrieved successfully",
                data=data,
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get expired products",
        operation_description="Get all expired products for a business.",
        operation_id="inventory_get_expired_products",
        responses={
            200: ExpiredProductSerializer(many=True),
            403: "Permission denied",
            404: "Business not found",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Inventory"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="(?P<business_id>[^/.]+)/products/expired",
        url_name="expired",
    )
    def get_expired_products(self, request: Request, business_id: UUID) -> Response:
        """Get expired products."""
        try:
            use_case = ListExpiredProductsUseCase(
                inventory_domain_service=self._get_inventory_domain_service(),
                business_id=business_id,
            )
            products = use_case.execute()

            data = [
                ExpiredProductSerializer.from_dto(product_dto)
                for product_dto in products
            ]

            return self.success(
                message="Expired products retrieved successfully",
                data=data,
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Record stock movement",
        operation_description="Record a stock movement (ENTRY, EXIT, or ADJUSTMENT).",
        operation_id="inventory_record_stock_movement",
        request_body=StockMovementCreateSerializer,
        responses={
            201: StockMovementResponseSerializer(),
            400: "Validation error",
            403: "Permission denied",
            404: "Business not found",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Inventory"],
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="(?P<business_id>[^/.]+)/stock-movements",
        url_name="stock-movement-create",
    )
    def record_stock_movement(self, request: Request, business_id: UUID) -> Response:
        """Record stock movement."""
        serializer = StockMovementCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            dto = serializer.to_dto()
            use_case = RecordStockMovementUseCase(
                inventory_domain_service=self._get_inventory_domain_service(),
                product_repository=ProductRepositoryImpl(),
                business_id=business_id,
                user_id=request.user.id,
            )
            movement_dto = use_case.execute(dto)

            return self.success(
                message="Stock movement recorded successfully",
                data=StockMovementResponseSerializer.from_dto(movement_dto),
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Check and alert expired products",
        operation_description="Check for expired products and create notifications for owner and managers.",
        operation_id="inventory_check_expired_products",
        responses={
            200: "Expired products checked and notifications created",
            403: "Permission denied",
            404: "Business not found",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Inventory"],
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="(?P<business_id>[^/.]+)/products/check-expired",
        url_name="check-expired",
    )
    def check_expired_products(self, request: Request, business_id: UUID) -> Response:
        """Check expired products and create notifications."""
        try:
            use_case = CheckExpiredProductsUseCaseFromAlert(
                inventory_domain_service=self._get_inventory_domain_service(),
                notification_domain_service=self._get_notification_domain_service(),
                business_id=business_id,
            )
            notifications = use_case.execute()

            return self.success(
                message=f"Checked expired products. Created {len(notifications)} notification(s).",
                data={"notifications_created": notifications},
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Check and alert low stock products",
        operation_description="Check for low stock products and create notifications for owner and managers.",
        operation_id="inventory_check_low_stock_products",
        responses={
            200: "Low stock products checked and notifications created",
            403: "Permission denied",
            404: "Business not found",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Inventory"],
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="(?P<business_id>[^/.]+)/products/check-low-stock",
        url_name="check-low-stock",
    )
    def check_low_stock_products(self, request: Request, business_id: UUID) -> Response:
        """Check low stock products and create notifications."""
        try:

            use_case = CheckLowStockProductsUseCase(
                inventory_domain_service=self._get_inventory_domain_service(),
                notification_domain_service=self._get_notification_domain_service(),
                business_id=business_id,
            )
            notifications = use_case.execute()

            return self.success(
                message=f"Checked low stock products. Created {len(notifications)} notification(s).",
                data={"notifications_created": notifications},
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)
