# dashboard/serializers.py
from __future__ import annotations

from rest_framework import serializers


class PeriodQuerySerializer(serializers.Serializer):
    """
    Serializer for period query parameters.
    """
    period = serializers.ChoiceField(
        choices=['daily', 'weekly', 'monthly', 'yearly'],
        default='monthly',
        required=False
    )


class CategorySaleSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    value = serializers.DecimalField(max_digits=20, decimal_places=3, required=False)


class ProductPerformanceSerializer(serializers.Serializer):
    name = serializers.CharField()
    sold = serializers.IntegerField()
    revenue = serializers.FloatField()
    profit = serializers.FloatField()
    margin = serializers.FloatField(required=False)


class ProductsDataSerializer(serializers.Serializer):
    top_products = ProductPerformanceSerializer(many=True)
    top_categories = ProductPerformanceSerializer(many=True)


class StockStatusSerializer(serializers.Serializer):
    name = serializers.CharField()
    value = serializers.IntegerField()
    color = serializers.CharField(required=False)


class SalesDataSerializer(serializers.ListSerializer):
    child = serializers.DictField()

    class SalesItemSerializer(serializers.Serializer):
        period = serializers.CharField()
        date = serializers.CharField()
        completed = serializers.DictField()
        credit = serializers.DictField()
        total = serializers.DictField()

    child = SalesItemSerializer()


class InventoryDataDashboardSerializer(serializers.Serializer):
    stockStatus = StockStatusSerializer(many=True)
    stockData = serializers.ListSerializer(child=serializers.DictField())
    alerts = serializers.DictField()


class CreditDataSerializer(serializers.Serializer):
    total = serializers.FloatField()
    advance_paid = serializers.FloatField()
    to_collect = serializers.FloatField()
    count = serializers.IntegerField()


class RevenueDataSerializer(serializers.Serializer):
    total = serializers.FloatField()
    completed = serializers.FloatField()
    credit = CreditDataSerializer()
    advance_paid = serializers.FloatField()
    outstanding = serializers.FloatField()


class DashboardStatsSerializer(serializers.Serializer):
    revenue = serializers.DictField()
    profit = serializers.DictField()
    orders = serializers.DictField()
    averageOrderValue = serializers.DictField(required=False)


class RecentSaleItemSerializer(serializers.Serializer):
    """Serializer for items in a recent sale."""
    name = serializers.CharField()
    quantity = serializers.IntegerField()
    total = serializers.FloatField()


class RecentSaleSerializer(serializers.Serializer):
    """Serializer for recent sales data."""
    invoice_id = serializers.UUIDField()
    invoice_number = serializers.IntegerField()
    date = serializers.DateTimeField()
    formatted_date = serializers.CharField()
    customer = serializers.CharField()
    total = serializers.FloatField()
    profit = serializers.FloatField()
    margin = serializers.FloatField()
    items = serializers.IntegerField()
    top_items = RecentSaleItemSerializer(many=True)


class TopSellingProductSerializer(serializers.Serializer):
    """Serializer for top selling products data."""
    id = serializers.UUIDField()
    name = serializers.CharField()
    category = serializers.CharField()
    quantity_sold = serializers.IntegerField()
    revenue = serializers.FloatField()
    profit = serializers.FloatField()
    margin = serializers.FloatField()
    avg_price = serializers.FloatField()
    sale_count = serializers.IntegerField()
    trend = serializers.DictField()


class LimitQuerySerializer(serializers.Serializer):
    """
    Serializer for limit query parameters.
    """
    limit = serializers.IntegerField(default=10, required=False)
