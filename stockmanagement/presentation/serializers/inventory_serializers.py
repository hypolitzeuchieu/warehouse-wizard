"""Inventory serializers."""

from decimal import Decimal

from rest_framework import serializers

from application.dto.inventory_dto import (
    ProductCreateDTO,
    ProductResponseDTO,
    ProductUpdateDTO,
    StockMovementCreateDTO,
    StockMovementResponseDTO,
)


class ProductCreateSerializer(serializers.Serializer):
    """Serializer for product creation."""

    name = serializers.CharField(max_length=255, required=True)
    description = serializers.CharField(required=False, allow_blank=True)
    barcode = serializers.CharField(max_length=100, required=False, allow_blank=True)
    category_id = serializers.UUIDField(required=True)
    subcategory_id = serializers.UUIDField(required=False, allow_null=True)
    purchase_price = serializers.DecimalField(max_digits=15, decimal_places=2, required=True)
    unit_price = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=True, min_value=Decimal("0.01")
    )
    image_url = serializers.URLField(max_length=500, required=False, allow_blank=True)
    quantity = serializers.IntegerField(required=False, default=0, min_value=0)
    min_quantity = serializers.IntegerField(required=False, default=10, min_value=0)
    expiry_date = serializers.DateTimeField(required=False, allow_null=True)

    def to_dto(self) -> ProductCreateDTO:
        """Convert to DTO."""
        return ProductCreateDTO(
            name=self.validated_data["name"],
            description=self.validated_data.get("description"),
            barcode=self.validated_data.get("barcode"),
            category_id=self.validated_data["category_id"],
            subcategory_id=self.validated_data.get("subcategory_id"),
            purchase_price=self.validated_data["purchase_price"],
            unit_price=self.validated_data["unit_price"],
            image_url=self.validated_data.get("image_url"),
            quantity=self.validated_data.get("quantity", 0),
            min_quantity=self.validated_data.get("min_quantity", 10),
            expiry_date=self.validated_data.get("expiry_date"),
        )


class ProductUpdateSerializer(serializers.Serializer):
    """Serializer for product update."""

    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    barcode = serializers.CharField(max_length=100, required=False, allow_blank=True)
    category_id = serializers.UUIDField(required=False, allow_null=True)
    subcategory_id = serializers.UUIDField(required=False, allow_null=True)
    purchase_price = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    unit_price = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False, min_value=Decimal("0.01")
    )
    image_url = serializers.URLField(max_length=500, required=False, allow_blank=True)
    quantity = serializers.IntegerField(required=False, min_value=0)
    min_quantity = serializers.IntegerField(required=False, min_value=0)
    expiry_date = serializers.DateTimeField(required=False, allow_null=True)

    def to_dto(self) -> ProductUpdateDTO:
        """Convert to DTO."""
        return ProductUpdateDTO(
            name=self.validated_data.get("name"),
            description=self.validated_data.get("description"),
            barcode=self.validated_data.get("barcode"),
            category_id=self.validated_data.get("category_id"),
            subcategory_id=self.validated_data.get("subcategory_id"),
            purchase_price=self.validated_data.get("purchase_price"),
            unit_price=self.validated_data.get("unit_price"),
            image_url=self.validated_data.get("image_url"),
            quantity=self.validated_data.get("quantity"),
            min_quantity=self.validated_data.get("min_quantity"),
            expiry_date=self.validated_data.get("expiry_date"),
        )


class StockMovementCreateSerializer(serializers.Serializer):
    """Serializer for stock movement creation."""

    product_id = serializers.UUIDField(required=True)
    movement_type = serializers.ChoiceField(choices=["ENTRY", "EXIT", "ADJUSTMENT"], required=True)
    quantity = serializers.IntegerField(required=True, min_value=1)
    reason = serializers.CharField(required=False, allow_blank=True)

    def to_dto(self) -> StockMovementCreateDTO:
        """Convert to DTO."""
        return StockMovementCreateDTO(
            product_id=self.validated_data["product_id"],
            movement_type=self.validated_data["movement_type"],
            quantity=self.validated_data["quantity"],
            reason=self.validated_data.get("reason"),
        )


