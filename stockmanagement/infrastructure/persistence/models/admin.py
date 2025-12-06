"""Django admin configuration for persistence models."""

from django.contrib import admin

from infrastructure.persistence.models.business_models import (
    Business,
    BusinessMember,
)
from infrastructure.persistence.models.customer_models import (
    Customer,
    CustomerPurchaseHistory,
)
from infrastructure.persistence.models.delivery_models import Delivery
from infrastructure.persistence.models.doc_credential_models import (
    DocumentationCredential,
)
from infrastructure.persistence.models.finance_models import (
    Expense,
    FinancialSummary,
    Payroll,
    Salary,
)
from infrastructure.persistence.models.inventory_models import (
    Category,
    Product,
    StockMovement,
    SubCategory,
)
from infrastructure.persistence.models.notification_models import Notification
from infrastructure.persistence.models.otp_models import OTP
from infrastructure.persistence.models.password_reset_models import PasswordResetToken
from infrastructure.persistence.models.sales_models import (
    Invoice,
    InvoiceLine,
    Order,
    OrderItem,
)
from infrastructure.persistence.models.user_models import (
    Device,
    RefreshToken,
    RetailPulseUser,
    Session,
)

# Register models with admin (optional, can be customized later)
admin.site.register(RetailPulseUser)
admin.site.register(Session)
admin.site.register(RefreshToken)
admin.site.register(Device)
admin.site.register(Business)
admin.site.register(BusinessMember)
admin.site.register(Category)
admin.site.register(SubCategory)
admin.site.register(Product)
admin.site.register(StockMovement)
admin.site.register(Invoice)
admin.site.register(InvoiceLine)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(Expense)
admin.site.register(Salary)
admin.site.register(Payroll)
admin.site.register(FinancialSummary)
admin.site.register(Notification)
admin.site.register(Delivery)
admin.site.register(Customer)
admin.site.register(CustomerPurchaseHistory)
admin.site.register(OTP)
admin.site.register(PasswordResetToken)


@admin.register(DocumentationCredential)
class DocumentationCredentialAdmin(admin.ModelAdmin):
    """Admin interface for DocumentationCredential."""

    list_display = ("username", "is_active", "expires_at", "created_at", "updated_at")
    list_filter = ("is_active", "expires_at", "created_at")
    search_fields = ("username",)
    readonly_fields = ("id", "created_at", "updated_at", "password_hash")
    fieldsets = (
        ("Credential Information", {"fields": ("username", "password_hash")}),
        ("Status", {"fields": ("is_active", "expires_at")}),
        ("Metadata", {"fields": ("id", "created_at", "updated_at")}),
    )
    actions = ["activate_credentials", "deactivate_credentials"]

    def activate_credentials(self, request, queryset):
        """Activate selected credentials."""
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} credential(s) activated.")

    activate_credentials.short_description = "Activate selected credentials"

    def deactivate_credentials(self, request, queryset):
        """Deactivate selected credentials."""
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} credential(s) deactivated.")

    deactivate_credentials.short_description = "Deactivate selected credentials"
