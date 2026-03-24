"""Inventory domain services."""

from __future__ import annotations

import logging
from datetime import timedelta
from uuid import UUID, uuid4

from django.db import transaction
from django.utils import timezone

from domain.inventory.entities import Product, StockMovement, StockMovementType
from domain.inventory.repositories import (
    ProductRepository,
    StockMovementRepository,
)

logger = logging.getLogger(__name__)


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

    @transaction.atomic
    def record_stock_entry(
        self,
        business_id: UUID,
        product_id: UUID,
        quantity: int,
        user_id: UUID,
        reason: str | None = None,
    ) -> StockMovement:
        """Record a stock entry (incoming stock)."""
        product = self.product_repository.get_by_id_for_update(product_id)
        if not product:
            raise ValueError(f"Product {product_id} not found")

        product.quantity += quantity
        product.updated_at = timezone.now()
        product = self.product_repository.update(product)

        now = timezone.now()
        movement = StockMovement(
            id=uuid4(),
            business_id=business_id,
            product_id=product_id,
            movement_type=StockMovementType.ENTRY,
            quantity=quantity,
            reason=reason,
            user_id=user_id,
            created_at=now,
            updated_at=now,
        )

        return self.stock_movement_repository.create(movement)

    @transaction.atomic
    def record_stock_exit(
        self,
        business_id: UUID,
        product_id: UUID,
        quantity: int,
        user_id: UUID,
        reason: str | None = None,
    ) -> StockMovement:
        """Record a stock exit (outgoing stock)."""
        product = self.product_repository.get_by_id_for_update(product_id)
        if not product:
            raise ValueError(f"Product {product_id} not found")

        if product.quantity < quantity:
            raise ValueError(
                f"Insufficient stock. Available: {product.quantity}, Requested: {quantity}"
            )

        product.quantity -= quantity
        product.updated_at = timezone.now()
        product = self.product_repository.update(product)

        now = timezone.now()
        movement = StockMovement(
            id=uuid4(),
            business_id=business_id,
            product_id=product_id,
            movement_type=StockMovementType.EXIT,
            quantity=quantity,
            reason=reason,
            user_id=user_id,
            created_at=now,
            updated_at=now,
        )

        return self.stock_movement_repository.create(movement)

    def get_low_stock_products(self, business_id: UUID) -> list[Product]:
        """Get all products with low stock for a business."""
        products = self.product_repository.get_by_business(
            business_id=business_id,
            low_stock_only=True,
        )
        return [p for p in products if p.is_low_stock()]

    def check_expired_products(self, business_id: UUID) -> list[Product]:
        """Check and mark expired products for a business."""
        products = self.product_repository.get_by_business(business_id=business_id)
        expired_products = []

        for product in products:
            if product.expiry_date and product.check_expiry():
                if not product.is_expired:
                    product.is_expired = True
                    product.updated_at = timezone.now()
                    product = self.product_repository.update(product)
                expired_products.append(product)
            elif product.is_expired and product.expiry_date:
                # Product was marked as expired but is no longer expired (date changed)
                if not product.check_expiry():
                    product.is_expired = False
                    product.updated_at = timezone.now()
                    product = self.product_repository.update(product)

        return expired_products

    def get_products_near_expiry(self, business_id: UUID, days_ahead: int = 7) -> list[Product]:
        """Get products that will expire within the specified number of days."""
        products = self.product_repository.get_by_business(business_id=business_id)
        threshold_date = timezone.now() + timedelta(days=days_ahead)
        near_expiry = []

        for product in products:
            if (
                product.expiry_date
                and not product.is_expired
                and product.expiry_date <= threshold_date
            ):
                near_expiry.append(product)

        return near_expiry
