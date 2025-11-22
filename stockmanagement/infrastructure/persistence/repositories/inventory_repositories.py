"""Inventory repository implementations."""

from datetime import datetime
from uuid import UUID

from django.db.models import F

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
from infrastructure.persistence.models.inventory_models import (
    Category as CategoryModel,
)
from infrastructure.persistence.models.inventory_models import (
    Product as ProductModel,
)
from infrastructure.persistence.models.inventory_models import (
    StockMovement as StockMovementModel,
)
from infrastructure.persistence.models.inventory_models import (
    SubCategory as SubCategoryModel,
)


class CategoryRepositoryImpl(CategoryRepository):
    """Django implementation of CategoryRepository."""

    def get_by_id(self, category_id: UUID) -> Category | None:
        """Get category by ID."""
        try:
            category_model = CategoryModel.objects.select_related("business").get(id=category_id)
            return self._to_entity(category_model)
        except CategoryModel.DoesNotExist:
            return None

    def get_by_business(self, business_id: UUID) -> list[Category]:
        """Get all categories for a business."""
        categories = CategoryModel.objects.filter(business_id=business_id).select_related(
            "business"
        )
        return [self._to_entity(category) for category in categories]

    def get_by_name(self, business_id: UUID, name: str) -> Category | None:
        """Get category by name within a business."""
        try:
            category_model = CategoryModel.objects.get(business_id=business_id, name=name)
            return self._to_entity(category_model)
        except CategoryModel.DoesNotExist:
            return None

    def create(self, category: Category) -> Category:
        """Create a new category."""
        category_model = CategoryModel(
            id=category.id,
            business_id=category.business_id,
            name=category.name,
            description=category.description,
            created_by_id=category.created_by,
        )
        category_model.save()
        return self._to_entity(category_model)

    def update(self, category: Category) -> Category:
        """Update an existing category."""
        category_model = CategoryModel.objects.get(id=category.id)
        category_model.name = category.name
        category_model.description = category.description
        category_model.save()
        return self._to_entity(category_model)

    def delete(self, category_id: UUID) -> None:
        """Delete a category."""
        CategoryModel.objects.filter(id=category_id).delete()

    def _to_entity(self, category_model: CategoryModel) -> Category:
        """Convert Django model to domain entity."""
        return Category(
            id=category_model.id,
            business_id=category_model.business_id,
            name=category_model.name,
            description=category_model.description,
            created_at=category_model.created_at,
            updated_at=category_model.updated_at,
            created_by=category_model.created_by_id,
        )


class SubCategoryRepositoryImpl(SubCategoryRepository):
    """Django implementation of SubCategoryRepository."""

    def get_by_id(self, subcategory_id: UUID) -> SubCategory | None:
        """Get subcategory by ID."""
        try:
            subcategory_model = SubCategoryModel.objects.select_related("category", "business").get(
                id=subcategory_id
            )
            return self._to_entity(subcategory_model)
        except SubCategoryModel.DoesNotExist:
            return None

    def get_by_category(self, category_id: UUID) -> list[SubCategory]:
        """Get all subcategories for a category."""
        subcategories = SubCategoryModel.objects.filter(category_id=category_id).select_related(
            "category"
        )
        return [self._to_entity(sub) for sub in subcategories]

    def get_by_name(self, category_id: UUID, name: str) -> SubCategory | None:
        """Get subcategory by name within a category."""
        try:
            subcategory_model = SubCategoryModel.objects.get(category_id=category_id, name=name)
            return self._to_entity(subcategory_model)
        except SubCategoryModel.DoesNotExist:
            return None

    def create(self, subcategory: SubCategory) -> SubCategory:
        """Create a new subcategory."""
        subcategory_model = SubCategoryModel(
            id=subcategory.id,
            business_id=subcategory.business_id,
            category_id=subcategory.category_id,
            name=subcategory.name,
            description=subcategory.description,
            created_by_id=subcategory.created_by,
        )
        subcategory_model.save()
        return self._to_entity(subcategory_model)

    def update(self, subcategory: SubCategory) -> SubCategory:
        """Update an existing subcategory."""
        subcategory_model = SubCategoryModel.objects.get(id=subcategory.id)
        subcategory_model.name = subcategory.name
        subcategory_model.description = subcategory.description
        subcategory_model.save()
        return self._to_entity(subcategory_model)

    def delete(self, subcategory_id: UUID) -> None:
        """Delete a subcategory."""
        SubCategoryModel.objects.filter(id=subcategory_id).delete()

    def _to_entity(self, subcategory_model: SubCategoryModel) -> SubCategory:
        """Convert Django model to domain entity."""
        return SubCategory(
            id=subcategory_model.id,
            business_id=subcategory_model.business_id,
            category_id=subcategory_model.category_id,
            name=subcategory_model.name,
            description=subcategory_model.description,
            created_at=subcategory_model.created_at,
            updated_at=subcategory_model.updated_at,
            created_by=subcategory_model.created_by_id,
        )


