"""Finance domain repositories (interfaces)."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from uuid import UUID

from domain.finance.entities import (
    Expense,
    ExpenseType,
    FinancialSummary,
    Payroll,
    Salary,
)


class ExpenseRepository(ABC):
    """Expense repository interface."""

    @abstractmethod
    def get_by_id(self, expense_id: UUID) -> Optional[Expense]:
        """Get expense by ID."""
        pass

    @abstractmethod
    def get_by_business(
        self,
        business_id: UUID,
        expense_type: Optional[ExpenseType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[Expense]:
        """Get expenses for a business with optional filters."""
        pass

    @abstractmethod
    def create(self, expense: Expense) -> Expense:
        """Create a new expense."""
        pass

    @abstractmethod
    def update(self, expense: Expense) -> Expense:
        """Update an existing expense."""
        pass

    @abstractmethod
    def delete(self, expense_id: UUID) -> None:
        """Delete an expense."""
        pass


class SalaryRepository(ABC):
    """Salary repository interface."""

    @abstractmethod
    def get_by_id(self, salary_id: UUID) -> Optional[Salary]:
        """Get salary by ID."""
        pass

    @abstractmethod
    def get_by_user(self, user_id: UUID) -> list[Salary]:
        """Get salary history for a user."""
        pass

    @abstractmethod
    def get_current_salary(
        self, business_id: UUID, user_id: UUID
    ) -> Optional[Salary]:
        """Get current active salary for a user."""
        pass

    @abstractmethod
    def create(self, salary: Salary) -> Salary:
        """Create a new salary record."""
        pass

    @abstractmethod
    def update(self, salary: Salary) -> Salary:
        """Update an existing salary record."""
        pass


class PayrollRepository(ABC):
    """Payroll repository interface."""

    @abstractmethod
    def get_by_id(self, payroll_id: UUID) -> Optional[Payroll]:
        """Get payroll by ID."""
        pass

    @abstractmethod
    def get_by_user(
        self, user_id: UUID, limit: int = 100
    ) -> list[Payroll]:
        """Get payroll history for a user."""
        pass

    @abstractmethod
    def get_by_business(
        self,
        business_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[Payroll]:
        """Get payroll records for a business."""
        pass

    @abstractmethod
    def create(self, payroll: Payroll) -> Payroll:
        """Create a new payroll record."""
        pass


class FinancialSummaryRepository(ABC):
    """Financial summary repository interface."""

    @abstractmethod
    def get_by_business(
        self,
        business_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[FinancialSummary]:
        """Get financial summary for a business in a period."""
        pass

    @abstractmethod
    def create(self, summary: FinancialSummary) -> FinancialSummary:
        """Create a new financial summary."""
        pass

