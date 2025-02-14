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
    category_id = serializers.CharField(required=True)
    subcategory_id = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )


class GetProductCategorySerializer(serializers.Serializer):
    category_id = serializers.CharField(required=True)


class GetProductSubCategorySerializer(serializers.Serializer):
    subcategory_id = serializers.CharField(required=True)


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

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'description',
            'unit_price',
            'image',
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
        if attrs.get('on_promotion'):
            if not attrs.get('promo_price'):
                raise serializers.ValidationError(
                    'Promotion price is required when the product is on promotion.'
                )
            if attrs.get('promotion_start_date') and attrs.get(
                'promotion_end_date'
            ):
                if (
                    attrs['promotion_start_date']
                    >= attrs['promotion_end_date']
                ):
                    raise serializers.ValidationError(
                        'Promotion start date must be before promotion end date.'
                    )
            elif not (
                attrs.get('promotion_start_date')
                or attrs.get('promotion_end_date')
            ):
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
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all()
    )
    subcategory = serializers.PrimaryKeyRelatedField(
        queryset=SubCategory.objects.all(), required=False, allow_null=True
    )
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            'id',
            'product',
            'category',
            'subcategory',
            'movement_type',
            'quantity',
            'reason',
            'user',
            'created_at',
        ]


class ProductDetailSerializer(serializers.Serializer):
    product_id = serializers.CharField(required=True)