class ProductRepositoryImpl(ProductRepository):
    """Django implementation of ProductRepository."""

    def get_by_id(self, product_id: UUID) -> Product | None:
        """Get product by ID."""
        try:
            product_model = ProductModel.objects.select_related(
                "business", "category", "subcategory"
            ).get(id=product_id)
            return self._to_entity(product_model)
        except ProductModel.DoesNotExist:
            return None

    def get_by_barcode(self, barcode: str, business_id: UUID) -> Product | None:
        """Get product by barcode."""
        try:
            product_model = ProductModel.objects.select_related("business", "category").get(
                barcode=barcode, business_id=business_id
            )
            return self._to_entity(product_model)
        except ProductModel.DoesNotExist:
            return None

    def barcode_exists_globally(self, barcode: str) -> bool:
        """Check if barcode exists globally (across all businesses)."""
        return ProductModel.objects.filter(barcode=barcode).exists()

    def get_by_business(
        self,
        business_id: UUID,
        category_id: UUID | None = None,
        subcategory_id: UUID | None = None,
        low_stock_only: bool = False,
        expired_only: bool = False,
    ) -> list[Product]:
        """Get products for a business with optional filters."""
        query = ProductModel.objects.filter(business_id=business_id).select_related(
            "category", "subcategory"
        )

        if category_id:
            query = query.filter(category_id=category_id)
        if subcategory_id is not None:
            if subcategory_id:
                query = query.filter(subcategory_id=subcategory_id)
            else:
                query = query.filter(subcategory__isnull=True)

        if low_stock_only:

            query = query.filter(quantity__lte=F("min_quantity"))

        if expired_only:
            query = query.filter(expiry_date__lt=datetime.utcnow(), is_expired=True)

        products = query.prefetch_related("stock_movements")
        return [self._to_entity(product) for product in products]

    def get_by_name_in_scope(
        self,
        business_id: UUID,
        category_id: UUID,
        subcategory_id: UUID | None,
        name: str,
        exclude_id: UUID | None = None,
    ) -> Product | None:
        """Get product by name within category/subcategory scope."""
        query = ProductModel.objects.filter(
            business_id=business_id,
            category_id=category_id,
            name=name,
        )
        if subcategory_id:
            query = query.filter(subcategory_id=subcategory_id)
        else:
            query = query.filter(subcategory__isnull=True)

        if exclude_id:
            query = query.exclude(id=exclude_id)

        try:
            product_model = query.get()
            return self._to_entity(product_model)
        except ProductModel.DoesNotExist:
            return None

    def create(self, product: Product) -> Product:
        """Create a new product."""
        product_model = ProductModel(
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
            image_url=product.image_url,
            quantity=product.quantity,
            min_quantity=product.min_quantity,
            expiry_date=product.expiry_date,
            is_expired=product.is_expired,
            on_promotion=product.on_promotion,
            promotion_start_date=product.promotion_start_date,
            promotion_end_date=product.promotion_end_date,
            promo_price=product.promo_price,
            created_by_id=product.created_by,
        )
        product_model.save()
        return self._to_entity(product_model)

    def update(self, product: Product) -> Product:
        """Update an existing product."""
        product_model = ProductModel.objects.get(id=product.id)
        product_model.name = product.name
        product_model.description = product.description
        product_model.barcode = product.barcode
        product_model.barcode_image_url = product.barcode_image_url
        product_model.category_id = product.category_id
        product_model.subcategory_id = product.subcategory_id
        product_model.purchase_price = product.purchase_price
        product_model.unit_price = product.unit_price
        product_model.image_url = product.image_url
        product_model.quantity = product.quantity
        product_model.min_quantity = product.min_quantity
        product_model.expiry_date = product.expiry_date
        product_model.is_expired = product.is_expired
        product_model.on_promotion = product.on_promotion
        product_model.promotion_start_date = product.promotion_start_date
        product_model.promotion_end_date = product.promotion_end_date
        product_model.promo_price = product.promo_price
        product_model.save()
        return self._to_entity(product_model)

    def delete(self, product_id: UUID) -> None:
        """Delete a product."""
        ProductModel.objects.filter(id=product_id).delete()

    def update_quantity(self, product_id: UUID, quantity: int) -> None:
        """Update product quantity."""
        ProductModel.objects.filter(id=product_id).update(quantity=quantity)

    def _to_entity(self, product_model: ProductModel) -> Product:
        """Convert Django model to domain entity."""
        return Product(
            id=product_model.id,
            business_id=product_model.business_id,
            name=product_model.name,
            description=product_model.description,
            barcode=product_model.barcode,
            barcode_image_url=product_model.barcode_image_url,
            category_id=product_model.category_id,
            subcategory_id=product_model.subcategory_id,
            purchase_price=product_model.purchase_price,
            unit_price=product_model.unit_price,
            image_url=product_model.image_url,
            quantity=product_model.quantity,
            min_quantity=product_model.min_quantity,
            expiry_date=product_model.expiry_date,
            is_expired=product_model.is_expired,
            on_promotion=product_model.on_promotion,
            promotion_start_date=product_model.promotion_start_date,
            promotion_end_date=product_model.promotion_end_date,
            promo_price=product_model.promo_price,
            created_at=product_model.created_at,
            updated_at=product_model.updated_at,
            created_by=product_model.created_by_id,
        )


