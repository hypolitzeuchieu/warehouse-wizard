"""Inventory domain entities."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID


class StockMovementType(str, Enum):
    """Stock movement type enumeration."""

    ENTRY = "ENTRY"
    EXIT = "EXIT"
    ADJUSTMENT = "ADJUSTMENT"


@dataclass
class Category:
    """Product category entity."""

    id: UUID
    business_id: UUID
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None

    def __post_init__(self) -> None:
        """Validate category data."""
        if not self.name:
            raise ValueError("Category name is required")


@dataclass
class SubCategory:
    """Product subcategory entity."""

    id: UUID
    business_id: UUID
    category_id: UUID
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None

    def __post_init__(self) -> None:
        """Validate subcategory data."""
        if not self.name:
            raise ValueError("Subcategory name is required")


@dataclass
class Product:
    """Product entity."""

    id: UUID
    business_id: UUID
    name: str
    description: Optional[str]
    barcode: Optional[str]  # Barcode only, no QR code for products
    barcode_image_url: Optional[str]
    category_id: UUID
    subcategory_id: Optional[UUID]
    purchase_price: Decimal
    unit_price: Decimal
    image_url: Optional[str]
    quantity: int
    min_quantity: int
    expiry_date: Optional[datetime]
    is_expired: bool
    on_promotion: bool
    promotion_start_date: Optional[datetime]
    promotion_end_date: Optional[datetime]
    promo_price: Optional[Decimal]
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None

    def get_current_price(self) -> Decimal:
        """Get current price (promo price if on promotion, else unit price)."""
        if self.on_promotion and self.promo_price is not None:
            return self.promo_price
        return self.unit_price

    def is_low_stock(self) -> bool:
        """Check if product is low in stock."""
        return self.quantity <= self.min_quantity

    def check_expiry(self) -> bool:
        """Check if product is expired."""
        if self.expiry_date:
            return datetime.utcnow() > self.expiry_date
        return False


@dataclass
class StockMovement:
    """Stock movement entity."""

    id: UUID
    business_id: UUID
    product_id: UUID
    movement_type: StockMovementType
    quantity: int
    reason: Optional[str]
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        """Validate stock movement data."""
        if self.quantity == 0:
            raise ValueError("Stock movement quantity cannot be zero")
        if self.movement_type == StockMovementType.EXIT and self.quantity > 0:
            # Exit movements should have negative quantity
            self.quantity = -abs(self.quantity)

