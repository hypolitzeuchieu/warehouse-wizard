"""Inventory domain Django models."""

from __future__ import annotations

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from infrastructure.persistence.models.base_model import BaseModel
from infrastructure.persistence.models.business_models import Business
from infrastructure.persistence.models.user_models import RetailPulseUser


class Category(BaseModel):
    """Product category model."""

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(
        RetailPulseUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_categories",
    )

    class Meta:
        db_table = "categories"
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        constraints = [
            models.UniqueConstraint(
                fields=["business", "name"],
                name="uniq_category_business_name",
            ),
        ]
        indexes = [
            models.Index(fields=["business", "name"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.business.name})"


class SubCategory(BaseModel):
    """Product subcategory model."""

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="subcategories")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="subcategories")
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(
        RetailPulseUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_subcategories",
    )

    class Meta:
        db_table = "subcategories"
        verbose_name = "SubCategory"
        verbose_name_plural = "SubCategories"
        constraints = [
            models.UniqueConstraint(
                fields=["category", "name"],
                name="uniq_subcategory_per_category",
            ),
        ]
        indexes = [
            models.Index(fields=["business", "category"]),
        ]

    def __str__(self) -> str:
        return f"{self.category.name} - {self.name}"


class Product(BaseModel):
    """Product model."""

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    barcode = models.CharField(
        max_length=100, null=True, blank=True, unique=True
    )  # Barcode only, no QR code
    barcode_image_url = models.URLField(max_length=500, null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="products")
    subcategory = models.ForeignKey(
        SubCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    purchase_price = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))
    unit_price = models.DecimalField(
        max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    image_url = models.URLField(max_length=500, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=0)
    min_quantity = models.PositiveIntegerField(default=10)
    expiry_date = models.DateTimeField(null=True, blank=True)
    is_expired = models.BooleanField(default=False)
    on_promotion = models.BooleanField(default=False)
    promotion_start_date = models.DateTimeField(null=True, blank=True)
    promotion_end_date = models.DateTimeField(null=True, blank=True)
    promo_price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    created_by = models.ForeignKey(
        RetailPulseUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_products",
    )

    class Meta:
        db_table = "products"
        verbose_name = "Product"
        verbose_name_plural = "Products"
        constraints = [
            models.UniqueConstraint(
                fields=["business", "category", "name"],
                name="uniq_product_category_name_when_no_subcategory",
                condition=Q(subcategory__isnull=True),
            ),
            models.UniqueConstraint(
                fields=["business", "subcategory", "name"],
                name="uniq_product_subcategory_name",
                condition=Q(subcategory__isnull=False),
            ),
        ]
        indexes = [
            models.Index(fields=["business", "name"]),
            models.Index(fields=["barcode"]),
            models.Index(fields=["category"]),
            models.Index(fields=["is_expired"]),
            models.Index(fields=["quantity"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.business.name})"

    def get_current_price(self) -> Decimal:
        """Get current price (promo price if on promotion, else unit price)."""
        if self.on_promotion and self.promo_price is not None:
            return self.promo_price
        return self.unit_price

    def is_low_stock(self) -> bool:
        """Check if product is low in stock."""
        return self.quantity <= self.min_quantity


class StockMovement(BaseModel):
    """Stock movement model."""

    MOVEMENT_TYPES = [
        ("ENTRY", "Entry"),
        ("EXIT", "Exit"),
        ("ADJUSTMENT", "Adjustment"),
    ]
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="stock_movements")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="stock_movements")
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField()
    reason = models.TextField(null=True, blank=True)
    user = models.ForeignKey(
        RetailPulseUser, on_delete=models.CASCADE, related_name="stock_movements"
    )

    class Meta:
        db_table = "stock_movements"
        verbose_name = "Stock Movement"
        verbose_name_plural = "Stock Movements"
        indexes = [
            models.Index(fields=["business", "-updated_at"]),
            models.Index(fields=["product", "-updated_at"]),
            models.Index(fields=["movement_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.movement_type} - {self.product.name} ({self.quantity})"
