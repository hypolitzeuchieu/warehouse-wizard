"""Inventory ViewSet for products and stock movements."""

from __future__ import annotations

from uuid import UUID

from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from application.use_cases.inventory_use_cases import (
    CheckExpiredProductsUseCase as ListExpiredProductsUseCase,
)
from application.use_cases.inventory_use_cases import (
    CreateProductUseCase,
    DeleteProductUseCase,
    GetLowStockProductsUseCase,
    GetProductUseCase,
    ListProductsUseCase,
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
)
from presentation.serializers.inventory_serializers import (
    ProductCreateSerializer,
    ProductUpdateSerializer,
    StockMovementCreateSerializer,
)
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
        operation_summary="List products",
        operation_description="Get all products for a business with optional filters.",
        responses={200: "List of products", 403: "Permission denied"},
        tags=["Inventory"],
    )
    @action(detail=False, methods=["get"], url_path="businesses/(?P<business_id>[^/.]+)/products")
    def list_products(self, request: Request, business_id: UUID) -> Response:
        """List all products for a business."""
        try:
            # Get query parameters
            from shared.security.query_params_validator import QueryParamsValidator

            category_id = QueryParamsValidator.validate_uuid(
                request.query_params.get("category_id"), param_name="category_id"
            )
            low_stock_only = QueryParamsValidator.validate_boolean(
                request.query_params.get("low_stock_only", "false"), param_name="low_stock_only"
            )
            expired_only = QueryParamsValidator.validate_boolean(
                request.query_params.get("expired_only", "false"), param_name="expired_only"
            )

            use_case = ListProductsUseCase(
                product_repository=ProductRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=business_id,
                user_id=request.user.id,
                category_id=category_id,
                low_stock_only=low_stock_only,
                expired_only=expired_only,
            )
            products = use_case.execute()

            data = [
                {
                    "id": str(p.id),
                    "business_id": str(p.business_id),
                    "name": p.name,
                    "description": p.description,
                    "barcode": p.barcode,
                    "barcode_image_url": p.barcode_image_url,
                    "category_id": str(p.category_id),
                    "subcategory_id": str(p.subcategory_id) if p.subcategory_id else None,
                    "purchase_price": str(p.purchase_price),
                    "unit_price": str(p.unit_price),
                    "current_price": str(p.current_price),
                    "image_url": p.image_url,
                    "quantity": p.quantity,
                    "min_quantity": p.min_quantity,
                    "is_low_stock": p.is_low_stock,
                    "expiry_date": p.expiry_date.isoformat() if p.expiry_date else None,
                    "is_expired": p.is_expired,
                    "on_promotion": p.on_promotion,
                    "promotion_start_date": (
                        p.promotion_start_date.isoformat() if p.promotion_start_date else None
                    ),
                    "promotion_end_date": (
                        p.promotion_end_date.isoformat() if p.promotion_end_date else None
                    ),
                    "promo_price": str(p.promo_price) if p.promo_price else None,
                    "created_at": p.created_at.isoformat(),
                    "updated_at": p.updated_at.isoformat(),
                }
                for p in products
            ]

            return self.success(
                message="Products retrieved successfully",
                data=data,
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Create product",
        operation_description="Create a new product for a business.",
        request_body=ProductCreateSerializer,
        responses={201: "Product created", 400: "Validation error", 403: "Permission denied"},
        tags=["Inventory"],
    )
    @action(detail=False, methods=["post"], url_path="businesses/(?P<business_id>[^/.]+)/products")
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
                business_id=business_id,
                user_id=request.user.id,
            )
            product_dto = use_case.execute(dto)

            return self.success(
                message="Product created successfully",
                data={
                    "id": str(product_dto.id),
                    "business_id": str(product_dto.business_id),
                    "name": product_dto.name,
                    "description": product_dto.description,
                    "barcode": product_dto.barcode,
                    "barcode_image_url": product_dto.barcode_image_url,
                    "category_id": str(product_dto.category_id),
                    "subcategory_id": (
                        str(product_dto.subcategory_id) if product_dto.subcategory_id else None
                    ),
                    "purchase_price": str(product_dto.purchase_price),
                    "unit_price": str(product_dto.unit_price),
                    "current_price": str(product_dto.current_price),
                    "image_url": product_dto.image_url,
                    "quantity": product_dto.quantity,
                    "min_quantity": product_dto.min_quantity,
                    "is_low_stock": product_dto.is_low_stock,
                    "expiry_date": (
                        product_dto.expiry_date.isoformat() if product_dto.expiry_date else None
                    ),
                    "is_expired": product_dto.is_expired,
                    "on_promotion": product_dto.on_promotion,
                    "created_at": product_dto.created_at.isoformat(),
                    "updated_at": product_dto.updated_at.isoformat(),
                },
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get product",
        operation_description="Get product details by ID.",
        responses={200: "Product details", 403: "Permission denied", 404: "Product not found"},
        tags=["Inventory"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="businesses/(?P<business_id>[^/.]+)/products/(?P<product_id>[^/.]+)",
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
                data={
                    "id": str(product_dto.id),
                    "business_id": str(product_dto.business_id),
                    "name": product_dto.name,
                    "description": product_dto.description,
                    "barcode": product_dto.barcode,
                    "barcode_image_url": product_dto.barcode_image_url,
                    "category_id": str(product_dto.category_id),
                    "subcategory_id": (
                        str(product_dto.subcategory_id) if product_dto.subcategory_id else None
                    ),
                    "purchase_price": str(product_dto.purchase_price),
                    "unit_price": str(product_dto.unit_price),
                    "current_price": str(product_dto.current_price),
                    "image_url": product_dto.image_url,
                    "quantity": product_dto.quantity,
                    "min_quantity": product_dto.min_quantity,
                    "is_low_stock": product_dto.is_low_stock,
                    "expiry_date": (
                        product_dto.expiry_date.isoformat() if product_dto.expiry_date else None
                    ),
                    "is_expired": product_dto.is_expired,
                    "on_promotion": product_dto.on_promotion,
                    "promotion_start_date": (
                        product_dto.promotion_start_date.isoformat()
                        if product_dto.promotion_start_date
                        else None
                    ),
                    "promotion_end_date": (
                        product_dto.promotion_end_date.isoformat()
                        if product_dto.promotion_end_date
                        else None
                    ),
                    "promo_price": (
                        str(product_dto.promo_price) if product_dto.promo_price else None
                    ),
                    "created_at": product_dto.created_at.isoformat(),
                    "updated_at": product_dto.updated_at.isoformat(),
                },
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Update product",
        operation_description="Update product details.",
        request_body=ProductUpdateSerializer,
        responses={200: "Product updated", 403: "Permission denied", 404: "Product not found"},
        tags=["Inventory"],
        method="put",
    )
    @swagger_auto_schema(
        operation_summary="Update product (partial)",
        operation_description="Partially update product details.",
        request_body=ProductUpdateSerializer,
        responses={200: "Product updated", 403: "Permission denied", 404: "Product not found"},
        tags=["Inventory"],
        method="patch",
    )
    @action(
        detail=False,
        methods=["put", "patch"],
        url_path="businesses/(?P<business_id>[^/.]+)/products/(?P<product_id>[^/.]+)",
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
                business_domain_service=self._get_business_domain_service(),
                product_id=product_id,
                business_id=business_id,
                user_id=request.user.id,
            )
            product_dto = use_case.execute(dto)

            return self.success(
                message="Product updated successfully",
                data={
                    "id": str(product_dto.id),
                    "name": product_dto.name,
                    "description": product_dto.description,
                    "barcode": product_dto.barcode,
                    "barcode_image_url": product_dto.barcode_image_url,
                    "category_id": str(product_dto.category_id),
                    "subcategory_id": (
                        str(product_dto.subcategory_id) if product_dto.subcategory_id else None
                    ),
                    "purchase_price": str(product_dto.purchase_price),
                    "unit_price": str(product_dto.unit_price),
                    "current_price": str(product_dto.current_price),
                    "image_url": product_dto.image_url,
                    "quantity": product_dto.quantity,
                    "min_quantity": product_dto.min_quantity,
                    "is_low_stock": product_dto.is_low_stock,
                    "expiry_date": (
                        product_dto.expiry_date.isoformat() if product_dto.expiry_date else None
                    ),
                    "is_expired": product_dto.is_expired,
                    "updated_at": product_dto.updated_at.isoformat(),
                },
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Delete product",
        operation_description="Delete a product.",
        responses={200: "Product deleted", 403: "Permission denied", 404: "Product not found"},
        tags=["Inventory"],
    )
    @action(
        detail=False,
        methods=["delete"],
        url_path="businesses/(?P<business_id>[^/.]+)/products/(?P<product_id>[^/.]+)",
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
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Record stock movement",
        operation_description="Record a stock movement (ENTRY, EXIT, or ADJUSTMENT).",
        request_body=StockMovementCreateSerializer,
        responses={201: "Stock movement recorded", 400: "Validation error"},
        tags=["Inventory"],
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="businesses/(?P<business_id>[^/.]+)/stock-movements",
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
                data={
                    "id": str(movement_dto.id),
                    "business_id": str(movement_dto.business_id),
                    "product_id": str(movement_dto.product_id),
                    "product_name": movement_dto.product_name,
                    "movement_type": movement_dto.movement_type,
                    "quantity": movement_dto.quantity,
                    "reason": movement_dto.reason,
                    "user_id": str(movement_dto.user_id),
                    "created_at": movement_dto.created_at.isoformat(),
                },
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get low stock products",
        operation_description="Get all products with low stock for a business.",
        responses={200: "List of low stock products", 403: "Permission denied"},
        tags=["Inventory"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="businesses/(?P<business_id>[^/.]+)/products/low-stock",
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
                {
                    "id": str(p.id),
                    "name": p.name,
                    "quantity": p.quantity,
                    "min_quantity": p.min_quantity,
                    "is_low_stock": p.is_low_stock,
                }
                for p in products
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
        responses={200: "List of expired products", 403: "Permission denied"},
        tags=["Inventory"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="businesses/(?P<business_id>[^/.]+)/products/expired",
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
                {
                    "id": str(p.id),
                    "name": p.name,
                    "expiry_date": p.expiry_date.isoformat() if p.expiry_date else None,
                    "is_expired": p.is_expired,
                }
                for p in products
            ]

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
        responses={200: "Expired products checked and notifications created"},
        tags=["Inventory"],
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="businesses/(?P<business_id>[^/.]+)/products/check-expired",
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
        responses={200: "Low stock products checked and notifications created"},
        tags=["Inventory"],
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="businesses/(?P<business_id>[^/.]+)/products/check-low-stock",
    )
    def check_low_stock_products(self, request: Request, business_id: UUID) -> Response:
        """Check low stock products and create notifications."""
        try:
            from application.use_cases.alert_use_cases import CheckLowStockProductsUseCase

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
        responses={200: "Product information", 404: "Product not found"},
        tags=["Inventory"],
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="businesses/(?P<business_id>[^/.]+)/products/scan-barcode",
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
                data={
                    "id": str(product.id),
                    "name": product.name,
                    "barcode": product.barcode,
                    "barcode_image_url": product.barcode_image_url,
                    "unit_price": str(product.unit_price),
                    "current_price": str(product.get_current_price()),
                    "quantity": product.quantity,
                    "is_low_stock": product.is_low_stock(),
                    "is_expired": product.is_expired,
                },
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)