class ProductResponseSerializer(serializers.Serializer):
    """Serializer for product responses."""

    id = serializers.UUIDField()
    business_id = serializers.UUIDField()
    name = serializers.CharField()
    description = serializers.CharField(allow_null=True, required=False)
    barcode = serializers.CharField(allow_null=True, required=False)
    barcode_image_url = serializers.CharField(allow_null=True, required=False)
    category_id = serializers.UUIDField()
    subcategory_id = serializers.UUIDField(allow_null=True, required=False)
    purchase_price = serializers.DecimalField(max_digits=15, decimal_places=2)
    unit_price = serializers.DecimalField(max_digits=15, decimal_places=2)
    current_price = serializers.DecimalField(max_digits=15, decimal_places=2)
    image_url = serializers.CharField(allow_null=True, required=False)
    quantity = serializers.IntegerField()
    min_quantity = serializers.IntegerField()
    is_low_stock = serializers.BooleanField()
    expiry_date = serializers.DateTimeField(allow_null=True, required=False)
    is_expired = serializers.BooleanField()
    on_promotion = serializers.BooleanField()
    promotion_start_date = serializers.DateTimeField(allow_null=True, required=False)
    promotion_end_date = serializers.DateTimeField(allow_null=True, required=False)
    promo_price = serializers.DecimalField(
        max_digits=15, decimal_places=2, allow_null=True, required=False
    )
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    @classmethod
    def from_dto(cls, dto: ProductResponseDTO) -> dict:
        serializer = cls(
            data={
                "id": dto.id,
                "business_id": dto.business_id,
                "name": dto.name,
                "description": dto.description,
                "barcode": dto.barcode,
                "barcode_image_url": dto.barcode_image_url,
                "category_id": dto.category_id,
                "subcategory_id": dto.subcategory_id,
                "purchase_price": dto.purchase_price,
                "unit_price": dto.unit_price,
                "current_price": dto.current_price,
                "image_url": dto.image_url,
                "quantity": dto.quantity,
                "min_quantity": dto.min_quantity,
                "is_low_stock": dto.is_low_stock,
                "expiry_date": dto.expiry_date,
                "is_expired": dto.is_expired,
                "on_promotion": dto.on_promotion,
                "promotion_start_date": dto.promotion_start_date,
                "promotion_end_date": dto.promotion_end_date,
                "promo_price": dto.promo_price,
                "created_at": dto.created_at,
                "updated_at": dto.updated_at,
            }
        )
        serializer.is_valid(raise_exception=True)
        return serializer.data


class StockMovementResponseSerializer(serializers.Serializer):
    """Serializer for stock movement responses."""

    id = serializers.UUIDField()
    business_id = serializers.UUIDField()
    product_id = serializers.UUIDField()
    movement_type = serializers.CharField()
    quantity = serializers.IntegerField()
    user_id = serializers.UUIDField()
    created_at = serializers.DateTimeField()
    product_name = serializers.CharField(allow_null=True, required=False)
    reason = serializers.CharField(allow_null=True, required=False)
    user_name = serializers.CharField(allow_null=True, required=False)

    @classmethod
    def from_dto(cls, dto: StockMovementResponseDTO) -> dict:
        serializer = cls(
            data={
                "id": dto.id,
                "business_id": dto.business_id,
                "product_id": dto.product_id,
                "movement_type": dto.movement_type,
                "quantity": dto.quantity,
                "user_id": dto.user_id,
                "created_at": dto.created_at,
                "product_name": dto.product_name,
                "reason": dto.reason,
                "user_name": dto.user_name,
            }
        )
        serializer.is_valid(raise_exception=True)
        return serializer.data
