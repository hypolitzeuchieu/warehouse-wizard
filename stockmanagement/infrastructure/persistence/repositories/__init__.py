"""Repository implementations for RetailPulse."""

from infrastructure.persistence.repositories.user_repositories import (
    DeviceRepositoryImpl,
    RefreshTokenRepositoryImpl,
    SessionRepositoryImpl,
    UserRepositoryImpl,
)
from infrastructure.persistence.repositories.business_repositories import (
    BusinessMemberRepositoryImpl,
    BusinessRepositoryImpl,
)
from infrastructure.persistence.repositories.inventory_repositories import (
    CategoryRepositoryImpl,
    ProductRepositoryImpl,
    StockMovementRepositoryImpl,
    SubCategoryRepositoryImpl,
)
from infrastructure.persistence.repositories.sales_repositories import (
    InvoiceLineRepositoryImpl,
    InvoiceRepositoryImpl,
    OrderItemRepositoryImpl,
    OrderRepositoryImpl,
)
from infrastructure.persistence.repositories.finance_repositories import (
    ExpenseRepositoryImpl,
    FinancialSummaryRepositoryImpl,
    PayrollRepositoryImpl,
    SalaryRepositoryImpl,
)
from infrastructure.persistence.repositories.notification_repositories import (
    NotificationRepositoryImpl,
)
from infrastructure.persistence.repositories.delivery_repositories import (
    DeliveryRepositoryImpl,
)
from infrastructure.persistence.repositories.customer_repositories import (
    CustomerPurchaseHistoryRepositoryImpl,
    CustomerRepositoryImpl,
)
from infrastructure.persistence.repositories.otp_repositories import (
    OTPRepositoryImpl,
)
from infrastructure.persistence.repositories.sales_repositories import (
    InvoiceLineRepositoryImpl,
    InvoiceRepositoryImpl,
    OrderItemRepositoryImpl,
    OrderRepositoryImpl,
)

__all__ = [
    # User repositories
    "UserRepositoryImpl",
    "SessionRepositoryImpl",
    "RefreshTokenRepositoryImpl",
    "DeviceRepositoryImpl",
    # Business repositories
    "BusinessRepositoryImpl",
    "BusinessMemberRepositoryImpl",
    # Inventory repositories
    "CategoryRepositoryImpl",
    "SubCategoryRepositoryImpl",
    "ProductRepositoryImpl",
    "StockMovementRepositoryImpl",
    # Sales repositories
    "InvoiceRepositoryImpl",
    "InvoiceLineRepositoryImpl",
    "OrderRepositoryImpl",
    "OrderItemRepositoryImpl",
    # Finance repositories
    "ExpenseRepositoryImpl",
    "SalaryRepositoryImpl",
    "PayrollRepositoryImpl",
    "FinancialSummaryRepositoryImpl",
    # Notification repositories
    "NotificationRepositoryImpl",
    # Delivery repositories
    "DeliveryRepositoryImpl",
    # Customer repositories
    "CustomerRepositoryImpl",
    "CustomerPurchaseHistoryRepositoryImpl",
    # OTP repositories
    "OTPRepositoryImpl",
]

