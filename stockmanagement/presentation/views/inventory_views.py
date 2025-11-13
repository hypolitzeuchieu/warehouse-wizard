"""Inventory API views."""

from uuid import UUID

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from application.use_cases.inventory_use_cases import (
    CheckExpiredProductsUseCase,
    CreateProductUseCase,
    GetLowStockProductsUseCase,
    RecordStockMovementUseCase,
)
from domain.inventory.services import InventoryDomainService
from infrastructure.persistence.repositories import (
    CategoryRepositoryImpl,
    ProductRepositoryImpl,
    StockMovementRepositoryImpl,
)
from presentation.serializers.inventory_serializers import (
    ProductCreateSerializer,
    StockMovementCreateSerializer,
)
from shared.response.mixin import ResponseMixin


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_product_view(request: Request, business_id: UUID) -> Response:
    """Create product endpoint."""
    serializer = ProductCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return ResponseMixin.error(
            message="Validation error",
            errors=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
        )

    try:
        dto = serializer.to_dto()
        use_case = CreateProductUseCase(
            product_repository=ProductRepositoryImpl(),
            category_repository=CategoryRepositoryImpl(),
            business_id=business_id,
            user_id=request.user.id,
        )
        product_dto = use_case.execute(dto)

        return ResponseMixin.success(
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
        return ResponseMixin.from_exception(e)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def record_stock_movement_view(request: Request, business_id: UUID) -> Response:
    """Record stock movement endpoint."""
    serializer = StockMovementCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return ResponseMixin.error(
            message="Validation error",
            errors=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
        )

    try:
        dto = serializer.to_dto()
        inventory_domain_service = InventoryDomainService(
            product_repository=ProductRepositoryImpl(),
            stock_movement_repository=StockMovementRepositoryImpl(),
        )
        use_case = RecordStockMovementUseCase(
            inventory_domain_service=inventory_domain_service,
            product_repository=ProductRepositoryImpl(),
            business_id=business_id,
            user_id=request.user.id,
        )
        movement_dto = use_case.execute(dto)

        return ResponseMixin.success(
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
        return ResponseMixin.from_exception(e)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_low_stock_products_view(request: Request, business_id: UUID) -> Response:
    """Get low stock products endpoint."""
    try:
        inventory_domain_service = InventoryDomainService(
            product_repository=ProductRepositoryImpl(),
            stock_movement_repository=StockMovementRepositoryImpl(),
        )
        use_case = GetLowStockProductsUseCase(
            inventory_domain_service=inventory_domain_service,
            business_id=business_id,
        )
        products = use_case.execute()

        return ResponseMixin.success(
            message="Low stock products retrieved successfully",
            data=[
                {
                    "id": str(p.id),
                    "name": p.name,
                    "quantity": p.quantity,
                    "min_quantity": p.min_quantity,
                    "is_low_stock": p.is_low_stock,
                }
                for p in products
            ],
            status_code=status.HTTP_200_OK,
        )
    except Exception as e:
        return ResponseMixin.from_exception(e)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_expired_products_view(request: Request, business_id: UUID) -> Response:
    """Get expired products endpoint."""
    try:
        inventory_domain_service = InventoryDomainService(
            product_repository=ProductRepositoryImpl(),
            stock_movement_repository=StockMovementRepositoryImpl(),
        )
        use_case = CheckExpiredProductsUseCase(
            inventory_domain_service=inventory_domain_service,
            business_id=business_id,
        )
        products = use_case.execute()

        return ResponseMixin.success(
            message="Expired products retrieved successfully",
            data=[
                {
                    "id": str(p.id),
                    "name": p.name,
                    "expiry_date": p.expiry_date.isoformat() if p.expiry_date else None,
                    "is_expired": p.is_expired,
                }
                for p in products
            ],
            status_code=status.HTTP_200_OK,
        )
    except Exception as e:
        return ResponseMixin.from_exception(e)
