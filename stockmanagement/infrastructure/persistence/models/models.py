"""Django models module - imports all models for auto-discovery."""

from infrastructure.persistence.models.business_models import (  # noqa: F401
    Business,
    BusinessMember,
)
from infrastructure.persistence.models.customer_models import (  # noqa: F401
    Customer,
    CustomerPurchaseHistory,
)
from infrastructure.persistence.models.delivery_models import Delivery  # noqa: F401
from infrastructure.persistence.models.finance_models import (  # noqa: F401
    Expense,
    FinancialSummary,
    Payroll,
    Salary,
)
from infrastructure.persistence.models.inventory_models import (  # noqa: F401
    Category,
    Product,
    StockMovement,
    SubCategory,
)
from infrastructure.persistence.models.notification_models import Notification  # noqa: F401
from infrastructure.persistence.models.otp_models import OTP  # noqa: F401
from infrastructure.persistence.models.password_reset_models import PasswordResetToken  # noqa: F401
from infrastructure.persistence.models.report_models import Report  # noqa: F401
from infrastructure.persistence.models.sales_models import (  # noqa: F401
    Invoice,
    InvoiceLine,
    Order,
    OrderItem,
)
from infrastructure.persistence.models.user_models import (  # noqa: F401
    Device,
    RefreshToken,
    RetailPulseUser,
    Session,
)
