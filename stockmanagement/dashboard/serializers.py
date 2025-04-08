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


# Serializers pour les sous-éléments des réponses
class KPIItemSerializer(serializers.Serializer):
    value = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    change = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    change_percent = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)


class SalesDataPointSerializer(serializers.Serializer):
    period = serializers.CharField(required=False)
    date = serializers.CharField(required=False)
    sales = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    target = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    profit = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    expenses = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)


class RecentSaleSerializer(serializers.Serializer):
    id = serializers.CharField(required=False)
    customerName = serializers.CharField(required=False)
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    date = serializers.CharField(required=False)


class CategorySaleSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    value = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)


class ProductPerformanceSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    sold = serializers.IntegerField(required=False)
    revenue = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)


class StockStatusSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    value = serializers.IntegerField(required=False)


class StockDataSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    inStock = serializers.IntegerField(required=False)
    lowStock = serializers.IntegerField(required=False)
    outOfStock = serializers.IntegerField(required=False)


class StockAlertSerializer(serializers.Serializer):
    low_stock = serializers.IntegerField(required=False)
    out_of_stock = serializers.IntegerField(required=False)
    overstocked = serializers.IntegerField(required=False)


class DashboardStatsSerializer(serializers.Serializer):
    """
    Serializer for dashboard statistics response.
    """
    revenue = KPIItemSerializer(required=False)
    orders = KPIItemSerializer(required=False)
    averageOrderValue = KPIItemSerializer()
    customers = KPIItemSerializer(required=False)


class MonthlyRevenueSerializer(serializers.Serializer):
    month = serializers.CharField(required=False)
    revenue = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)


class SalesDataSerializer(serializers.Serializer):
    """
    Serializer for sales data response.
    """
    salesOverTime = SalesDataPointSerializer(many=True, required=False)
    recentSales = RecentSaleSerializer(many=True, required=False)
    salesByCategory = CategorySaleSerializer(many=True, required=False)
    monthlyRevenue = MonthlyRevenueSerializer(many=True, required=False)


class ProductsDataSerializer(serializers.Serializer):
    """
    Serializer for products data response.
    """
    topProducts = ProductPerformanceSerializer(many=True, required=False)
    productPerformance = CategorySaleSerializer(many=True, required=False)


class InventoryDataDashboardSerializer(serializers.Serializer):
    """
    Serializer for inventory data response.
    """
    stockStatus = StockStatusSerializer(many=True, required=False)
    stockData = StockDataSerializer(many=True, required=False)
    alerts = StockAlertSerializer(required=False)
