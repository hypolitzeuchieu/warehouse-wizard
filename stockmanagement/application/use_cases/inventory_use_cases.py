"""Inventory use cases."""

from uuid import UUID, uuid4

from django.utils import timezone

from application.dto.inventory_dto import (
    ProductCreateDTO,
    ProductResponseDTO,
    StockMovementCreateDTO,
    StockMovementResponseDTO,
)
from domain.inventory.entities import (
    Product,
    StockMovement,
)
from domain.inventory.repositories import (
    CategoryRepository,
    ProductRepository,
)
from domain.inventory.services import InventoryDomainService
from shared.exceptions.base import BaseAPIException


class CreateProductUseCase:
    """Use case for creating a product."""

    def __init__(
        self,
        product_repository: ProductRepository,
        category_repository: CategoryRepository,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.product_repository = product_repository
        self.category_repository = category_repository
        self.business_id = business_id
        self.user_id = user_id

    def execute(self, dto: ProductCreateDTO) -> ProductResponseDTO:
        """Execute product creation."""
        # Validate category exists
        category = self.category_repository.get_by_id(dto.category_id)
        if not category or category.business_id != self.business_id:
            raise BaseAPIException(
                detail="Category not found",
                code="CATEGORY_NOT_FOUND",
                status_code=404,
            )

        # Check if barcode already exists
        if dto.barcode:
            existing = self.product_repository.get_by_barcode(dto.barcode, self.business_id)
            if existing:
                raise BaseAPIException(
                    detail="Product with this barcode already exists",
                    code="BARCODE_EXISTS",
                    status_code=400,
                )

        # Create product entity
        product = Product(
            id=uuid4(),
            business_id=self.business_id,
            name=dto.name,
            description=dto.description,
            barcode=dto.barcode,
            barcode_image_url=None,  # Will be generated later
            category_id=dto.category_id,
            subcategory_id=dto.subcategory_id,
            purchase_price=dto.purchase_price,
            unit_price=dto.unit_price,
            image_url=dto.image_url,
            quantity=dto.quantity,
            min_quantity=dto.min_quantity,
            expiry_date=dto.expiry_date,
            is_expired=False,
            on_promotion=False,
            promotion_start_date=None,
            promotion_end_date=None,
            promo_price=None,
            created_at=timezone.now(),
            updated_at=timezone.now(),
            created_by=self.user_id,
        )

        # Check expiry
        if product.expiry_date and product.check_expiry():
            product.is_expired = True

        product = self.product_repository.create(product)
        return self._to_dto(product)

    def _to_dto(self, product: Product) -> ProductResponseDTO:
        """Convert product entity to DTO."""
        return ProductResponseDTO(
            id=product.id,
            business_id=product.business_id,
            name=product.name,
            description=product.description,
            barcode=product.barcode,
            barcode_image_url=product.barcode_image_url,
            category_id=product.category_id,
            subcategory_id=product.subcategory_id,
            purchase_price=product.purchase_price,
            unit_price=product.unit_price,
            current_price=product.get_current_price(),
            image_url=product.image_url,
            quantity=product.quantity,
            min_quantity=product.min_quantity,
            is_low_stock=product.is_low_stock(),
            expiry_date=product.expiry_date,
            is_expired=product.is_expired,
            on_promotion=product.on_promotion,
            promotion_start_date=product.promotion_start_date,
            promotion_end_date=product.promotion_end_date,
            promo_price=product.promo_price,
            created_at=product.created_at,
            updated_at=product.updated_at,
        )


class RecordStockMovementUseCase:
    """Use case for recording stock movement."""

    def __init__(
        self,
        inventory_domain_service: InventoryDomainService,
        product_repository: ProductRepository,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.inventory_domain_service = inventory_domain_service
        self.product_repository = product_repository
        self.business_id = business_id
        self.user_id = user_id

    def execute(self, dto: StockMovementCreateDTO) -> StockMovementResponseDTO:
        """Execute stock movement recording."""
        # Validate product exists
        product = self.product_repository.get_by_id(dto.product_id)
        if not product or product.business_id != self.business_id:
            raise BaseAPIException(
                detail="Product not found",
                code="PRODUCT_NOT_FOUND",
                status_code=404,
            )

        # Record movement based on type
        if dto.movement_type == "ENTRY":
            movement = self.inventory_domain_service.record_stock_entry(
                business_id=self.business_id,
                product_id=dto.product_id,
                quantity=dto.quantity,
                user_id=self.user_id,
                reason=dto.reason,
            )
        elif dto.movement_type == "EXIT":
            movement = self.inventory_domain_service.record_stock_exit(
                business_id=self.business_id,
                product_id=dto.product_id,
                quantity=dto.quantity,
                user_id=self.user_id,
                reason=dto.reason,
            )
        else:
            raise BaseAPIException(
                detail="Invalid movement type",
                code="INVALID_MOVEMENT_TYPE",
                status_code=400,
            )

        # Get updated product for response
        updated_product = self.product_repository.get_by_id(dto.product_id)
        return self._to_dto(movement, updated_product)

    def _to_dto(
        self, movement: StockMovement, product: Product | None = None
    ) -> StockMovementResponseDTO:
        """Convert stock movement entity to DTO."""
        return StockMovementResponseDTO(
            id=movement.id,
            business_id=movement.business_id,
            product_id=movement.product_id,
            product_name=product.name if product else None,
            movement_type=movement.movement_type.value,
            quantity=movement.quantity,
            reason=movement.reason,
            user_id=movement.user_id,
            created_at=movement.created_at,
        )


class GetLowStockProductsUseCase:
    """Use case for getting low stock products."""

    def __init__(self, inventory_domain_service: InventoryDomainService, business_id: UUID) -> None:
        """Initialize use case."""
        self.inventory_domain_service = inventory_domain_service
        self.business_id = business_id

    def execute(self) -> list[ProductResponseDTO]:
        """Execute getting low stock products."""
        products = self.inventory_domain_service.get_low_stock_products(self.business_id)
        return [
            ProductResponseDTO(
                id=p.id,
                business_id=p.business_id,
                name=p.name,
                description=p.description,
                barcode=p.barcode,
                barcode_image_url=p.barcode_image_url,
                category_id=p.category_id,
                subcategory_id=p.subcategory_id,
                purchase_price=p.purchase_price,
                unit_price=p.unit_price,
                current_price=p.get_current_price(),
                image_url=p.image_url,
                quantity=p.quantity,
                min_quantity=p.min_quantity,
                is_low_stock=p.is_low_stock(),
                expiry_date=p.expiry_date,
                is_expired=p.is_expired,
                on_promotion=p.on_promotion,
                promotion_start_date=p.promotion_start_date,
                promotion_end_date=p.promotion_end_date,
                promo_price=p.promo_price,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in products
        ]


class CheckExpiredProductsUseCase:
    """Use case for checking expired products."""

    def __init__(self, inventory_domain_service: InventoryDomainService, business_id: UUID) -> None:
        """Initialize use case."""
        self.inventory_domain_service = inventory_domain_service
        self.business_id = business_id

    def execute(self) -> list[ProductResponseDTO]:
        """Execute checking expired products."""
        products = self.inventory_domain_service.check_expired_products(self.business_id)
        return [
            ProductResponseDTO(
                id=p.id,
                business_id=p.business_id,
                name=p.name,
                description=p.description,
                barcode=p.barcode,
                barcode_image_url=p.barcode_image_url,
                category_id=p.category_id,
                subcategory_id=p.subcategory_id,
                purchase_price=p.purchase_price,
                unit_price=p.unit_price,
                current_price=p.get_current_price(),
                image_url=p.image_url,
                quantity=p.quantity,
                min_quantity=p.min_quantity,
                is_low_stock=p.is_low_stock(),
                expiry_date=p.expiry_date,
                is_expired=p.is_expired,
                on_promotion=p.on_promotion,
                promotion_start_date=p.promotion_start_date,
                promotion_end_date=p.promotion_end_date,
                promo_price=p.promo_price,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in products
        ]
