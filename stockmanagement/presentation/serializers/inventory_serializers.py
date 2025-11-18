"""Inventory serializers."""

from decimal import Decimal

from rest_framework import serializers

from application.dto.inventory_dto import (
    ProductCreateDTO,
    ProductUpdateDTO,
    StockMovementCreateDTO,
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
