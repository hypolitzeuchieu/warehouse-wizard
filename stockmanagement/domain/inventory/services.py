"""Inventory domain services."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from domain.inventory.entities import Product, StockMovement, StockMovementType
from domain.inventory.repositories import (
    ProductRepository,
    StockMovementRepository,
)


class InventoryDomainService:
    """Inventory domain service."""

    def __init__(
        self,
        product_repository: ProductRepository,
        stock_movement_repository: StockMovementRepository,
    ) -> None:
        """Initialize inventory domain service."""
        self.product_repository = product_repository
        self.stock_movement_repository = stock_movement_repository

    def record_stock_entry(
        self,
        business_id: UUID,
        product_id: UUID,
        quantity: int,
        user_id: UUID,
        reason: Optional[str] = None,
    ) -> StockMovement:
        """Record a stock entry."""
        movement = StockMovement(
            id=uuid4(),
            business_id=business_id,
            product_id=product_id,
            movement_type=StockMovementType.ENTRY,
            quantity=abs(quantity),
            reason=reason,
            user_id=user_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        movement = self.stock_movement_repository.create(movement)

        # Update product quantity
        product = self.product_repository.get_by_id(product_id)
        if product:
            new_quantity = product.quantity + abs(quantity)
            self.product_repository.update_quantity(product_id, new_quantity)

        return movement

    def record_stock_exit(
        self,
        business_id: UUID,
        product_id: UUID,
        quantity: int,
        user_id: UUID,
        reason: Optional[str] = None,
    ) -> StockMovement:
        """Record a stock exit."""
        product = self.product_repository.get_by_id(product_id)
        if not product:
            raise ValueError("Product not found")

        if product.quantity < abs(quantity):
            raise ValueError("Insufficient stock")

        movement = StockMovement(
            id=uuid4(),
            business_id=business_id,
            product_id=product_id,
            movement_type=StockMovementType.EXIT,
            quantity=-abs(quantity),
            reason=reason,
            user_id=user_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        movement = self.stock_movement_repository.create(movement)

        # Update product quantity
        new_quantity = product.quantity - abs(quantity)
        self.product_repository.update_quantity(product_id, new_quantity)

        return movement

    def check_expired_products(
        self, business_id: UUID
    ) -> list[Product]:
        """Check and mark expired products."""
        products = self.product_repository.get_by_business(
            business_id, expired_only=False
        )
        expired_products = []

        for product in products:
            if product.expiry_date and product.check_expiry():
                if not product.is_expired:
                    product.is_expired = True
                    self.product_repository.update(product)
                expired_products.append(product)

        return expired_products

    def get_low_stock_products(
        self, business_id: UUID
    ) -> list[Product]:
        """Get products with low stock."""
        products = self.product_repository.get_by_business(
            business_id, low_stock_only=True
        )
        return [p for p in products if p.is_low_stock()]

