"""Inventory use cases."""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from django.db import transaction
from django.utils import timezone

from application.dto.inventory_dto import (
    CategoryCreateDTO,
    CategoryResponseDTO,
    CategoryUpdateDTO,
    InventoryReportDTO,
    ProductCreateDTO,
    ProductResponseDTO,
    ProductStockInfoDTO,
    ProductUpdateDTO,
    StockMovementCreateDTO,
    StockMovementResponseDTO,
    StockMovementSummaryDTO,
    StockReportDTO,
    SubCategoryCreateDTO,
    SubCategoryResponseDTO,
    SubCategoryUpdateDTO,
)
from domain.business.services import BusinessDomainService
from domain.inventory.entities import (
    Category,
    Product,
    StockMovement,
    StockMovementType,
    SubCategory,
)
from domain.inventory.repositories import (
    CategoryRepository,
    ProductRepository,
    StockMovementRepository,
    SubCategoryRepository,
)
from domain.inventory.services import InventoryDomainService
from domain.notifications.services import NotificationDomainService
from domain.sales.services import DateRangeValidationService
from shared.exceptions.specific import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
)
from shared.services.barcode_service import BarcodeService
from shared.services.s3_service import S3Service
from shared.utils.validation import (
    validate_business_access,
    validate_entity_belongs_to_business,
)

logger = logging.getLogger(__name__)


