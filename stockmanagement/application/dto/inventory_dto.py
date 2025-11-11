"""Inventory DTOs."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID


@dataclass
class CategoryCreateDTO:
    """DTO for creating a category."""

    name: str
    description: Optional[str] = None


@dataclass
class CategoryUpdateDTO:
    """DTO for updating a category."""

    name: Optional[str] = None
    description: Optional[str] = None


@dataclass
class CategoryResponseDTO:
    """DTO for category response."""

    id: UUID
    business_id: UUID
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime


@dataclass
class SubCategoryCreateDTO:
    """DTO for creating a subcategory."""

    category_id: UUID
    name: str
    description: Optional[str] = None


@dataclass
class SubCategoryUpdateDTO:
    """DTO for updating a subcategory."""

    name: Optional[str] = None
    description: Optional[str] = None


@dataclass
class SubCategoryResponseDTO:
    """DTO for subcategory response."""

    id: UUID
    business_id: UUID
    category_id: UUID
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime


@dataclass
class ProductCreateDTO:
    """DTO for creating a product."""

    name: str
    category_id: UUID
    purchase_price: Decimal
    unit_price: Decimal
    description: Optional[str] = None
    barcode: Optional[str] = None
    subcategory_id: Optional[UUID] = None
    image_url: Optional[str] = None
    quantity: int = 0
    min_quantity: int = 10
    expiry_date: Optional[datetime] = None


@dataclass
class ProductUpdateDTO:
    """DTO for updating a product."""

    name: Optional[str] = None
    description: Optional[str] = None
    barcode: Optional[str] = None
    category_id: Optional[UUID] = None
    subcategory_id: Optional[UUID] = None
    purchase_price: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    image_url: Optional[str] = None
    quantity: Optional[int] = None
    min_quantity: Optional[int] = None
    expiry_date: Optional[datetime] = None


@dataclass
class ProductResponseDTO:
    """DTO for product response."""

    id: UUID
    business_id: UUID
    name: str
    description: Optional[str]
    barcode: Optional[str]
    barcode_image_url: Optional[str]
    category_id: UUID
    subcategory_id: Optional[UUID]
    purchase_price: Decimal
    unit_price: Decimal
    current_price: Decimal
    image_url: Optional[str]
    quantity: int
    min_quantity: int
    is_low_stock: bool
    expiry_date: Optional[datetime]
    is_expired: bool
    on_promotion: bool
    promotion_start_date: Optional[datetime]
    promotion_end_date: Optional[datetime]
    promo_price: Optional[Decimal]
    created_at: datetime
    updated_at: datetime


@dataclass
class StockMovementCreateDTO:
    """DTO for creating a stock movement."""

    product_id: UUID
    movement_type: str  # ENTRY, EXIT, ADJUSTMENT
    quantity: int
    reason: Optional[str] = None


@dataclass
class StockMovementResponseDTO:
    """DTO for stock movement response."""

    id: UUID
    business_id: UUID
    product_id: UUID
    movement_type: str
    quantity: int
    user_id: UUID
    created_at: datetime
    product_name: Optional[str] = None
    reason: Optional[str] = None
    user_name: Optional[str] = None

