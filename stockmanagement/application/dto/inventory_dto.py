"""Inventory DTOs."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass
class CategoryCreateDTO:
    """DTO for creating a category."""

    name: str
    description: str | None = None


@dataclass
class CategoryUpdateDTO:
    """DTO for updating a category."""

    name: str | None = None
    description: str | None = None


@dataclass
class CategoryResponseDTO:
    """DTO for category response."""

    id: UUID
    business_id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


@dataclass
class SubCategoryCreateDTO:
    """DTO for creating a subcategory."""

    category_id: UUID
    name: str
    description: str | None = None


@dataclass
class SubCategoryUpdateDTO:
    """DTO for updating a subcategory."""

    name: str | None = None
    description: str | None = None


@dataclass
class SubCategoryResponseDTO:
    """DTO for subcategory response."""

    id: UUID
    business_id: UUID
    category_id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


@dataclass
class ProductCreateDTO:
    """DTO for creating a product."""

    name: str
    category_id: UUID
    purchase_price: Decimal
    unit_price: Decimal
    description: str | None = None
    barcode: str | None = None
    subcategory_id: UUID | None = None
    image_url: str | None = None
    quantity: int = 0
    min_quantity: int = 10
    expiry_date: datetime | None = None
    on_promotion: bool = False
    promotion_start_date: datetime | None = None
    promotion_end_date: datetime | None = None
    promo_price: Decimal | None = None


@dataclass
class ProductUpdateDTO:
    """DTO for updating a product."""

    name: str | None = None
    description: str | None = None
    barcode: str | None = None
    category_id: UUID | None = None
    subcategory_id: UUID | None = None
    purchase_price: Decimal | None = None
    unit_price: Decimal | None = None
    image_url: str | None = None
    quantity: int | None = None
    min_quantity: int | None = None
    expiry_date: datetime | None = None
    subcategory_id_provided: bool = False


@dataclass
class ProductResponseDTO:
    """DTO for product response."""

    id: UUID
    business_id: UUID
    name: str
    description: str | None
    barcode: str | None
    barcode_image_url: str | None
    category_id: UUID
    subcategory_id: UUID | None
    purchase_price: Decimal
    unit_price: Decimal
    current_price: Decimal
    image_url: str | None
    quantity: int
    min_quantity: int
    is_low_stock: bool
    expiry_date: datetime | None
    is_expired: bool
    on_promotion: bool
    promotion_start_date: datetime | None
    promotion_end_date: datetime | None
    promo_price: Decimal | None
    created_at: datetime
    updated_at: datetime


@dataclass
class StockMovementCreateDTO:
    """DTO for creating a stock movement."""

    product_id: UUID
    movement_type: str  # ENTRY, EXIT, ADJUSTMENT
    quantity: int
    reason: str | None = None


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
    product_name: str | None = None
    reason: str | None = None
    user_name: str | None = None


@dataclass
class ProductStockInfoDTO:
    """DTO for product stock information in reports."""

    product_id: UUID
    product_name: str
    current_quantity: int
    min_quantity: int
    unit_price: Decimal
    total_value: Decimal
    is_low_stock: bool
    is_expired: bool
    expiry_date: datetime | None


@dataclass
class StockMovementSummaryDTO:
    """DTO for stock movement summary."""

    movement_type: str
    total_quantity: int
    number_of_movements: int
    products_affected: int


@dataclass
class InventoryReportDTO:
    """DTO for inventory report."""

    business_id: UUID
    period_start: datetime | None
    period_end: datetime | None
    total_products: int
    total_inventory_value: Decimal
    low_stock_products: int
    expired_products: int
    products_on_promotion: int
    products: list[ProductStockInfoDTO]
    stock_movements_summary: list[StockMovementSummaryDTO]
    generated_at: datetime


@dataclass
class StockReportDTO:
    """DTO for stock report."""

    business_id: UUID
    period_start: datetime
    period_end: datetime
    current_stock_value: Decimal
    stock_movements_in: int
    stock_movements_out: int
    net_stock_change: int
    products_by_stock_level: dict[str, list[ProductStockInfoDTO]]
    stock_movements_by_type: list[StockMovementSummaryDTO]
    generated_at: datetime