def _product_to_dto(product: Product) -> ProductResponseDTO:
    """Convert product entity to DTO (shared utility function)."""
    image_url = product.image_url
    barcode_image_url = product.barcode_image_url

    try:
        s3 = S3Service()
        if image_url:
            image_url = s3.generate_presigned_get_url(image_url, expires_in=86400) or image_url
        if barcode_image_url:
            barcode_image_url = (
                s3.generate_presigned_get_url(barcode_image_url, expires_in=86400)
                or barcode_image_url
            )
    except Exception:
        pass

    return ProductResponseDTO(
        id=product.id,
        business_id=product.business_id,
        name=product.name,
        description=product.description,
        barcode=product.barcode,
        barcode_image_url=barcode_image_url,
        category_id=product.category_id,
        subcategory_id=product.subcategory_id,
        purchase_price=product.purchase_price,
        unit_price=product.unit_price,
        current_price=product.get_current_price(),
        image_url=image_url,
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


def _normalize_uuid(value: UUID | str | None) -> UUID | None:
    """
    Normalize UUID value to UUID type for consistent comparison.

    Args:
        value: UUID, string, or None value to normalize

    Returns:
        UUID object or None if value is None
    """
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        return None


def _compare_business_ids(
    entity_business_id: UUID | str | None, target_business_id: UUID | str | None
) -> bool:
    """
    Compare two business IDs safely, handling UUID and string types.

    Args:
        entity_business_id: Business ID from entity (can be UUID or str)
        target_business_id: Target business ID to compare (can be UUID or str)

    Returns:
        True if both IDs are equal, False otherwise
    """
    normalized_entity = _normalize_uuid(entity_business_id)
    normalized_target = _normalize_uuid(target_business_id)

    if normalized_entity is None or normalized_target is None:
        return False

    return normalized_entity == normalized_target


def _validate_subcategory_belongs_to_category(
    subcategory: SubCategory,
    category_id: UUID,
) -> None:
    """
    Validate that subcategory belongs to the specified category.

    Shared utility function to avoid code duplication.

    Args:
        subcategory: Subcategory entity
        category_id: Expected category ID

    Raises:
        BadRequestError: If subcategory doesn't belong to category
    """
    normalized_subcategory_category = _normalize_uuid(subcategory.category_id)
    normalized_target_category = _normalize_uuid(category_id)

    if normalized_subcategory_category != normalized_target_category:
        raise BadRequestError(
            detail="Subcategory does not belong to the specified category",
            code="SUBCATEGORY_MISMATCH",
        )


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
        validate_business_access(
            business_domain_service=self.business_domain_service,
            business_id=self.business_id,
            user_id=self.user_id,
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
        if not self.business_domain_service.can_create_inventory(self.business_id, self.user_id):
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

        validate_business_access(
            business_domain_service=self.business_domain_service,
            business_id=category.business_id,
            user_id=self.user_id,
            error_message="You don't have access to this category",
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

        if not self.business_domain_service.can_create_inventory(
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

        if not self.business_domain_service.can_create_inventory(
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

        validate_business_access(
            business_domain_service=self.business_domain_service,
            business_id=category.business_id,
            user_id=self.user_id,
            error_message="You don't have access to this category",
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
        if not self.business_domain_service.can_create_inventory(self.business_id, self.user_id):
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

        if not _compare_business_ids(category.business_id, self.business_id):
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

        validate_business_access(
            business_domain_service=self.business_domain_service,
            business_id=subcategory.business_id,
            user_id=self.user_id,
            error_message="You don't have access to this subcategory",
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

        if not self.business_domain_service.can_create_inventory(
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

        if not self.business_domain_service.can_create_inventory(
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
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.product_repository = product_repository
        self.category_repository = category_repository
        self.subcategory_repository = subcategory_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id

    def execute(self, dto: ProductCreateDTO) -> ProductResponseDTO:
        """Execute product creation."""
        if not self.business_domain_service.can_modify_products(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="You don't have permission to create products for this business",
                code="PERMISSION_DENIED",
            )

        category = self.category_repository.get_by_id(dto.category_id)
        if not category:
            logger.error(f"Category {dto.category_id} not found in database")
            raise NotFoundError(
                detail=f"Category with ID {dto.category_id} not found",
                code="CATEGORY_NOT_FOUND",
            )

        # Ensure category belongs to the business
        if not _compare_business_ids(category.business_id, self.business_id):
            logger.warning(
                f"Category {dto.category_id} (business: {category.business_id}) "
                f"does not belong to business {self.business_id}"
            )
            raise NotFoundError(
                detail=f"Category {dto.category_id} does not belong to business {self.business_id}",
                code="CATEGORY_NOT_FOUND",
            )

        subcategory_id = dto.subcategory_id
        if subcategory_id:
            subcategory = self.subcategory_repository.get_by_id(subcategory_id)
            validate_entity_belongs_to_business(
                entity=subcategory,
                business_id=self.business_id,
                entity_name="Subcategory",
            )

            # Ensure subcategory belongs to the specified category
            _validate_subcategory_belongs_to_category(subcategory, dto.category_id)

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

        barcode_value = dto.barcode
        barcode_image_url = None

        # Normalize barcode: treat empty strings as None
        if barcode_value and barcode_value.strip():
            barcode_value = barcode_value.strip()
        else:
            barcode_value = None

        if not barcode_value:
            try:
                barcode_service = BarcodeService()
                barcode_value, barcode_image_url = barcode_service.generate_and_upload_barcode(
                    product_repository=self.product_repository
                )
                logger.info(f"Generated unique barcode for product: {barcode_value}")
            except Exception as e:
                logger.warning(f"Failed to generate barcode for product: {str(e)}")
                # Continue without barcode - it can be generated later
        else:
            logger.info(f"Checking provided barcode for uniqueness: {barcode_value}")
            if self.product_repository.barcode_exists_globally(barcode_value):
                logger.warning(f"Provided barcode {barcode_value} already exists globally")
                raise BadRequestError(
                    detail="Product with this barcode already exists. Barcodes must be unique across all businesses.",
                    code="BARCODE_EXISTS",
                )
            logger.info(f"Provided barcode {barcode_value} is unique")

        # Validate promotion if provided
        if dto.on_promotion:
            if not dto.promo_price or not dto.promotion_start_date or not dto.promotion_end_date:
                raise BadRequestError(
                    detail="promo_price, promotion_start_date, and promotion_end_date are required when on_promotion is True",
                    code="PROMOTION_FIELDS_REQUIRED",
                )
            if dto.promo_price >= dto.unit_price:
                raise BadRequestError(
                    detail="promo_price must be less than unit_price",
                    code="INVALID_PROMO_PRICE",
                )

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
            on_promotion=dto.on_promotion,
            promotion_start_date=dto.promotion_start_date,
            promotion_end_date=dto.promotion_end_date,
            promo_price=dto.promo_price,
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
        return _product_to_dto(product)


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
        validate_entity_belongs_to_business(
            entity=product,
            business_id=self.business_id,
            entity_name="Product",
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
        validate_business_access(
            business_domain_service=self.business_domain_service,
            business_id=self.business_id,
            user_id=self.user_id,
        )

        product = self.product_repository.get_by_id(self.product_id)
        validate_entity_belongs_to_business(
            entity=product,
            business_id=self.business_id,
            entity_name="Product",
        )

        return self._to_dto(product)

    def _to_dto(self, product: Product) -> ProductResponseDTO:
        """Convert product entity to DTO."""
        return _product_to_dto(product)


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
        validate_business_access(
            business_domain_service=self.business_domain_service,
            business_id=self.business_id,
            user_id=self.user_id,
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
        return _product_to_dto(product)


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
        # Check if user can modify products
        if not self.business_domain_service.can_modify_products(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="You don't have permission to modify products for this business",
                code="PERMISSION_DENIED",
            )

        product = self.product_repository.get_by_id(self.product_id)
        validate_entity_belongs_to_business(
            entity=product,
            business_id=self.business_id,
            entity_name="Product",
        )

        target_category_id = product.category_id
        if dto.category_id is not None:
            category = self.category_repository.get_by_id(dto.category_id)
            validate_entity_belongs_to_business(
                entity=category,
                business_id=self.business_id,
                entity_name="Category",
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
            validate_entity_belongs_to_business(
                entity=subcategory,
                business_id=self.business_id,
                entity_name="Subcategory",
            )

            # Ensure subcategory belongs to the specified category
            _validate_subcategory_belongs_to_category(subcategory, target_category_id)

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
        return _product_to_dto(product)


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
        # Check if user can modify products
        if not self.business_domain_service.can_modify_products(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="You don't have permission to delete products for this business",
                code="PERMISSION_DENIED",
            )

        product = self.product_repository.get_by_id(self.product_id)
        if not product:
            raise NotFoundError(
                detail="Product not found",
                code="PRODUCT_NOT_FOUND",
            )

        # Ensure product belongs to the business
        if not _compare_business_ids(product.business_id, self.business_id):
            logger.warning(
                f"Product {self.product_id} (business: {product.business_id}) "
                f"does not belong to business {self.business_id}"
            )
            raise NotFoundError(
                detail="Product not found",
                code="PRODUCT_NOT_FOUND",
            )

        # Delete S3 files before deleting product
        s3_service = S3Service()

        # Delete product image
        if product.image_url:
            try:
                s3_service.delete_file_safe(product.image_url)
            except Exception as e:
                logger.warning(f"Failed to delete product image from S3: {str(e)}")

        # Delete barcode image
        if product.barcode_image_url:
            try:
                s3_service.delete_file_safe(product.barcode_image_url)
            except Exception as e:
                logger.warning(f"Failed to delete barcode image from S3: {str(e)}")

        self.product_repository.delete(self.product_id)


class ScanBarcodeUseCase:
    """Use case for scanning barcode to find a product."""

    def __init__(
        self,
        product_repository: ProductRepository,
        business_id: UUID,
    ):
        self.product_repository = product_repository
        self.business_id = business_id

    def execute(self, barcode: str) -> ProductResponseDTO:
        """Scan barcode and return product information."""
        if not barcode:
            raise BadRequestError(
                detail="Barcode is required",
                code="BARCODE_REQUIRED",
            )

        product = self.product_repository.get_by_barcode(barcode, self.business_id)
        if not product:
            raise NotFoundError(
                detail=f"Product with barcode {barcode} not found",
                code="PRODUCT_NOT_FOUND",
            )

        return self._to_dto(product)

    def _to_dto(self, product: Product) -> ProductResponseDTO:
        """Convert product entity to DTO."""
        return _product_to_dto(product)


class NotifyExpiringProductsUseCase:
    """
    Use case for notifying business owners and managers about expiring/expired products.
    """

    def __init__(
        self,
        product_repository: ProductRepository,
        business_domain_service: BusinessDomainService,
        notification_domain_service: NotificationDomainService,
        product_id: UUID,
        business_id: UUID,
    ) -> None:
        """
        Initialize use case.

        Args:
            product_repository: Repository for product operations
            business_domain_service: Service for business operations
            notification_domain_service: Service for notification operations
            product_id: ID of the product to notify about
            business_id: ID of the business that owns the product
        """
        self.product_repository = product_repository
        self.business_domain_service = business_domain_service
        self.notification_domain_service = notification_domain_service
        self.product_id = product_id
        self.business_id = business_id

    def execute(self) -> None:
        """
        Execute notification using NotificationDomainService.
        """
        product = self.product_repository.get_by_id(self.product_id)
        if not product or not _compare_business_ids(product.business_id, self.business_id):
            logger.warning(f"Product {self.product_id} not found for notification")
            return

        # Calculate days until expiry
        days_until_expiry = None
        if product.expiry_date:
            delta = product.expiry_date - timezone.now()
            days_until_expiry = delta.days

        # Create notifications based on product status
        try:
            if product.is_expired:
                # Product is expired - notify about expiration
                notifications = self.notification_domain_service.notify_product_expired(
                    product_id=product.id,
                    product_name=product.name,
                    business_id=product.business_id,
                    expiry_date=product.expiry_date,
                )
                logger.info(
                    f"Created {len(notifications)} notifications for expired product {product.id}"
                )
            elif days_until_expiry is not None and days_until_expiry <= 15:
                # Product is expiring soon - notify about upcoming expiration
                notifications = self.notification_domain_service.notify_product_expiring(
                    product_id=product.id,
                    product_name=product.name,
                    business_id=product.business_id,
                    expiry_date=product.expiry_date,
                    days_until_expiry=days_until_expiry,
                )
                logger.info(
                    f"Created {len(notifications)} notifications for expiring product {product.id}"
                )
            else:
                logger.debug(
                    f"Product {product.id} expiry is more than 15 days away, skipping notification"
                )
        except Exception as e:
            logger.error(
                f"Failed to create notifications for product {product.id}: {str(e)}",
                exc_info=True,
            )


class GenerateInventoryReportUseCase:
    """
    Use case for generating inventory report.

    Inventory Report = État actuel de l'inventaire (snapshot)
    - Liste de tous les produits avec quantités actuelles
    - Valeur totale de l'inventaire
    - Produits en rupture de stock
    - Produits expirés
    - Produits en promotion
    """

    def __init__(
        self,
        product_repository: ProductRepository,
        stock_movement_repository: StockMovementRepository,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> None:
        """Initialize use case."""
        self.product_repository = product_repository
        self.stock_movement_repository = stock_movement_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id
        self.start_date = start_date
        self.end_date = end_date

    @transaction.atomic
    def execute(self) -> InventoryReportDTO:
        """Execute inventory report generation."""
        # Validate user access
        validate_business_access(
            business_domain_service=self.business_domain_service,
            business_id=self.business_id,
            user_id=self.user_id,
        )

        # Validate and normalize date range (optional for inventory report)
        period_start = None
        period_end = None
        if self.start_date or self.end_date:
            try:
                period_start, period_end = DateRangeValidationService.validate_date_range(
                    start_date=self.start_date,
                    end_date=self.end_date,
                    allow_future=False,
                )
            except ValueError as e:
                raise BadRequestError(
                    detail=f"Invalid date range: {str(e)}",
                    code="INVALID_DATE_RANGE",
                ) from e

        # Get all products for the business (current state)
        products = self.product_repository.get_by_business(business_id=self.business_id)

        # Calculate inventory metrics
        total_products = len(products)
        total_inventory_value = Decimal("0.00")
        low_stock_products = 0
        expired_products = 0
        products_on_promotion = 0
        product_stock_infos: list[ProductStockInfoDTO] = []

        for product in products:
            # Calculate product value
            product_value = Decimal(str(product.quantity)) * product.get_current_price()
            total_inventory_value += product_value

            # Count metrics
            if product.is_low_stock():
                low_stock_products += 1
            if product.is_expired:
                expired_products += 1
            if product.on_promotion:
                products_on_promotion += 1

            # Create product stock info
            product_stock_infos.append(
                ProductStockInfoDTO(
                    product_id=product.id,
                    product_name=product.name,
                    current_quantity=product.quantity,
                    min_quantity=product.min_quantity,
                    unit_price=product.get_current_price(),
                    total_value=product_value,
                    is_low_stock=product.is_low_stock(),
                    is_expired=product.is_expired,
                    expiry_date=product.expiry_date,
                )
            )

        # Get stock movements summary for the period (if dates provided)
        stock_movements_summary: list[StockMovementSummaryDTO] = []
        if period_start and period_end:
            movements = self.stock_movement_repository.get_by_business_period(
                business_id=self.business_id,
                start_date=period_start,
                end_date=period_end,
            )

            # Group by movement type
            movements_by_type: dict[str, dict[str, Any]] = {}
            for movement in movements:
                movement_type = movement.movement_type.value
                if movement_type not in movements_by_type:
                    movements_by_type[movement_type] = {
                        "total_quantity": 0,
                        "number_of_movements": 0,
                        "products_affected": set(),
                    }
                movements_by_type[movement_type]["total_quantity"] += movement.quantity
                movements_by_type[movement_type]["number_of_movements"] += 1
                movements_by_type[movement_type]["products_affected"].add(movement.product_id)

            # Convert to DTOs
            for movement_type, data in movements_by_type.items():
                stock_movements_summary.append(
                    StockMovementSummaryDTO(
                        movement_type=movement_type,
                        total_quantity=data["total_quantity"],
                        number_of_movements=data["number_of_movements"],
                        products_affected=len(data["products_affected"]),
                    )
                )

        return InventoryReportDTO(
            business_id=self.business_id,
            period_start=period_start,
            period_end=period_end,
            total_products=total_products,
            total_inventory_value=total_inventory_value,
            low_stock_products=low_stock_products,
            expired_products=expired_products,
            products_on_promotion=products_on_promotion,
            products=product_stock_infos,
            stock_movements_summary=stock_movements_summary,
            generated_at=timezone.now(),
        )


class GenerateStockReportUseCase:
    """
    Use case for generating stock report.

    Stock Report = Mouvements de stock sur une période (historique)
    - Entrées de stock (ENTRY)
    - Sorties de stock (EXIT)
    - Ajustements (ADJUSTMENT)
    - Mouvements nets
    - Historique des mouvements
    """

    def __init__(
        self,
        product_repository: ProductRepository,
        stock_movement_repository: StockMovementRepository,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> None:
        """Initialize use case."""
        self.product_repository = product_repository
        self.stock_movement_repository = stock_movement_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id
        self.start_date = start_date
        self.end_date = end_date

    @transaction.atomic
    def execute(self) -> StockReportDTO:
        """Execute stock report generation."""
        # Validate user access
        validate_business_access(
            business_domain_service=self.business_domain_service,
            business_id=self.business_id,
            user_id=self.user_id,
        )

        # Validate and normalize date range (required for stock report)
        try:
            start_date, end_date = DateRangeValidationService.validate_date_range(
                start_date=self.start_date,
                end_date=self.end_date,
                allow_future=False,
            )
        except ValueError as e:
            raise BadRequestError(
                detail=f"Invalid date range: {str(e)}",
                code="INVALID_DATE_RANGE",
            ) from e

        # Get stock movements for the period
        movements = self.stock_movement_repository.get_by_business_period(
            business_id=self.business_id,
            start_date=start_date,
            end_date=end_date,
        )

        # Calculate movement metrics
        stock_movements_in = 0
        stock_movements_out = 0
        movements_by_type: dict[str, dict[str, Any]] = {}

        for movement in movements:
            movement_type = movement.movement_type.value

            if movement_type == StockMovementType.ENTRY.value:
                stock_movements_in += movement.quantity
            elif movement_type == StockMovementType.EXIT.value:
                stock_movements_out += movement.quantity

            if movement_type not in movements_by_type:
                movements_by_type[movement_type] = {
                    "total_quantity": 0,
                    "number_of_movements": 0,
                    "products_affected": set(),
                }
            movements_by_type[movement_type]["total_quantity"] += movement.quantity
            movements_by_type[movement_type]["number_of_movements"] += 1
            movements_by_type[movement_type]["products_affected"].add(movement.product_id)

        net_stock_change = stock_movements_in - stock_movements_out

        # Get current stock value
        products = self.product_repository.get_by_business(business_id=self.business_id)
        current_stock_value = sum(
            Decimal(str(p.quantity)) * p.get_current_price() for p in products
        )

        # Group products by stock level
        products_by_stock_level: dict[str, list[ProductStockInfoDTO]] = {
            "low": [],
            "normal": [],
            "high": [],
        }

        for product in products:
            product_value = Decimal(str(product.quantity)) * product.get_current_price()
            product_info = ProductStockInfoDTO(
                product_id=product.id,
                product_name=product.name,
                current_quantity=product.quantity,
                min_quantity=product.min_quantity,
                unit_price=product.get_current_price(),
                total_value=product_value,
                is_low_stock=product.is_low_stock(),
                is_expired=product.is_expired,
                expiry_date=product.expiry_date,
            )

            if product.is_low_stock():
                products_by_stock_level["low"].append(product_info)
            elif product.quantity > product.min_quantity * 2:
                products_by_stock_level["high"].append(product_info)
            else:
                products_by_stock_level["normal"].append(product_info)

        # Convert movements summary to DTOs
        stock_movements_by_type: list[StockMovementSummaryDTO] = []
        for movement_type, data in movements_by_type.items():
            stock_movements_by_type.append(
                StockMovementSummaryDTO(
                    movement_type=movement_type,
                    total_quantity=data["total_quantity"],
                    number_of_movements=data["number_of_movements"],
                    products_affected=len(data["products_affected"]),
                )
            )

        return StockReportDTO(
            business_id=self.business_id,
            period_start=start_date,
            period_end=end_date,
            current_stock_value=current_stock_value,
            stock_movements_in=stock_movements_in,
            stock_movements_out=stock_movements_out,
            net_stock_change=net_stock_change,
            products_by_stock_level=products_by_stock_level,
            stock_movements_by_type=stock_movements_by_type,
            generated_at=timezone.now(),
        )
