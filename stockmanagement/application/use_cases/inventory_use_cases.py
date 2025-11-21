"""Inventory use cases."""

import logging
from uuid import UUID, uuid4

from django.utils import timezone

from application.dto.inventory_dto import (
    CategoryCreateDTO,
    CategoryResponseDTO,
    CategoryUpdateDTO,
    ProductCreateDTO,
    ProductResponseDTO,
    ProductUpdateDTO,
    StockMovementCreateDTO,
    StockMovementResponseDTO,
    SubCategoryCreateDTO,
    SubCategoryResponseDTO,
    SubCategoryUpdateDTO,
)
from domain.business.services import BusinessDomainService
from domain.inventory.entities import (
    Category,
    Product,
    StockMovement,
    SubCategory,
)
from domain.inventory.repositories import (
    CategoryRepository,
    ProductRepository,
    SubCategoryRepository,
)
from domain.inventory.services import InventoryDomainService
from shared.exceptions.specific import BadRequestError, ForbiddenError, NotFoundError

logger = logging.getLogger(__name__)


def _category_to_dto(category: Category) -> CategoryResponseDTO:
    """Convert category entity to response DTO."""
    return CategoryResponseDTO(
        id=category.id,
        business_id=category.business_id,
        name=category.name,
        description=category.description,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


def _subcategory_to_dto(subcategory: SubCategory) -> SubCategoryResponseDTO:
    """Convert subcategory entity to response DTO."""
    return SubCategoryResponseDTO(
        id=subcategory.id,
        business_id=subcategory.business_id,
        category_id=subcategory.category_id,
        name=subcategory.name,
        description=subcategory.description,
        created_at=subcategory.created_at,
        updated_at=subcategory.updated_at,
    )


class ListCategoriesUseCase:
    """Use case for listing categories for a business."""

    def __init__(
        self,
        category_repository: CategoryRepository,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        self.category_repository = category_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id

    def execute(self) -> list[CategoryResponseDTO]:
        if not self.business_domain_service.user_has_access(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="You don't have access to this business",
                code="PERMISSION_DENIED",
            )
        categories = self.category_repository.get_by_business(self.business_id)
        return [_category_to_dto(category) for category in categories]


class CreateCategoryUseCase:
    """Use case for creating a category."""

    def __init__(
        self,
        category_repository: CategoryRepository,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        self.category_repository = category_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id

    def execute(self, dto: CategoryCreateDTO) -> CategoryResponseDTO:
        if not self.business_domain_service.can_user_manage_members(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="You don't have permission to create categories for this business",
                code="PERMISSION_DENIED",
            )

        existing = self.category_repository.get_by_name(self.business_id, dto.name)
        if existing:
            raise BadRequestError(
                detail="Category with this name already exists for this business",
                code="CATEGORY_NAME_EXISTS",
            )

        category = Category(
            id=uuid4(),
            business_id=self.business_id,
            name=dto.name,
            description=dto.description,
            created_at=timezone.now(),
            updated_at=timezone.now(),
            created_by=self.user_id,
        )
        category = self.category_repository.create(category)
        return _category_to_dto(category)


class GetCategoryUseCase:
    """Use case for getting a category by ID."""

    def __init__(
        self,
        category_repository: CategoryRepository,
        business_domain_service: BusinessDomainService,
        category_id: UUID,
        user_id: UUID,
    ) -> None:
        self.category_repository = category_repository
        self.business_domain_service = business_domain_service
        self.category_id = category_id
        self.user_id = user_id

    def execute(self) -> CategoryResponseDTO:
        category = self.category_repository.get_by_id(self.category_id)
        if not category:
            raise NotFoundError(detail="Category not found", code="CATEGORY_NOT_FOUND")

        if not self.business_domain_service.user_has_access(category.business_id, self.user_id):
            raise ForbiddenError(
                detail="You don't have access to this category",
                code="PERMISSION_DENIED",
            )

        return _category_to_dto(category)


class UpdateCategoryUseCase:
    """Use case for updating a category."""

    def __init__(
        self,
        category_repository: CategoryRepository,
        business_domain_service: BusinessDomainService,
        category_id: UUID,
        user_id: UUID,
    ) -> None:
        self.category_repository = category_repository
        self.business_domain_service = business_domain_service
        self.category_id = category_id
        self.user_id = user_id

    def execute(self, dto: CategoryUpdateDTO) -> CategoryResponseDTO:
        category = self.category_repository.get_by_id(self.category_id)
        if not category:
            raise NotFoundError(detail="Category not found", code="CATEGORY_NOT_FOUND")

        if not self.business_domain_service.can_user_manage_members(
            category.business_id, self.user_id
        ):
            raise ForbiddenError(
                detail="You don't have permission to update this category",
                code="PERMISSION_DENIED",
            )

        if dto.name and dto.name != category.name:
            existing = self.category_repository.get_by_name(category.business_id, dto.name)
            if existing:
                raise BadRequestError(
                    detail="Category with this name already exists for this business",
                    code="CATEGORY_NAME_EXISTS",
                )
            category.name = dto.name

        if dto.description is not None:
            category.description = dto.description

        category.updated_at = timezone.now()
        category = self.category_repository.update(category)
        return _category_to_dto(category)


class DeleteCategoryUseCase:
    """Use case for deleting a category."""

    def __init__(
        self,
        category_repository: CategoryRepository,
        business_domain_service: BusinessDomainService,
        category_id: UUID,
        user_id: UUID,
    ) -> None:
        self.category_repository = category_repository
        self.business_domain_service = business_domain_service
        self.category_id = category_id
        self.user_id = user_id

    def execute(self) -> None:
        category = self.category_repository.get_by_id(self.category_id)
        if not category:
            raise NotFoundError(detail="Category not found", code="CATEGORY_NOT_FOUND")

        if not self.business_domain_service.can_user_manage_members(
            category.business_id, self.user_id
        ):
            raise ForbiddenError(
                detail="You don't have permission to delete this category",
                code="PERMISSION_DENIED",
            )

        self.category_repository.delete(self.category_id)


class ListSubCategoriesUseCase:
    """Use case for listing subcategories under a category."""

    def __init__(
        self,
        subcategory_repository: SubCategoryRepository,
        category_repository: CategoryRepository,
        business_domain_service: BusinessDomainService,
        category_id: UUID,
        user_id: UUID,
    ) -> None:
        self.subcategory_repository = subcategory_repository
        self.category_repository = category_repository
        self.business_domain_service = business_domain_service
        self.category_id = category_id
        self.user_id = user_id

    def execute(self) -> list[SubCategoryResponseDTO]:
        category = self.category_repository.get_by_id(self.category_id)
        if not category:
            raise NotFoundError(detail="Category not found", code="CATEGORY_NOT_FOUND")

        if not self.business_domain_service.user_has_access(category.business_id, self.user_id):
            raise ForbiddenError(
                detail="You don't have access to this category",
                code="PERMISSION_DENIED",
            )

        subcategories = self.subcategory_repository.get_by_category(self.category_id)
        return [_subcategory_to_dto(subcategory) for subcategory in subcategories]


class CreateSubCategoryUseCase:
    """Use case for creating a subcategory."""

    def __init__(
        self,
        subcategory_repository: SubCategoryRepository,
        category_repository: CategoryRepository,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        self.subcategory_repository = subcategory_repository
        self.category_repository = category_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id

    def execute(self, dto: SubCategoryCreateDTO) -> SubCategoryResponseDTO:
        if not self.business_domain_service.can_user_manage_members(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="You don't have permission to create subcategories for this business",
                code="PERMISSION_DENIED",
            )

        category = self.category_repository.get_by_id(dto.category_id)
        if not category:
            raise NotFoundError(
                detail=f"Category with ID {dto.category_id} not found",
                code="CATEGORY_NOT_FOUND",
            )
        category_business_id = UUID(str(category.business_id))
        use_case_business_id = UUID(str(self.business_id))

        if category_business_id != use_case_business_id:
            logger.error(
                f"Category {dto.category_id} does not belong to business {self.business_id}"
            )
            raise NotFoundError(
                detail=f"Category {dto.category_id} does not belong to business {self.business_id}",
                code="CATEGORY_NOT_FOUND",
            )

        existing = self.subcategory_repository.get_by_name(dto.category_id, dto.name)
        if existing:
            raise BadRequestError(
                detail="Subcategory with this name already exists in this category",
                code="SUBCATEGORY_NAME_EXISTS",
            )

        subcategory = SubCategory(
            id=uuid4(),
            business_id=self.business_id,
            category_id=dto.category_id,
            name=dto.name,
            description=dto.description,
            created_at=timezone.now(),
            updated_at=timezone.now(),
            created_by=self.user_id,
        )
        subcategory = self.subcategory_repository.create(subcategory)
        return _subcategory_to_dto(subcategory)


class GetSubCategoryUseCase:
    """Use case for getting a subcategory by ID."""

    def __init__(
        self,
        subcategory_repository: SubCategoryRepository,
        business_domain_service: BusinessDomainService,
        subcategory_id: UUID,
        user_id: UUID,
    ) -> None:
        self.subcategory_repository = subcategory_repository
        self.business_domain_service = business_domain_service
        self.subcategory_id = subcategory_id
        self.user_id = user_id

    def execute(self) -> SubCategoryResponseDTO:
        subcategory = self.subcategory_repository.get_by_id(self.subcategory_id)
        if not subcategory:
            raise NotFoundError(detail="Subcategory not found", code="SUBCATEGORY_NOT_FOUND")

        if not self.business_domain_service.user_has_access(subcategory.business_id, self.user_id):
            raise ForbiddenError(
                detail="You don't have access to this subcategory",
                code="PERMISSION_DENIED",
            )

        return _subcategory_to_dto(subcategory)


class UpdateSubCategoryUseCase:
    """Use case for updating a subcategory."""

    def __init__(
        self,
        subcategory_repository: SubCategoryRepository,
        category_repository: CategoryRepository,
        business_domain_service: BusinessDomainService,
        subcategory_id: UUID,
        user_id: UUID,
    ) -> None:
        self.subcategory_repository = subcategory_repository
        self.category_repository = category_repository
        self.business_domain_service = business_domain_service
        self.subcategory_id = subcategory_id
        self.user_id = user_id

    def execute(self, dto: SubCategoryUpdateDTO) -> SubCategoryResponseDTO:
        subcategory = self.subcategory_repository.get_by_id(self.subcategory_id)
        if not subcategory:
            raise NotFoundError(detail="Subcategory not found", code="SUBCATEGORY_NOT_FOUND")

        if not self.business_domain_service.can_user_manage_members(
            subcategory.business_id, self.user_id
        ):
            raise ForbiddenError(
                detail="You don't have permission to update this subcategory",
                code="PERMISSION_DENIED",
            )

        if dto.name and dto.name != subcategory.name:
            existing = self.subcategory_repository.get_by_name(subcategory.category_id, dto.name)
            if existing:
                raise BadRequestError(
                    detail="Subcategory with this name already exists in this category",
                    code="SUBCATEGORY_NAME_EXISTS",
                )
            subcategory.name = dto.name

        if dto.description is not None:
            subcategory.description = dto.description

        subcategory.updated_at = timezone.now()
        subcategory = self.subcategory_repository.update(subcategory)
        return _subcategory_to_dto(subcategory)


class DeleteSubCategoryUseCase:
    """Use case for deleting a subcategory."""

    def __init__(
        self,
        subcategory_repository: SubCategoryRepository,
        business_domain_service: BusinessDomainService,
        subcategory_id: UUID,
        user_id: UUID,
    ) -> None:
        self.subcategory_repository = subcategory_repository
        self.business_domain_service = business_domain_service
        self.subcategory_id = subcategory_id
        self.user_id = user_id

    def execute(self) -> None:
        subcategory = self.subcategory_repository.get_by_id(self.subcategory_id)
        if not subcategory:
            raise NotFoundError(detail="Subcategory not found", code="SUBCATEGORY_NOT_FOUND")

        if not self.business_domain_service.can_user_manage_members(
            subcategory.business_id, self.user_id
        ):
            raise ForbiddenError(
                detail="You don't have permission to delete this subcategory",
                code="PERMISSION_DENIED",
            )

        self.subcategory_repository.delete(self.subcategory_id)


class CreateProductUseCase:
    """Use case for creating a product."""

    def __init__(
        self,
        product_repository: ProductRepository,
        category_repository: CategoryRepository,
        subcategory_repository: SubCategoryRepository,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.product_repository = product_repository
        self.category_repository = category_repository
        self.subcategory_repository = subcategory_repository
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

        subcategory_id = dto.subcategory_id
        if subcategory_id:
            subcategory = self.subcategory_repository.get_by_id(subcategory_id)
            if not subcategory or subcategory.business_id != self.business_id:
                raise NotFoundError(
                    detail="Subcategory not found",
                    code="SUBCATEGORY_NOT_FOUND",
                )
            if subcategory.category_id != dto.category_id:
                raise BadRequestError(
                    detail="Subcategory does not belong to the specified category",
                    code="SUBCATEGORY_MISMATCH",
                )

        # Check if barcode already exists
        if dto.barcode:
            existing = self.product_repository.get_by_barcode(dto.barcode, self.business_id)
            if existing:
                raise BadRequestError(
                    detail="Product with this barcode already exists",
                    code="BARCODE_EXISTS",
                )

        existing_name = self.product_repository.get_by_name_in_scope(
            business_id=self.business_id,
            category_id=dto.category_id,
            subcategory_id=subcategory_id,
            name=dto.name,
        )
        if existing_name:
            raise BadRequestError(
                detail="Product with this name already exists in this category or subcategory",
                code="PRODUCT_NAME_EXISTS",
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
            subcategory_id=subcategory_id,
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
        subcategory_id: UUID | None = None,
        low_stock_only: bool = False,
        expired_only: bool = False,
    ) -> None:
        """Initialize use case."""
        self.product_repository = product_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id
        self.category_id = category_id
        self.subcategory_id = subcategory_id
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
            subcategory_id=self.subcategory_id,
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
        subcategory_repository: SubCategoryRepository,
        business_domain_service: BusinessDomainService,
        product_id: UUID,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.product_repository = product_repository
        self.category_repository = category_repository
        self.subcategory_repository = subcategory_repository
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

        target_category_id = product.category_id
        if dto.category_id is not None:
            category = self.category_repository.get_by_id(dto.category_id)
            if not category or category.business_id != self.business_id:
                raise NotFoundError(
                    detail="Category not found",
                    code="CATEGORY_NOT_FOUND",
                )
            target_category_id = dto.category_id

        if dto.subcategory_id_provided:
            target_subcategory_id = dto.subcategory_id
        elif dto.category_id is not None:
            target_subcategory_id = None
        else:
            target_subcategory_id = product.subcategory_id

        if target_subcategory_id:
            subcategory = self.subcategory_repository.get_by_id(target_subcategory_id)
            if not subcategory or subcategory.business_id != self.business_id:
                raise NotFoundError(
                    detail="Subcategory not found",
                    code="SUBCATEGORY_NOT_FOUND",
                )
            if subcategory.category_id != target_category_id:
                raise BadRequestError(
                    detail="Subcategory does not belong to the specified category",
                    code="SUBCATEGORY_MISMATCH",
                )

        target_name = dto.name if dto.name is not None else product.name

        existing_with_name = self.product_repository.get_by_name_in_scope(
            business_id=self.business_id,
            category_id=target_category_id,
            subcategory_id=target_subcategory_id,
            name=target_name,
            exclude_id=product.id,
        )
        if existing_with_name:
            raise BadRequestError(
                detail="Product with this name already exists in this category or subcategory",
                code="PRODUCT_NAME_EXISTS",
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
        product.category_id = target_category_id
        product.subcategory_id = target_subcategory_id
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
