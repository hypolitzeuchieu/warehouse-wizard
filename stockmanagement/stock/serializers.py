from __future__ import annotations

from rest_framework import serializers
from stock.models import Category
from stock.models import Product
from stock.models import Stock
from stock.models import StockMovement
from stock.models import SubCategory


class CategorySerializer(serializers.ModelSerializer):

    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'created_at']


class QuantitySerializer(serializers.Serializer):
    product_id = serializers.CharField(required=True)


class GetProductCategorySerializer(serializers.Serializer):
    category_id = serializers.CharField(required=True)
    page_size = serializers.IntegerField(required=False, min_value=1, default=10)


class GetProductSubCategorySerializer(serializers.Serializer):
    subcategory_id = serializers.CharField(required=True)
    page_size = serializers.IntegerField(required=False, min_value=1, default=10)


class SubCategorySerializer(serializers.ModelSerializer):
    category_id = serializers.CharField(required=True)

    class Meta:
        model = SubCategory
        fields = ['id', 'name', 'description', 'created_at', 'category_id']


class ProductSerializer(serializers.ModelSerializer):
    category_id = serializers.CharField(required=True)
    subcategory_id = serializers.CharField(
        allow_null=True, required=False, allow_blank=True
    )
    purchase_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, write_only=True
    )
    image_file = serializers.ImageField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'description',
            'purchase_price',
            'unit_price',
            'image',
            'image_file',
            'created_at',
            'quantity',
            'min_quantity',
            'is_expired',
            'expiry_date',
            'on_promotion',
            'promotion_start_date',
            'promotion_end_date',
            'promo_price',
            'category_id',
            'subcategory_id',
        ]

    def validate(self, attrs):
        unit_price = attrs.get('unit_price')
        purchase_price = attrs.get('purchase_price')
        on_promotion = attrs.get('on_promotion', False)
        promo_price = attrs.get('promo_price')

        if unit_price is not None and purchase_price is not None:
            if unit_price < purchase_price and not on_promotion:
                raise serializers.ValidationError(
                    'Unit price cannot be less than the purchase price.'
                )

        if on_promotion:
            if not promo_price:
                raise serializers.ValidationError(
                    'Promotion price is required when the product is on promotion.'
                )
            if attrs.get('promotion_start_date') and attrs.get('promotion_end_date'):
                if attrs['promotion_start_date'] >= attrs['promotion_end_date']:
                    raise serializers.ValidationError(
                        'Promotion start date must be before promotion end date.'
                    )
            elif not (attrs.get('promotion_start_date') or attrs.get('promotion_end_date')):
                raise serializers.ValidationError(
                    'At least one of promotion_start_date or promotion_end_date'
                    ' is required when the product is on promotion.'
                )
        return attrs


class StockSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    subcategory = SubCategorySerializer(read_only=True)

    class Meta:
        model = Stock
        fields = [
            'id',
            'product',
            'category',
            'subcategory',
        ]


class StockMovementSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all()
    )
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            'id',
            'product',
            'movement_type',
            'quantity',
            'reason',
            'user',
            'created_at',
        ]


class ProductDetailSerializer(serializers.Serializer):
    product_id = serializers.CharField(required=True)


class ProductUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating an existing product.
    """
    product_id = serializers.CharField()
    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(allow_blank=True, required=False)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    expired_date = serializers.DateTimeField(required=False)
    image = serializers.ImageField(required=False, allow_null=True)
    on_promotion = serializers.BooleanField(required=False)
    promo_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )
    promotion_start_date = serializers.DateTimeField(required=False, allow_null=True)
    promotion_end_date = serializers.DateTimeField(required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=0, required=False)
    min_quantity = serializers.IntegerField(min_value=0, required=False)

    def validate(self, attrs):
        """
        Validation for update constraints.
        """
        unit_price = attrs.get('unit_price')
        promo_price = attrs.get('promo_price')
        on_promotion = attrs.get('on_promotion', False)
        promotion_start_date = attrs.get('promotion_start_date')
        promotion_end_date = attrs.get('promotion_end_date')

        # Promo price validation
        if on_promotion:
            if promo_price is None:
                raise serializers.ValidationError(
                    {'promo_price': 'Promo price is required '
                                    'when the product is on promotion.'}
                )
            if unit_price is not None and promo_price >= unit_price:
                raise serializers.ValidationError(
                    {'promo_price': 'Promo price must be less than the unit price.'}
                )

        # Promotion dates validation
        if promotion_start_date and promotion_end_date:
            if promotion_start_date >= promotion_end_date:
                raise serializers.ValidationError(
                    {'promotion_end_date': 'Promotion end date must '
                                           'be after promotion start date.'}
                )
        elif on_promotion and not (promotion_start_date or promotion_end_date):
            raise serializers.ValidationError(
                'At least one of promotion start date or promotion end date'
                ' is required when the product is on promotion.'
            )

        return attrs


class PaginationQuerySerializer(serializers.Serializer):
    page_size = serializers.IntegerField(required=False, min_value=1, default=10)
