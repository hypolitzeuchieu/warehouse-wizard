"""Finance DTOs."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass
class ExpenseCreateDTO:
    """DTO for creating an expense."""

    expense_type: str
    amount: Decimal
    reason: str


@dataclass
class ExpenseUpdateDTO:
    """DTO for updating an expense."""

    expense_type: str | None = None
    amount: Decimal | None = None
    reason: str | None = None
    is_approved: bool | None = None


@dataclass
class ExpenseResponseDTO:
    """DTO for expense response."""

    id: UUID
    business_id: UUID
    expense_type: str
    amount: Decimal
    reason: str
    user_id: UUID
    approved_by: UUID | None
    is_approved: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class SalaryCreateDTO:
    """DTO for creating a salary."""

    user_id: UUID
    amount: Decimal
    currency: str = "USD"
    payment_frequency: str = "monthly"  # daily, weekly, monthly
    deductions: Decimal = Decimal("0.00")
    bonuses: Decimal = Decimal("0.00")
    effective_from: datetime | None = None


@dataclass
class SalaryUpdateDTO:
    """DTO for updating a salary."""

    amount: Decimal | None = None
    currency: str | None = None
    payment_frequency: str | None = None
    deductions: Decimal | None = None
    bonuses: Decimal | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None


@dataclass
class SalaryPromotionDTO:
    """DTO for promoting an employee (creating new salary)."""

    new_amount: Decimal
    currency: str = "USD"
    payment_frequency: str = "monthly"
    deductions: Decimal = Decimal("0.00")
    bonuses: Decimal = Decimal("0.00")
    effective_from: datetime | None = None
    reason: str | None = None


@dataclass
class SalaryResponseDTO:
    """DTO for salary response."""

    id: UUID
    business_id: UUID
    user_id: UUID
    amount: Decimal
    currency: str
    payment_frequency: str
    deductions: Decimal
    bonuses: Decimal
    net_salary: Decimal
    effective_from: datetime
    effective_to: datetime | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class PayrollCreateDTO:
    """DTO for creating a payroll payment."""

    user_id: UUID
    salary_id: UUID
    amount: Decimal
    payment_date: datetime | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    deductions: Decimal = Decimal("0.00")
    bonuses: Decimal = Decimal("0.00")


@dataclass
class PayrollResponseDTO:
    """DTO for payroll response."""

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
class ExpenseCategoryStatsDTO:
    """DTO for expense category statistics."""

    expense_type: str
    total_amount: Decimal
    count: int
    average_amount: Decimal
    percentage_of_total: Decimal
