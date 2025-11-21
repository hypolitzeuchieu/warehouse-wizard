"""Inventory ViewSet for products and stock movements."""

from __future__ import annotations

from uuid import UUID

from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from application.dto.product_list_filter_dto import ProductListFilterDTO
from application.use_cases.alert_use_cases import CheckLowStockProductsUseCase
from application.use_cases.inventory_use_cases import (
    CheckExpiredProductsUseCase as ListExpiredProductsUseCase,
)
from application.use_cases.inventory_use_cases import (
    CreateCategoryUseCase,
    CreateProductUseCase,
    CreateSubCategoryUseCase,
    DeleteProductUseCase,
    GetLowStockProductsUseCase,
    GetProductUseCase,
    ListCategoriesUseCase,
    ListProductsUseCase,
    ListSubCategoriesUseCase,
    RecordStockMovementUseCase,
    UpdateProductUseCase,
)
from domain.business.services import BusinessDomainService
from domain.inventory.services import InventoryDomainService
from infrastructure.persistence.repositories import (
    BusinessMemberRepositoryImpl,
    BusinessRepositoryImpl,
    CategoryRepositoryImpl,
    ProductRepositoryImpl,
    StockMovementRepositoryImpl,
    SubCategoryRepositoryImpl,
)
from presentation.serializers.inventory_serializers import (
    CategoryCreateSerializer,
    CategoryResponseSerializer,
    ExpiredProductSerializer,
    LowStockProductSerializer,
    ProductCreateSerializer,
    ProductResponseSerializer,
    ProductScanSerializer,
    ProductUpdateSerializer,
    StockMovementCreateSerializer,
    StockMovementResponseSerializer,
    SubCategoryCreateSerializer,
    SubCategoryResponseSerializer,
)
from shared.exceptions.specific import BadRequestError, NotFoundError
from shared.views.base_viewset import BaseViewSet


