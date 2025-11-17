"""Inventory use cases."""

import logging
from uuid import UUID, uuid4

from django.utils import timezone

from application.dto.inventory_dto import (
    ProductCreateDTO,
    ProductResponseDTO,
    ProductUpdateDTO,
    StockMovementCreateDTO,
    StockMovementResponseDTO,
)
from domain.business.services import BusinessDomainService
from domain.inventory.entities import (
    Product,
    StockMovement,
)
from domain.inventory.repositories import (
    CategoryRepository,
    ProductRepository,
)
from domain.inventory.services import InventoryDomainService
from shared.exceptions.specific import BadRequestError, ForbiddenError, NotFoundError

logger = logging.getLogger(__name__)


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
            raise NotFoundError(
                detail="Category not found",
                code="CATEGORY_NOT_FOUND",
            )

        # Check if barcode already exists
        if dto.barcode:
            existing = self.product_repository.get_by_barcode(dto.barcode, self.business_id)
            if existing:
                raise BadRequestError(
                    detail="Product with this barcode already exists",
                    code="BARCODE_EXISTS",
                )

        # Generate barcode if not provided
        barcode_value = dto.barcode
        barcode_image_url = None

        if not barcode_value:
            try:
                from shared.services.barcode_service import BarcodeService

                barcode_service = BarcodeService()
                barcode_value, barcode_image_url = barcode_service.generate_and_upload_barcode()
                logger.info(f"Generated barcode for product: {barcode_value}")
            except Exception as e:
                logger.warning(f"Failed to generate barcode for product: {str(e)}")
                # Continue without barcode - it can be generated later

        # Create product entity
        product = Product(
            id=uuid4(),
            business_id=self.business_id,
            name=dto.name,
            description=dto.description,
            barcode=barcode_value,
            barcode_image_url=barcode_image_url,
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
            raise NotFoundError(
                detail="Product not found",
                code="PRODUCT_NOT_FOUND",
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
            raise BadRequestError(
                detail="Invalid movement type",
                code="INVALID_MOVEMENT_TYPE",
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


class GetProductUseCase:
    """Use case for getting a product by ID."""

    def __init__(
        self,
        product_repository: ProductRepository,
        business_domain_service: BusinessDomainService,
        product_id: UUID,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.product_repository = product_repository
        self.business_domain_service = business_domain_service
        self.product_id = product_id
        self.business_id = business_id
        self.user_id = user_id

    def execute(self) -> ProductResponseDTO:
        """Execute getting product."""
        # Check if user has access to business
        if not self.business_domain_service.user_has_access(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="You don't have access to this business",
                code="PERMISSION_DENIED",
            )

        product = self.product_repository.get_by_id(self.product_id)
        if not product or product.business_id != self.business_id:
            raise NotFoundError(
                detail="Product not found",
                code="PRODUCT_NOT_FOUND",
            )

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


class ListProductsUseCase:
    """Use case for listing products for a business."""

    def __init__(
        self,
        product_repository: ProductRepository,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,
        category_id: UUID | None = None,
        low_stock_only: bool = False,
        expired_only: bool = False,
    ) -> None:
        """Initialize use case."""
        self.product_repository = product_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id
        self.category_id = category_id
        self.low_stock_only = low_stock_only
        self.expired_only = expired_only

    def execute(self) -> list[ProductResponseDTO]:
        """Execute listing products."""
        # Check if user has access to business
        if not self.business_domain_service.user_has_access(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="You don't have access to this business",
                code="PERMISSION_DENIED",
            )

        products = self.product_repository.get_by_business(
            business_id=self.business_id,
            category_id=self.category_id,
            low_stock_only=self.low_stock_only,
            expired_only=self.expired_only,
        )

        return [self._to_dto(product) for product in products]

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


class UpdateProductUseCase:
    """Use case for updating a product."""

    def __init__(
        self,
        product_repository: ProductRepository,
        category_repository: CategoryRepository,
        business_domain_service: BusinessDomainService,
        product_id: UUID,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.product_repository = product_repository
        self.category_repository = category_repository
        self.business_domain_service = business_domain_service
        self.product_id = product_id
        self.business_id = business_id
        self.user_id = user_id

    def execute(self, dto: ProductUpdateDTO) -> ProductResponseDTO:
        """Execute product update."""
        # Check if user has access to business
        if not self.business_domain_service.user_has_access(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="You don't have access to this business",
                code="PERMISSION_DENIED",
            )

        product = self.product_repository.get_by_id(self.product_id)
        if not product or product.business_id != self.business_id:
            raise NotFoundError(
                detail="Product not found",
                code="PRODUCT_NOT_FOUND",
            )

        # Update fields
        if dto.name is not None:
            product.name = dto.name
        if dto.description is not None:
            product.description = dto.description
        if dto.barcode is not None:
            # Check if barcode already exists for another product
            existing = self.product_repository.get_by_barcode(dto.barcode, self.business_id)
            if existing and existing.id != product.id:
                raise BadRequestError(
                    detail="Product with this barcode already exists",
                    code="BARCODE_EXISTS",
                )
            product.barcode = dto.barcode
        if dto.category_id is not None:
            category = self.category_repository.get_by_id(dto.category_id)
            if not category or category.business_id != self.business_id:
                raise NotFoundError(
                    detail="Category not found",
                    code="CATEGORY_NOT_FOUND",
                )
            product.category_id = dto.category_id
        if dto.subcategory_id is not None:
            product.subcategory_id = dto.subcategory_id
        if dto.purchase_price is not None:
            product.purchase_price = dto.purchase_price
        if dto.unit_price is not None:
            product.unit_price = dto.unit_price
        if dto.image_url is not None:
            product.image_url = dto.image_url
        if dto.quantity is not None:
            product.quantity = dto.quantity
        if dto.min_quantity is not None:
            product.min_quantity = dto.min_quantity
        if dto.expiry_date is not None:
            product.expiry_date = dto.expiry_date
            # Recheck expiry
            if product.expiry_date and product.check_expiry():
                product.is_expired = True
            else:
                product.is_expired = False

        product.updated_at = timezone.now()
        product = self.product_repository.update(product)
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


class DeleteProductUseCase:
    """Use case for deleting a product."""

    def __init__(
        self,
        product_repository: ProductRepository,
        business_domain_service: BusinessDomainService,
        product_id: UUID,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.product_repository = product_repository
        self.business_domain_service = business_domain_service
        self.product_id = product_id
        self.business_id = business_id
        self.user_id = user_id

    def execute(self) -> None:
        """Execute product deletion."""
        # Check if user has access to business
        if not self.business_domain_service.user_has_access(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="You don't have access to this business",
                code="PERMISSION_DENIED",
            )

        product = self.product_repository.get_by_id(self.product_id)
        if not product or product.business_id != self.business_id:
            raise NotFoundError(
                detail="Product not found",
                code="PRODUCT_NOT_FOUND",
            )

        self.product_repository.delete(self.product_id)