class StockMovementRepositoryImpl(StockMovementRepository):
    """Django implementation of StockMovementRepository."""

    def get_by_id(self, movement_id: UUID) -> StockMovement | None:
        """Get stock movement by ID."""
        try:
            movement_model = StockMovementModel.objects.select_related(
                "product", "business", "user"
            ).get(id=movement_id)
            return self._to_entity(movement_model)
        except StockMovementModel.DoesNotExist:
            return None

    def get_by_product(self, product_id: UUID, limit: int = 100) -> list[StockMovement]:
        """Get stock movements for a product."""
        movements = (
            StockMovementModel.objects.filter(product_id=product_id)
            .select_related("product", "user")
            .order_by("-created_at")[:limit]
        )
        return [self._to_entity(movement) for movement in movements]

    def get_by_business(
        self,
        business_id: UUID,
        movement_type: StockMovementType | None = None,
        limit: int = 100,
    ) -> list[StockMovement]:
        """Get stock movements for a business."""
        query = StockMovementModel.objects.filter(business_id=business_id).select_related(
            "product", "user"
        )

        if movement_type:
            query = query.filter(movement_type=movement_type.value)

        movements = query.order_by("-created_at")[:limit]
        return [self._to_entity(movement) for movement in movements]

    def create(self, movement: StockMovement) -> StockMovement:
        """Create a new stock movement."""
        movement_model = StockMovementModel(
            id=movement.id,
            business_id=movement.business_id,
            product_id=movement.product_id,
            movement_type=movement.movement_type.value,
            quantity=movement.quantity,
            reason=movement.reason,
            user_id=movement.user_id,
        )
        movement_model.save()
        return self._to_entity(movement_model)

    def _to_entity(self, movement_model: StockMovementModel) -> StockMovement:
        """Convert Django model to domain entity."""
        return StockMovement(
            id=movement_model.id,
            business_id=movement_model.business_id,
            product_id=movement_model.product_id,
            movement_type=StockMovementType(movement_model.movement_type),
            quantity=movement_model.quantity,
            reason=movement_model.reason,
            user_id=movement_model.user_id,
            created_at=movement_model.created_at,
            updated_at=movement_model.updated_at,
        )
