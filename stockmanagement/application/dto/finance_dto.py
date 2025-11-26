"""Finance DTOs."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


@dataclass
class ExpenseCreateDTO:
    """DTO for creating an expense."""

    expense_type: str
    amount: Decimal
    reason: str
    reason_details: str
    payment_method: str
    payment_reference: str | None
    payee_type: str
    payee_name: str
    justification_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExpenseUpdateDTO:
    """DTO for updating an expense."""

    expense_type: str | None = None
    amount: Decimal | None = None
    reason: str | None = None
    reason_details: str | None = None
    is_approved: bool | None = None
    payment_method: str | None = None
    payment_reference: str | None = None
    payee_type: str | None = None
    payee_name: str | None = None
    justification_metadata: dict[str, Any] | None = None


@dataclass
class ExpenseResponseDTO:
    """DTO for expense response."""

    id: UUID
    business_id: UUID
    expense_type: str
    amount: Decimal
    reason: str
    reason_details: str | None
    user_id: UUID
    user_name: str | None
    approved_by: UUID | None
    is_approved: bool
    payment_method: str
    payment_reference: str | None
    payee_type: str
    payee_name: str | None
    justification_metadata: dict[str, Any]
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


@dataclass
class MonthlyExpenseStatDTO:
    """DTO describing aggregated expense per month."""

    month: datetime
    total_amount: Decimal
    count: int


@dataclass
class ExpenseSummaryDTO:
    """DTO for aggregated expense summary."""

    business_id: UUID
    total_amount: Decimal
    total_count: int
    by_type: list[ExpenseCategoryStatsDTO]
    by_payment_method: dict[str, Decimal]
    monthly_stats: list[MonthlyExpenseStatDTO]


@dataclass
class ExpenseAuditLogDTO:
    """DTO for returning expense audit history."""

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
    payment_method_before: str | None
    payment_method_after: str | None
    payee_type_before: str | None
    payee_type_after: str | None
    payee_name_before: str | None
    payee_name_after: str | None
    justification_snapshot: dict[str, Any]
    created_at: datetime