class InventoryViewSet(BaseViewSet):
    """ViewSet for inventory management (products and stock movements)."""

    permission_classes = [IsAuthenticated]

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

    def _list_products_for_scope(
        self,
        request: Request,
        *,
        business_id: UUID,
        category_id: UUID | None = None,
        subcategory_id: UUID | None = None,
    ) -> Response:
        """List products for a given scope."""
        filter_payload = self.parse_list_filters(
            request,
            search_fields=["name", "barcode"],
            order_fields=[
                "name",
                "created_at",
                "updated_at",
                "quantity",
                "unit_price",
            ],
            filter_definitions={
                "name": {"type": "string", "max_length": 255},
                "category_id": {"type": "uuid"},
                "subcategory_id": {"type": "uuid"},
                "low_stock_only": {"type": "boolean"},
                "expired_only": {"type": "boolean"},
            },
        )
        filter_payload["filters"]["business_id"] = str(business_id)
        if category_id is not None:
            filter_payload["filters"]["category_id"] = str(category_id)
        if subcategory_id is not None:
            filter_payload["filters"]["subcategory_id"] = (
                str(subcategory_id) if subcategory_id else None
            )

        filter_dto = ProductListFilterDTO.from_payload(filter_payload)
        resolved_category_id = category_id or filter_dto.category_id
        resolved_subcategory_id = (
            subcategory_id if subcategory_id is not None else filter_dto.subcategory_id
        )

        def _to_uuid(value: UUID | str | None) -> UUID | None:
            if value is None:
                return None
            if isinstance(value, UUID):
                return value
            return UUID(str(value))

        category_repo = CategoryRepositoryImpl()
        subcategory_repo = SubCategoryRepositoryImpl()

        resolved_category_uuid = _to_uuid(resolved_category_id)
        resolved_subcategory_uuid = _to_uuid(resolved_subcategory_id)

        category_obj = None
        if resolved_category_uuid:
            category_obj = category_repo.get_by_id(resolved_category_uuid)
            if not category_obj or category_obj.business_id != business_id:
                raise NotFoundError(detail="Category not found", code="CATEGORY_NOT_FOUND")

        if resolved_subcategory_uuid:
            subcategory_obj = subcategory_repo.get_by_id(resolved_subcategory_uuid)
            if not subcategory_obj or subcategory_obj.business_id != business_id:
                raise NotFoundError(
                    detail="Subcategory not found",
                    code="SUBCATEGORY_NOT_FOUND",
                )
            if category_obj and subcategory_obj.category_id != category_obj.id:
                raise BadRequestError(
                    detail="Subcategory does not belong to the selected category",
                    code="SUBCATEGORY_MISMATCH",
                )
            if category_obj is None:
                resolved_category_uuid = subcategory_obj.category_id
                category_obj = category_repo.get_by_id(resolved_category_uuid)

        if resolved_category_uuid:
            filter_payload["filters"]["category_id"] = str(resolved_category_uuid)
        if resolved_subcategory_uuid is not None:
            filter_payload["filters"]["subcategory_id"] = (
                str(resolved_subcategory_uuid) if resolved_subcategory_uuid else None
            )

        use_case = ListProductsUseCase(
            product_repository=ProductRepositoryImpl(),
            business_domain_service=self._get_business_domain_service(),
            business_id=business_id,
            user_id=request.user.id,
            category_id=resolved_category_uuid,
            subcategory_id=resolved_subcategory_uuid,
            low_stock_only=filter_dto.low_stock_only,
            expired_only=filter_dto.expired_only,
        )
        products = use_case.execute()
        products = self.apply_filtering_to_items(
            products,
            filter_payload,
            name_fields=["name", "barcode"],
        )

        return self.paginated_response(
            request=request,
            queryset=products,
            serializer_class=ProductResponseSerializer,
            message="Products retrieved successfully",
        )

    @swagger_auto_schema(
        operation_summary="List products",
        operation_description="Get all products for a business with optional filters.",
        operation_id="inventory_list_products",
        responses={
            200: ProductResponseSerializer(many=True),
            403: "Permission denied",
            404: "Business not found",
            400: "Validation error",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Inventory"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="(?P<business_id>[^/.]+)/products",
        url_name="product-list",
    )
    def list_products(self, request: Request, business_id: UUID) -> Response:
        """List all products for a business."""
        try:
            return self._list_products_for_scope(
                request,
                business_id=business_id,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="List products by category",
        operation_description="List all products belonging to a specific category.",
        operation_id="inventory_list_products_by_category",
        responses={
            200: ProductResponseSerializer(many=True),
            403: "Permission denied",
            404: "Category not found",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Inventory"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="(?P<category_id>[^/.]+)/products",
        url_name="category-products",
    )
    def list_products_by_category(self, request: Request, category_id: UUID) -> Response:
        """List products for a category."""
        try:
            category = CategoryRepositoryImpl().get_by_id(category_id)
            if not category:
                raise NotFoundError(detail="Category not found", code="CATEGORY_NOT_FOUND")

            return self._list_products_for_scope(
                request,
                business_id=category.business_id,
                category_id=category.id,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="List products by subcategory",
        operation_description="List all products belonging to a specific subcategory.",
        operation_id="inventory_list_products_by_subcategory",
        responses={
            200: ProductResponseSerializer(many=True),
            403: "Permission denied",
            404: "Subcategory not found",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Inventory"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="(?P<subcategory_id>[^/.]+)/products",
        url_name="subcategory-products",
    )
    def list_products_by_subcategory(self, request: Request, subcategory_id: UUID) -> Response:
        """List products for a subcategory."""
        try:
            subcategory = SubCategoryRepositoryImpl().get_by_id(subcategory_id)
            if not subcategory:
                raise NotFoundError(
                    detail="Subcategory not found",
                    code="SUBCATEGORY_NOT_FOUND",
                )

            return self._list_products_for_scope(
                request,
                business_id=subcategory.business_id,
                category_id=subcategory.category_id,
                subcategory_id=subcategory.id,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Create product",
        operation_description="Create a new product for a business.",
        operation_id="inventory_create_product",
        request_body=ProductCreateSerializer,
        responses={
            201: ProductResponseSerializer(),
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
        url_path="(?P<business_id>[^/.]+)/products",
        url_name="product-create",
    )
    def create_product(self, request: Request, business_id: UUID) -> Response:
        """Create a new product."""
        serializer = ProductCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            dto = serializer.to_dto()
            use_case = CreateProductUseCase(
                product_repository=ProductRepositoryImpl(),
                category_repository=CategoryRepositoryImpl(),
                subcategory_repository=SubCategoryRepositoryImpl(),
                business_id=business_id,
                user_id=request.user.id,
            )
            product_dto = use_case.execute(dto)

            return self.success(
                message="Product created successfully",
                data=ProductResponseSerializer.from_dto(product_dto),
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get product",
        operation_description="Get product details by ID.",
        operation_id="inventory_get_product",
        responses={
            200: ProductResponseSerializer(),
            403: "Permission denied",
            404: "Product not found",
            400: "Validation error",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Inventory"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="(?P<business_id>[^/.]+)/products/(?P<product_id>[^/.]+)",
        url_name="product-detail",
    )
    def get_product(self, request: Request, business_id: UUID, product_id: UUID) -> Response:
        """Get product by ID."""
        try:
            use_case = GetProductUseCase(
                product_repository=ProductRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                product_id=product_id,
                business_id=business_id,
                user_id=request.user.id,
            )
            product_dto = use_case.execute()

            return self.success(
                message="Product retrieved successfully",
                data=ProductResponseSerializer.from_dto(product_dto),
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Update product",
        operation_description="Update product details.",
        operation_id="inventory_update_product",
        request_body=ProductUpdateSerializer,
        responses={
            200: ProductResponseSerializer(),
            403: "Permission denied",
            404: "Product not found",
            400: "Validation error",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Inventory"],
    )
    @action(
        detail=False,
        methods=["put"],
        url_path="(?P<business_id>[^/.]+)/products/(?P<product_id>[^/.]+)",
        url_name="product-update",
    )
    def update_product(self, request: Request, business_id: UUID, product_id: UUID) -> Response:
        """Update product."""
        serializer = ProductUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            dto = serializer.to_dto()
            use_case = UpdateProductUseCase(
                product_repository=ProductRepositoryImpl(),
                category_repository=CategoryRepositoryImpl(),
                subcategory_repository=SubCategoryRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                product_id=product_id,
                business_id=business_id,
                user_id=request.user.id,
            )
            product_dto = use_case.execute(dto)

            return self.success(
                message="Product updated successfully",
                data=ProductResponseSerializer.from_dto(product_dto),
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Delete product",
        operation_description="Delete a product.",
        operation_id="inventory_delete_product",
        responses={
            204: "Product deleted successfully",
            403: "Permission denied",
            404: "Product not found",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Inventory"],
    )
    @action(
        detail=False,
        methods=["delete"],
        url_path="(?P<business_id>[^/.]+)/products/(?P<product_id>[^/.]+)",
        url_name="product-delete",
    )
    def delete_product(self, request: Request, business_id: UUID, product_id: UUID) -> Response:
        """Delete product."""
        try:
            use_case = DeleteProductUseCase(
                product_repository=ProductRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                product_id=product_id,
                business_id=business_id,
                user_id=request.user.id,
            )
            use_case.execute()

            return self.success(
                message="Product deleted successfully",
                status_code=status.HTTP_204_NO_CONTENT,
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

            data = [LowStockProductSerializer.from_dto(product_dto) for product_dto in products]

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

            data = [ExpiredProductSerializer.from_dto(product_dto) for product_dto in products]

            return self.success(
                message="Expired products retrieved successfully",
                data=data,
                status_code=status.HTTP_200_OK,
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
            from application.use_cases.alert_use_cases import CheckExpiredProductsUseCase

            use_case = CheckExpiredProductsUseCase(
                inventory_domain_service=self._get_inventory_domain_service(),
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

    @swagger_auto_schema(
        operation_summary="Scan barcode",
        operation_description="Scan barcode to get product information. Falls back to product ID if barcode not found.",
        operation_id="inventory_scan_barcode",
        request_body=ProductScanSerializer,
        responses={
            200: ProductScanSerializer(),
            400: "Validation error",
            403: "Permission denied",
            404: "Product not found",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Inventory"],
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="(?P<business_id>[^/.]+)/products/scan-barcode",
        url_name="scan-barcode",
    )
    def scan_barcode(self, request: Request, business_id: UUID) -> Response:
        """Scan barcode to get product information."""
        try:
            barcode = request.data.get("barcode")
            product_id = request.data.get("product_id")  # Fallback option

            if not barcode and not product_id:
                return self.error(
                    message="Barcode or product_id is required",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="MISSING_BARCODE_OR_ID",
                )

            product_repository = ProductRepositoryImpl()

            # Try to find by barcode first
            product = None
            if barcode:
                product = product_repository.get_by_barcode(barcode, business_id)

            # Fallback to product ID if barcode not found
            if not product and product_id:
                try:
                    product = product_repository.get_by_id(UUID(product_id))
                    if product and product.business_id != business_id:
                        product = None
                except (ValueError, TypeError):
                    pass

            if not product:
                return self.error(
                    message="Product not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="PRODUCT_NOT_FOUND",
                )

            # Check if user has access to business
            if not self._get_business_domain_service().user_has_access(
                business_id, request.user.id
            ):
                return self.error(
                    message="You don't have access to this business",
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="PERMISSION_DENIED",
                )

            return self.success(
                message="Product retrieved successfully",
                data=ProductScanSerializer.from_product(product),
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)
