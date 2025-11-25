"""Finance domain entities."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from django.utils import timezone


class ExpenseType(str, Enum):
    """Expense type enumeration."""

    REPLENISHMENT = "REPLENISHMENT"
    MISCELLANEOUS = "MISCELLANEOUS"
    ELECTRICITY = "ELECTRICITY"
    WATER = "WATER"
    SALARY = "SALARY"
    EXTRA = "EXTRA"
    MAINTENANCE = "MAINTENANCE"
    TAX = "TAX"
    RENT = "RENT"
    MARKETING = "MARKETING"
    INSURANCE = "INSURANCE"
    TRANSPORT = "TRANSPORT"
    UTILITIES = "UTILITIES"
    OFFICE_SUPPLIES = "OFFICE_SUPPLIES"
    PROFESSIONAL_SERVICES = "PROFESSIONAL_SERVICES"


class ExpensePaymentMethod(str, Enum):
    """Supported expense payment methods."""

    CASH = "CASH"
    MOBILE_MONEY = "MOBILE_MONEY"
    BANK_TRANSFER = "BANK_TRANSFER"
    CARD = "CARD"
    CHECK = "CHECK"
    OTHER = "OTHER"


class ExpensePayeeType(str, Enum):
    """Payee type enumeration."""

    EMPLOYEE = "EMPLOYEE"
    SUPPLIER = "SUPPLIER"
    SERVICE_PROVIDER = "SERVICE_PROVIDER"
    GOVERNMENT = "GOVERNMENT"
    LANDLORD = "LANDLORD"
    OTHER = "OTHER"


@dataclass
class Expense:
    """Expense entity."""

    id: UUID
    business_id: UUID
    expense_type: ExpenseType
    amount: Decimal
    reason: str
    reason_details: str | None
    user_id: UUID  # User who created the expense
    approved_by: UUID | None  # User who approved the expense
    is_approved: bool
    payment_method: ExpensePaymentMethod
    payment_reference: str | None
    payee_type: ExpensePayeeType
    payee_name: str | None
    created_at: datetime
    updated_at: datetime
    justification_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate expense data."""
        if self.amount <= 0:
            raise ValueError("Expense amount must be greater than zero")
        if not self.reason:
            raise ValueError("Expense reason is required")
        if self.payment_method not in ExpensePaymentMethod:
            raise ValueError("Invalid payment method")
        if self.payee_type not in ExpensePayeeType:
            raise ValueError("Invalid payee type")
        if not self.payee_name:
            raise ValueError("Payee name is required")
        if self.justification_metadata is None:
            self.justification_metadata = {}


@dataclass
class Salary:
    """Employee salary entity."""

    id: UUID
    business_id: UUID
    user_id: UUID
    amount: Decimal
    currency: str  # e.g., "USD", "XOF"
    payment_frequency: str  # monthly, weekly, daily
    deductions: Decimal
    bonuses: Decimal
    effective_from: datetime
    effective_to: datetime | None
    created_at: datetime
    updated_at: datetime

    def calculate_net_salary(self) -> Decimal:
        """Calculate net salary."""
        return self.amount - self.deductions + self.bonuses

    def is_active(self, current_date: datetime | None = None) -> bool:
        """Check if salary is currently active."""
        if current_date is None:
            current_date = timezone.now()

        if current_date < self.effective_from:
            return False

        if self.effective_to is None:
            return True

        return current_date <= self.effective_to


@dataclass
class Payroll:
    """Payroll entity for salary payments."""

    id: UUID
    business_id: UUID
    user_id: UUID
    salary_id: UUID
    amount: Decimal
    payment_date: datetime
    period_start: datetime
    period_end: datetime
    deductions: Decimal
    bonuses: Decimal
    net_amount: Decimal
    created_at: datetime
    updated_at: datetime


@dataclass
class FinancialSummary:
    """Financial summary entity for business."""

    business_id: UUID
    period_start: datetime
    period_end: datetime
    total_revenue: Decimal
    total_expenses: Decimal
    total_salaries: Decimal
    net_profit: Decimal
    tax_amount: Decimal
    created_at: datetime

    def calculate_profit_margin(self) -> Decimal:
        """Calculate profit margin percentage."""
        if self.total_revenue == 0:
            return Decimal("0.00")
        return (self.net_profit / self.total_revenue) * 100


@dataclass
class ExpenseAuditLog:
    """Audit trail entry for expense changes."""

    id: UUID
    expense_id: UUID
    action: str
    performed_by: UUID | None
    amount_before: Decimal | None
    amount_after: Decimal | None
    reason_before: str | None
    reason_after: str | None
    reason_details_before: str | None
    reason_details_after: str | None
    payment_method_before: ExpensePaymentMethod | None
    payment_method_after: ExpensePaymentMethod | None
    payee_type_before: ExpensePayeeType | None
    payee_type_after: ExpensePayeeType | None
    payee_name_before: str | None
    payee_name_after: str | None
    justification_snapshot: dict[str, Any]
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.action:
            raise ValueError("Audit action is required")
        if self.justification_snapshot is None:
            self.justification_snapshot = {}
