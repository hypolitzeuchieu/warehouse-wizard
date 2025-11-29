"""Dashboard DTOs."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
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
    period_start: datetime
    period_end: datetime
    revenue: RevenueMetricsDTO
    expenses: ExpenseMetricsDTO
    profit: ProfitMetricsDTO
    inventory: InventoryMetricsDTO
    customers: CustomerMetricsDTO
    top_products: list[TopProductDTO]
    generated_at: datetime


@dataclass
class DailyMetricsDTO:
    """DTO for daily metrics."""

    date: datetime
    complete_revenue: Decimal
    credit_revenue: Decimal
    total_revenue: Decimal
    profit: Decimal
    gross_profit: Decimal
    net_profit: Decimal
    total_sales: int
    total_expenses: Decimal
    credit_outstanding: Decimal


@dataclass
class TopCategoryDTO:
    """DTO for top category."""

    category_id: UUID
    category_name: str
    total_revenue: Decimal
    total_quantity_sold: int
    number_of_sales: int


@dataclass
class RecentSaleDTO:
    """DTO for recent sale."""

    invoice_id: UUID
    invoice_number: int
    customer_name: str | None
    total: Decimal
    status: str
    created_at: datetime


@dataclass
class ProductStatisticsDTO:
    """DTO for product statistics."""

    product_id: UUID
    product_name: str
    date: datetime
    quantity_sold: int
    revenue: Decimal
    cost: Decimal
    profit: Decimal
    margin_percentage: Decimal


@dataclass
class ProductMarginDTO:
    """DTO for product margin."""

    product_id: UUID
    product_name: str
    total_quantity_sold: int
    total_revenue: Decimal
    total_cost: Decimal
    total_profit: Decimal
    margin_percentage: Decimal


@dataclass
class PeriodTotalsDTO:
    """DTO for period totals."""

    total_revenue: Decimal
    total_sales: int
    credit_outstanding: Decimal
    total_expenses: Decimal
    gross_profit: Decimal
    net_profit: Decimal


@dataclass
class SalesPerformanceDTO:
    """DTO for sales performance summary."""

    credit_revenue: Decimal
    total_revenue: Decimal
    complete_revenue: Decimal
    profit: Decimal


@dataclass
class DashboardDailyResponseDTO:
    """DTO for daily dashboard response."""

    business_id: UUID
    period_start: datetime
    period_end: datetime
    totals: PeriodTotalsDTO
    daily_data: list[DailyMetricsDTO]
    sales_performance: SalesPerformanceDTO
    top_products: list[TopProductDTO]
    top_categories: list[TopCategoryDTO]
    recent_sales: list[RecentSaleDTO]
    product_statistics: dict[str, list[ProductStatisticsDTO]]
    product_margins: list[ProductMarginDTO]
    generated_at: datetime


@dataclass
class TrendsDTO:
    """DTO for trends comparison."""

    previous_period_start: datetime
    previous_period_end: datetime
    current_value: Decimal
    previous_value: Decimal
    change_amount: Decimal
    change_percentage: Decimal
    trend_direction: str


@dataclass
class ProductInfoDTO:
    """DTO for product information."""

    product_id: UUID
    product_name: str
    category_id: UUID
    category_name: str
    subcategory_id: UUID | None
    subcategory_name: str | None


@dataclass
class TopCustomerDTO:
    """DTO for top customer."""

    customer_id: UUID | None
    customer_name: str
    total_purchases: int
    total_revenue: Decimal


@dataclass
class ProductDetailStatisticsDTO:
    """DTO for detailed product statistics."""

    product: ProductInfoDTO
    period_start: datetime
    period_end: datetime
    totals: dict[str, Decimal | int]
    daily_data: list[ProductStatisticsDTO]
    trends: dict[str, TrendsDTO]
    top_customers: list[TopCustomerDTO]


@dataclass
class CategoryInfoDTO:
    """DTO for category information."""

    category_id: UUID
    category_name: str


@dataclass
class CategoryStatisticsDTO:
    """DTO for category statistics."""

    category: CategoryInfoDTO
    period_start: datetime
    period_end: datetime
    totals: dict[str, Decimal | int]
    top_products: list[TopProductDTO]
    daily_data: list[dict[str, Any]]
    trends: dict[str, TrendsDTO]


@dataclass
class SubCategoryInfoDTO:
    """DTO for subcategory information."""

    subcategory_id: UUID
    subcategory_name: str
    category_id: UUID
    category_name: str


@dataclass
class SubCategoryStatisticsDTO:
    """DTO for subcategory statistics."""

    subcategory: SubCategoryInfoDTO
    period_start: datetime
    period_end: datetime
    totals: dict[str, Decimal | int]
    top_products: list[TopProductDTO]
    daily_data: list[dict[str, Any]]
    trends: dict[str, TrendsDTO]


@dataclass
class CashierInfoDTO:
    """DTO for cashier information."""

    cashier_id: UUID
    cashier_name: str
    cashier_email: str
    phone_number: str | None
    avatar_url: str | None
    role: str
    is_active: bool
    joined_at: datetime
    left_at: datetime | None


@dataclass
class CashierDailyDataDTO:
    """DTO for cashier daily data."""

    date: datetime
    total_sales: int
    total_revenue: Decimal
    total_quantity_sold: int
    average_sale_value: Decimal
    customers_served: int


@dataclass
class CashierStatisticsDTO:
    """DTO for cashier statistics."""

    cashier: CashierInfoDTO
    period_start: datetime
    period_end: datetime
    totals: dict[str, Decimal | int]
    lifetime_totals: dict[str, Decimal | int]
    daily_data: list[CashierDailyDataDTO]
    trends: dict[str, TrendsDTO]
    ranking: int | None
