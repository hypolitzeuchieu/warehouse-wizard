"""Inventory serializers."""

from decimal import Decimal
from uuid import uuid4

from rest_framework import serializers

from application.dto.inventory_dto import (
    CategoryCreateDTO,
    CategoryResponseDTO,
    CategoryUpdateDTO,
    ProductCreateDTO,
    ProductResponseDTO,
    ProductUpdateDTO,
    StockMovementCreateDTO,
    StockMovementResponseDTO,
    SubCategoryCreateDTO,
    SubCategoryResponseDTO,
    SubCategoryUpdateDTO,
)
from shared.services.s3_service import S3Service
from shared.utils.upload_validation import validate_max_upload_size


class OptionalDescriptionMixin:
    """Mixin to handle optional description field that converts empty strings to None."""

    def validate_description(self, value):
        """Convert empty strings to None."""
        if value == "":
            return None
        return value


class CategoryCreateSerializer(OptionalDescriptionMixin, serializers.Serializer):
    """Serializer for category creation."""

    name = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def to_dto(self) -> CategoryCreateDTO:
        return CategoryCreateDTO(
            name=self.validated_data["name"],
            description=self.validated_data.get("description", None),
        )


class CategoryUpdateSerializer(OptionalDescriptionMixin, serializers.Serializer):
    """Serializer for category update."""

    name = serializers.CharField(max_length=100, required=False, allow_blank=False)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def to_dto(self) -> CategoryUpdateDTO:
        return CategoryUpdateDTO(
            name=self.validated_data.get("name"),
            description=self.validated_data.get("description"),
        )


class CategoryResponseSerializer(serializers.Serializer):
    """Serializer for category responses."""

    id = serializers.UUIDField()
    business_id = serializers.UUIDField()
    name = serializers.CharField()
    description = serializers.CharField(allow_null=True, required=False)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    @classmethod
    def from_dto(cls, dto: CategoryResponseDTO) -> dict:
        serializer = cls(
            data={
                "id": dto.id,
                "business_id": dto.business_id,
                "name": dto.name,
                "description": dto.description,
                "created_at": dto.created_at,
                "updated_at": dto.updated_at,
            }
        )
        serializer.is_valid(raise_exception=True)
        return serializer.data


class SubCategoryCreateSerializer(OptionalDescriptionMixin, serializers.Serializer):
    """Serializer for subcategory creation."""

    category_id = serializers.UUIDField()
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def to_dto(self) -> SubCategoryCreateDTO:
        return SubCategoryCreateDTO(
            category_id=self.validated_data["category_id"],
            name=self.validated_data["name"],
            description=self.validated_data.get("description"),
        )


class SubCategoryUpdateSerializer(OptionalDescriptionMixin, serializers.Serializer):
    """Serializer for subcategory update."""

    name = serializers.CharField(max_length=100, required=False, allow_blank=False)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def to_dto(self) -> SubCategoryUpdateDTO:
        return SubCategoryUpdateDTO(
            name=self.validated_data.get("name"),
            description=self.validated_data.get("description"),
        )


class SubCategoryResponseSerializer(serializers.Serializer):
    """Serializer for subcategory responses."""

    id = serializers.UUIDField()
    business_id = serializers.UUIDField()
    category_id = serializers.UUIDField()
    name = serializers.CharField()
    description = serializers.CharField(allow_null=True, required=False)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    @classmethod
    def from_dto(cls, dto: SubCategoryResponseDTO) -> dict:
        serializer = cls(
            data={
                "id": dto.id,
                "business_id": dto.business_id,
                "category_id": dto.category_id,
                "name": dto.name,
                "description": dto.description,
                "created_at": dto.created_at,
                "updated_at": dto.updated_at,
            }
        )
        serializer.is_valid(raise_exception=True)
        return serializer.data


