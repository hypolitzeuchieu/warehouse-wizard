"""Dashboard DTOs."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass
class RevenueMetricsDTO:
    """DTO for revenue metrics."""

    total_revenue: Decimal
    revenue_today: Decimal
    revenue_this_week: Decimal
    revenue_this_month: Decimal
    revenue_this_year: Decimal
    average_order_value: Decimal
    total_orders: int
    orders_today: int
    orders_this_week: int
    orders_this_month: int


@dataclass
class ExpenseMetricsDTO:
    """DTO for expense metrics."""

    total_expenses: Decimal
    expenses_today: Decimal
    expenses_this_week: Decimal
    expenses_this_month: Decimal
    expenses_this_year: Decimal
    salary_expenses: Decimal
    other_expenses: Decimal


@dataclass
class ProfitMetricsDTO:
    """DTO for profit metrics."""

    total_profit: Decimal
    profit_today: Decimal
    profit_this_week: Decimal
    profit_this_month: Decimal
    profit_margin_percentage: Decimal


@dataclass
class InventoryMetricsDTO:
    """DTO for inventory metrics."""

    total_products: int
    low_stock_products: int
    expired_products: int
    total_inventory_value: Decimal
    products_on_promotion: int


@dataclass
class CustomerMetricsDTO:
    """DTO for customer metrics."""

    total_customers: int
    new_customers_today: int
    new_customers_this_week: int
    new_customers_this_month: int
    active_customers: int
    total_credit_amount: Decimal
    overdue_credit_amount: Decimal


@dataclass
class TopProductDTO:
    """DTO for top product."""

    product_id: UUID
    product_name: str
    total_sold: int
    total_revenue: Decimal
    quantity_available: int


@dataclass
class DashboardSummaryDTO:
    """DTO for complete dashboard summary."""

    business_id: UUID
    period: str  # today, week, month, year
    revenue: RevenueMetricsDTO
    expenses: ExpenseMetricsDTO
    profit: ProfitMetricsDTO
    inventory: InventoryMetricsDTO
    customers: CustomerMetricsDTO
    top_products: list[TopProductDTO]
    generated_at: datetime
