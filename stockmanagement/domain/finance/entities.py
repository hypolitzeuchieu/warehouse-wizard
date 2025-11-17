"""Finance domain entities."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID


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


@dataclass
class Expense:
    """Expense entity."""

    id: UUID
    business_id: UUID
    expense_type: ExpenseType
    amount: Decimal
    reason: str
    user_id: UUID  # User who created the expense
    approved_by: UUID | None  # User who approved the expense
    is_approved: bool
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        """Validate expense data."""
        if self.amount <= 0:
            raise ValueError("Expense amount must be greater than zero")
        if not self.reason:
            raise ValueError("Expense reason is required")


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
            from django.utils import timezone

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
