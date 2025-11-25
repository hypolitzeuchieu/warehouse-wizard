"""Repository implementations for RetailPulse."""

from infrastructure.persistence.repositories.business_repositories import (
    BusinessMemberRepositoryImpl,
    BusinessRepositoryImpl,
)
from infrastructure.persistence.repositories.credit_repositories import (
    CreditPaymentRepositoryImpl,
    CreditRepositoryImpl,
)
from infrastructure.persistence.repositories.customer_repositories import (
    CustomerPurchaseHistoryRepositoryImpl,
    CustomerRepositoryImpl,
)
from infrastructure.persistence.repositories.delivery_repositories import (
    DeliveryRepositoryImpl,
)
from infrastructure.persistence.repositories.finance_repositories import (
    ExpenseAuditLogRepositoryImpl,
    ExpenseRepositoryImpl,
    FinancialSummaryRepositoryImpl,
    PayrollRepositoryImpl,
    SalaryRepositoryImpl,
)
from infrastructure.persistence.repositories.inventory_repositories import (
    CategoryRepositoryImpl,
    ProductRepositoryImpl,
    StockMovementRepositoryImpl,
    SubCategoryRepositoryImpl,
)
from infrastructure.persistence.repositories.notification_repositories import (
    NotificationRepositoryImpl,
)
from infrastructure.persistence.repositories.otp_repositories import (
    OTPRepositoryImpl,
)
from infrastructure.persistence.repositories.sales_repositories import (
    InvoiceLineRepositoryImpl,
    InvoiceLogRepositoryImpl,
    InvoicePaymentRepositoryImpl,
    InvoiceRepositoryImpl,
    OrderItemRepositoryImpl,
    OrderRepositoryImpl,
)
from infrastructure.persistence.repositories.user_repositories import (
    DeviceRepositoryImpl,
    RefreshTokenRepositoryImpl,
    SessionRepositoryImpl,
    UserRepositoryImpl,
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
    "InvoicePaymentRepositoryImpl",
    "InvoiceLogRepositoryImpl",
    "OrderRepositoryImpl",
    "OrderItemRepositoryImpl",
    # Finance repositories
    "ExpenseRepositoryImpl",
    "ExpenseAuditLogRepositoryImpl",
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
    # Credit repositories
    "CreditRepositoryImpl",
    "CreditPaymentRepositoryImpl",
    # OTP repositories
    "OTPRepositoryImpl",
]
