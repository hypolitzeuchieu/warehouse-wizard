"""Inventory domain repositories (interfaces)."""

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from domain.inventory.entities import (
    Category,
    Product,
    StockMovement,
    StockMovementType,
    SubCategory,
)


class CategoryRepository(ABC):
    """Category repository interface."""

    @abstractmethod
    def get_by_id(self, category_id: UUID) -> Optional[Category]:
        """Get category by ID."""
        pass

    @abstractmethod
    def get_by_business(self, business_id: UUID) -> list[Category]:
        """Get all categories for a business."""
        pass

    @abstractmethod
    def create(self, category: Category) -> Category:
        """Create a new category."""
        pass

    @abstractmethod
    def update(self, category: Category) -> Category:
        """Update an existing category."""
        pass

    @abstractmethod
    def delete(self, category_id: UUID) -> None:
        """Delete a category."""
        pass


class SubCategoryRepository(ABC):
    """SubCategory repository interface."""

    @abstractmethod
    def get_by_id(self, subcategory_id: UUID) -> Optional[SubCategory]:
        """Get subcategory by ID."""
        pass

    @abstractmethod
    def get_by_category(self, category_id: UUID) -> list[SubCategory]:
        """Get all subcategories for a category."""
        pass

    @abstractmethod
    def create(self, subcategory: SubCategory) -> SubCategory:
        """Create a new subcategory."""
        pass

    @abstractmethod
    def update(self, subcategory: SubCategory) -> SubCategory:
        """Update an existing subcategory."""
        pass

    @abstractmethod
    def delete(self, subcategory_id: UUID) -> None:
        """Delete a subcategory."""
        pass


class ProductRepository(ABC):
    """Product repository interface."""

    @abstractmethod
    def get_by_id(self, product_id: UUID) -> Optional[Product]:
        """Get product by ID."""
        pass

    @abstractmethod
    def get_by_barcode(self, barcode: str, business_id: UUID) -> Optional[Product]:
        """Get product by barcode."""
        pass

    @abstractmethod
    def get_by_business(
        self,
        business_id: UUID,
        category_id: Optional[UUID] = None,
        low_stock_only: bool = False,
        expired_only: bool = False,
    ) -> list[Product]:
        """Get products for a business with optional filters."""
        pass

    @abstractmethod
    def create(self, product: Product) -> Product:
        """Create a new product."""
        pass

    @abstractmethod
    def update(self, product: Product) -> Product:
        """Update an existing product."""
        pass

    @abstractmethod
    def delete(self, product_id: UUID) -> None:
        """Delete a product."""
        pass

    @abstractmethod
    def update_quantity(self, product_id: UUID, quantity: int) -> None:
        """Update product quantity."""
        pass


class StockMovementRepository(ABC):
    """Stock movement repository interface."""

    @abstractmethod
    def get_by_id(self, movement_id: UUID) -> Optional[StockMovement]:
        """Get stock movement by ID."""
        pass

    @abstractmethod
    def get_by_product(
        self, product_id: UUID, limit: int = 100
    ) -> list[StockMovement]:
        """Get stock movements for a product."""
        pass

    @abstractmethod
    def get_by_business(
        self,
        business_id: UUID,
        movement_type: Optional[StockMovementType] = None,
        limit: int = 100,
    ) -> list[StockMovement]:
        """Get stock movements for a business."""
        pass

    @abstractmethod
    def create(self, movement: StockMovement) -> StockMovement:
        """Create a new stock movement."""
        pass