class ProductCreateSerializer(serializers.Serializer):
    """Serializer for product creation."""

    name = serializers.CharField(max_length=255, required=True)
    description = serializers.CharField(required=False, allow_blank=True)
    barcode = serializers.CharField(
        max_length=100, required=False, allow_blank=True, allow_null=True
    )

    def validate_barcode(self, value):
        """Validate barcode format if provided."""
        if value and value.strip():
            cleaned_value = value.strip()
            if not cleaned_value.isdigit() or len(cleaned_value) != 13:
                return None
            return cleaned_value
        return None  # Return None to trigger automatic generation

    category_id = serializers.UUIDField(required=True)
    subcategory_id = serializers.UUIDField(required=False, allow_null=True)
    purchase_price = serializers.DecimalField(max_digits=15, decimal_places=2, required=True)
    unit_price = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=True, min_value=Decimal("0.01")
    )
    image = serializers.ImageField(required=False, allow_null=True)
    quantity = serializers.IntegerField(required=False, default=0, min_value=0)
    min_quantity = serializers.IntegerField(required=False, default=10, min_value=0)
    expiry_date = serializers.DateTimeField(required=False, allow_null=True)
    on_promotion = serializers.BooleanField(required=False, default=False)
    promotion_start_date = serializers.DateTimeField(required=False, allow_null=True)
    promotion_end_date = serializers.DateTimeField(required=False, allow_null=True)
    promo_price = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False, allow_null=True, min_value=Decimal("0.01")
    )

    def validate(self, attrs):
        """Validate product data."""
        unit_price = attrs.get("unit_price")
        purchase_price = attrs.get("purchase_price")
        quantity = attrs.get("quantity", 0)
        min_quantity = attrs.get("min_quantity", 10)
        on_promotion = attrs.get("on_promotion", False)
        promotion_start_date = attrs.get("promotion_start_date")
        promotion_end_date = attrs.get("promotion_end_date")
        promo_price = attrs.get("promo_price")

        if min_quantity > quantity:
            raise serializers.ValidationError(
                {"min_quantity": "min_quantity cannot be greater than quantity"}
            )

        if on_promotion:
            if not promotion_start_date:
                raise serializers.ValidationError(
                    {
                        "promotion_start_date": "promotion_start_date is required when on_promotion is True"
                    }
                )
            if not promotion_end_date:
                raise serializers.ValidationError(
                    {
                        "promotion_end_date": "promotion_end_date is required when on_promotion is True"
                    }
                )
            if not promo_price:
                raise serializers.ValidationError(
                    {"promo_price": "promo_price is required when on_promotion is True"}
                )

            # Validate promotion dates
            if promotion_end_date <= promotion_start_date:
                raise serializers.ValidationError(
                    {"promotion_end_date": "promotion_end_date must be after promotion_start_date"}
                )

            # Validate promo_price < unit_price
            if promo_price >= unit_price:
                raise serializers.ValidationError(
                    {"promo_price": "promo_price must be less than unit_price"}
                )

        else:
            # If not on promotion, unit_price must be >= purchase_price
            if unit_price < purchase_price:
                raise serializers.ValidationError(
                    {
                        "unit_price": "unit_price must be greater than or equal to purchase_price when not on promotion"
                    }
                )

        if attrs.get("image"):
            validate_max_upload_size(attrs.get("image"), field_name="image")

        return attrs

    def to_dto(self, business_id: str | None = None) -> ProductCreateDTO:
        """Convert to DTO."""
        # Handle image upload if provided
        image_url = None

        if "image" in self.validated_data and self.validated_data["image"]:

            s3_service = S3Service()
            image_file = self.validated_data["image"]
            # Set content_type for the file
            image_file.content_type = image_file.content_type or "image/jpeg"

            filename = s3_service.build_named_filename(
                prefix="product-image",
                name=self.validated_data.get("name"),
                entity_id=str(uuid4()),
                extra=(business_id or None),
            )
            image_url = s3_service.upload_image(
                file=image_file,
                folder="products",
                filename=filename,
            )

        return ProductCreateDTO(
            name=self.validated_data["name"],
            description=self.validated_data.get("description"),
            barcode=self.validated_data.get("barcode"),
            category_id=self.validated_data["category_id"],
            subcategory_id=self.validated_data.get("subcategory_id"),
            purchase_price=self.validated_data["purchase_price"],
            unit_price=self.validated_data["unit_price"],
            image_url=image_url,
            quantity=self.validated_data.get("quantity", 0),
            min_quantity=self.validated_data.get("min_quantity", 10),
            expiry_date=self.validated_data.get("expiry_date"),
            on_promotion=self.validated_data.get("on_promotion", False),
            promotion_start_date=self.validated_data.get("promotion_start_date"),
            promotion_end_date=self.validated_data.get("promotion_end_date"),
            promo_price=self.validated_data.get("promo_price"),
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
    image = serializers.ImageField(required=False, allow_null=True)
    quantity = serializers.IntegerField(required=False, min_value=0)
    min_quantity = serializers.IntegerField(required=False, min_value=0)
    expiry_date = serializers.DateTimeField(required=False, allow_null=True)

    def to_dto(
        self, business_id: str | None = None, old_image_url: str | None = None
    ) -> ProductUpdateDTO:
        """Convert to DTO."""
        # Handle image upload if provided
        image_url = old_image_url

        if "image" in self.validated_data and self.validated_data["image"]:

            s3_service = S3Service()
            image_file = self.validated_data["image"]
            validate_max_upload_size(image_file, field_name="image")
            # Set content_type for the file
            image_file.content_type = image_file.content_type or "image/jpeg"

            filename = s3_service.build_named_filename(
                prefix="product-image",
                name=self.validated_data.get("name"),
                entity_id=str(uuid4()),
                extra=(business_id or None),
            )
            image_url = s3_service.upload_image(
                file=image_file,
                folder="products",
                filename=filename,
            )

            # Delete old image if new one is uploaded
            if old_image_url:
                try:
                    s3_service.delete_file_safe(old_image_url)
                except Exception:
                    pass  # Logged in delete_file_safe

        subcategory_present = "subcategory_id" in self.validated_data
        subcategory_value = (
            self.validated_data.get("subcategory_id") if subcategory_present else None
        )
        return ProductUpdateDTO(
            name=self.validated_data.get("name"),
            description=self.validated_data.get("description"),
            barcode=self.validated_data.get("barcode"),
            category_id=self.validated_data.get("category_id"),
            subcategory_id=subcategory_value,
            purchase_price=self.validated_data.get("purchase_price"),
            unit_price=self.validated_data.get("unit_price"),
            image_url=image_url,
            quantity=self.validated_data.get("quantity"),
            min_quantity=self.validated_data.get("min_quantity"),
            expiry_date=self.validated_data.get("expiry_date"),
            subcategory_id_provided=subcategory_present,
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


class LowStockProductSerializer(serializers.Serializer):
    """Serializer for low stock product responses."""

    id = serializers.UUIDField()
    name = serializers.CharField()
    quantity = serializers.IntegerField()
    min_quantity = serializers.IntegerField()
    is_low_stock = serializers.BooleanField()

    @classmethod
    def from_dto(cls, dto: ProductResponseDTO) -> dict:
        """Convert ProductResponseDTO to serialized format."""
        serializer = cls(
            data={
                "id": dto.id,
                "name": dto.name,
                "quantity": dto.quantity,
                "min_quantity": dto.min_quantity,
                "is_low_stock": dto.is_low_stock,
            }
        )
        serializer.is_valid(raise_exception=True)
        return serializer.data


class ExpiredProductSerializer(serializers.Serializer):
    """Serializer for expired product responses."""

    id = serializers.UUIDField()
    name = serializers.CharField()
    expiry_date = serializers.DateTimeField(allow_null=True, required=False)
    is_expired = serializers.BooleanField()

    @classmethod
    def from_dto(cls, dto: ProductResponseDTO) -> dict:
        """Convert ProductResponseDTO to serialized format."""
        serializer = cls(
            data={
                "id": dto.id,
                "name": dto.name,
                "expiry_date": dto.expiry_date,
                "is_expired": dto.is_expired,
            }
        )
        serializer.is_valid(raise_exception=True)
        return serializer.data


class ProductListQuerySerializer(serializers.Serializer):
    """Serializer for product list query parameters."""

    business_id = serializers.UUIDField(required=True)
    category_id = serializers.UUIDField(required=False, allow_null=True)
    subcategory_id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    low_stock_only = serializers.BooleanField(required=False, allow_null=True)
    expired_only = serializers.BooleanField(required=False, allow_null=True)
    search = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    page_size = serializers.IntegerField(required=False, min_value=1, max_value=1000, default=20)
    order_by = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class ProductScanSerializer(serializers.Serializer):
    """Serializer for product scan responses."""

    id = serializers.UUIDField()
    name = serializers.CharField()
    barcode = serializers.CharField(allow_null=True, required=False)
    barcode_image_url = serializers.CharField(allow_null=True, required=False)
    unit_price = serializers.DecimalField(max_digits=15, decimal_places=2)
    current_price = serializers.DecimalField(max_digits=15, decimal_places=2)
    quantity = serializers.IntegerField()
    is_low_stock = serializers.BooleanField()
    is_expired = serializers.BooleanField()

    @classmethod
    def from_product(cls, product) -> dict:
        """Convert product entity to serialized format."""

        serializer = cls(
            data={
                "id": product.id,
                "name": product.name,
                "barcode": product.barcode,
                "barcode_image_url": product.barcode_image_url,
                "unit_price": product.unit_price,
                "current_price": product.get_current_price(),
                "quantity": product.quantity,
                "is_low_stock": product.is_low_stock(),
                "is_expired": product.is_expired,
            }
        )
        serializer.is_valid(raise_exception=True)
        return serializer.data
