"""Finance repository implementations."""

from datetime import datetime
from uuid import UUID

from django.db import models

from domain.finance.entities import (
    Expense,
    ExpenseType,
    FinancialSummary,
    Payroll,
    Salary,
)
from domain.finance.repositories import (
    ExpenseRepository,
    FinancialSummaryRepository,
    PayrollRepository,
    SalaryRepository,
)
from infrastructure.persistence.models.finance_models import (
    Expense as ExpenseModel,
)
from infrastructure.persistence.models.finance_models import (
    FinancialSummary as FinancialSummaryModel,
)
from infrastructure.persistence.models.finance_models import (
    Payroll as PayrollModel,
)
from infrastructure.persistence.models.finance_models import (
    Salary as SalaryModel,
)


class ExpenseRepositoryImpl(ExpenseRepository):
    """Django implementation of ExpenseRepository."""

    def get_by_id(self, expense_id: UUID) -> Expense | None:
        """Get expense by ID."""
        try:
            expense_model = ExpenseModel.objects.select_related(
                "business", "user", "approved_by"
            ).get(id=expense_id)
            return self._to_entity(expense_model)
        except ExpenseModel.DoesNotExist:
            return None

    def get_by_business(
        self,
        business_id: UUID,
        expense_type: ExpenseType | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> list[Expense]:
        """Get expenses for a business with optional filters."""
        query = ExpenseModel.objects.filter(business_id=business_id).select_related(
            "user", "approved_by"
        )

        if expense_type:
            query = query.filter(expense_type=expense_type.value)

        if start_date:
            query = query.filter(created_at__gte=start_date)

        if end_date:
            query = query.filter(created_at__lte=end_date)

        expenses = query.order_by("-created_at")[:limit]
        return [self._to_entity(expense) for expense in expenses]

    def create(self, expense: Expense) -> Expense:
        """Create a new expense."""
        expense_model = ExpenseModel(
            id=expense.id,
            business_id=expense.business_id,
            expense_type=expense.expense_type.value,
            amount=expense.amount,
            reason=expense.reason,
            user_id=expense.user_id,
            approved_by_id=expense.approved_by,
            is_approved=expense.is_approved,
        )
        expense_model.save()
        return self._to_entity(expense_model)

    def update(self, expense: Expense) -> Expense:
        """Update an existing expense."""
        expense_model = ExpenseModel.objects.get(id=expense.id)
        expense_model.expense_type = expense.expense_type.value
        expense_model.amount = expense.amount
        expense_model.reason = expense.reason
        expense_model.approved_by_id = expense.approved_by
        expense_model.is_approved = expense.is_approved
        expense_model.save()
        return self._to_entity(expense_model)

    def delete(self, expense_id: UUID) -> None:
        """Delete an expense."""
        ExpenseModel.objects.filter(id=expense_id).delete()

    def _to_entity(self, expense_model: ExpenseModel) -> Expense:
        """Convert Django model to domain entity."""
        return Expense(
            id=expense_model.id,
            business_id=expense_model.business_id,
            expense_type=ExpenseType(expense_model.expense_type),
            amount=expense_model.amount,
            reason=expense_model.reason,
            user_id=expense_model.user_id,
            approved_by=expense_model.approved_by_id,
            is_approved=expense_model.is_approved,
            created_at=expense_model.created_at,
            updated_at=expense_model.updated_at,
        )


class SalaryRepositoryImpl(SalaryRepository):
    """Django implementation of SalaryRepository."""

    def get_by_id(self, salary_id: UUID) -> Salary | None:
        """Get salary by ID."""
        try:
            salary_model = SalaryModel.objects.select_related("business", "user").get(id=salary_id)
            return self._to_entity(salary_model)
        except SalaryModel.DoesNotExist:
            return None

    def get_by_user(self, user_id: UUID) -> list[Salary]:
        """Get salary history for a user."""
        salaries = SalaryModel.objects.filter(user_id=user_id).select_related("business")
        return [self._to_entity(salary) for salary in salaries]

    def get_current_salary(self, business_id: UUID, user_id: UUID) -> Salary | None:
        """Get current active salary for a user."""
        now = datetime.utcnow()
        try:
            salary_model = (
                SalaryModel.objects.filter(
                    business_id=business_id,
                    user_id=user_id,
                    effective_from__lte=now,
                )
                .filter(models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=now))
                .order_by("-effective_from")
                .first()
            )
            if salary_model:
                return self._to_entity(salary_model)
            return None
        except SalaryModel.DoesNotExist:
            return None

    def create(self, salary: Salary) -> Salary:
        """Create a new salary record."""
        salary_model = SalaryModel(
            id=salary.id,
            business_id=salary.business_id,
            user_id=salary.user_id,
            amount=salary.amount,
            currency=salary.currency,
            payment_frequency=salary.payment_frequency,
            deductions=salary.deductions,
            bonuses=salary.bonuses,
            effective_from=salary.effective_from,
            effective_to=salary.effective_to,
        )
        salary_model.save()
        return self._to_entity(salary_model)

    def update(self, salary: Salary) -> Salary:
        """Update an existing salary record."""
        salary_model = SalaryModel.objects.get(id=salary.id)
        salary_model.amount = salary.amount
        salary_model.currency = salary.currency
        salary_model.payment_frequency = salary.payment_frequency
        salary_model.deductions = salary.deductions
        salary_model.bonuses = salary.bonuses
        salary_model.effective_from = salary.effective_from
        salary_model.effective_to = salary.effective_to
        salary_model.save()
        return self._to_entity(salary_model)

    def _to_entity(self, salary_model: SalaryModel) -> Salary:
        """Convert Django model to domain entity."""
        return Salary(
            id=salary_model.id,
            business_id=salary_model.business_id,
            user_id=salary_model.user_id,
            amount=salary_model.amount,
            currency=salary_model.currency,
            payment_frequency=salary_model.payment_frequency,
            deductions=salary_model.deductions,
            bonuses=salary_model.bonuses,
            effective_from=salary_model.effective_from,
            effective_to=salary_model.effective_to,
            created_at=salary_model.created_at,
            updated_at=salary_model.updated_at,
        )


class PayrollRepositoryImpl(PayrollRepository):
    """Django implementation of PayrollRepository."""

    def get_by_id(self, payroll_id: UUID) -> Payroll | None:
        """Get payroll by ID."""
        try:
            payroll_model = PayrollModel.objects.select_related("business", "user", "salary").get(
                id=payroll_id
            )
            return self._to_entity(payroll_model)
        except PayrollModel.DoesNotExist:
            return None

    def get_by_user(self, user_id: UUID, limit: int = 100) -> list[Payroll]:
        """Get payroll history for a user."""
        payrolls = (
            PayrollModel.objects.filter(user_id=user_id)
            .select_related("business", "salary")
            .order_by("-payment_date")[:limit]
        )
        return [self._to_entity(payroll) for payroll in payrolls]

    def get_by_business(
        self,
        business_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> list[Payroll]:
        """Get payroll records for a business."""
        query = PayrollModel.objects.filter(business_id=business_id).select_related(
            "user", "salary"
        )

        if start_date:
            query = query.filter(payment_date__gte=start_date)

        if end_date:
            query = query.filter(payment_date__lte=end_date)

        payrolls = query.order_by("-payment_date")[:limit]
        return [self._to_entity(payroll) for payroll in payrolls]

    def create(self, payroll: Payroll) -> Payroll:
        """Create a new payroll record."""
        payroll_model = PayrollModel(
            id=payroll.id,
            business_id=payroll.business_id,
            user_id=payroll.user_id,
            salary_id=payroll.salary_id,
            amount=payroll.amount,
            payment_date=payroll.payment_date,
            period_start=payroll.period_start,
            period_end=payroll.period_end,
            deductions=payroll.deductions,
            bonuses=payroll.bonuses,
            net_amount=payroll.net_amount,
        )
        payroll_model.save()
        return self._to_entity(payroll_model)

    def _to_entity(self, payroll_model: PayrollModel) -> Payroll:
        """Convert Django model to domain entity."""
        return Payroll(
            id=payroll_model.id,
            business_id=payroll_model.business_id,
            user_id=payroll_model.user_id,
            salary_id=payroll_model.salary_id,
            amount=payroll_model.amount,
            payment_date=payroll_model.payment_date,
            period_start=payroll_model.period_start,
            period_end=payroll_model.period_end,
            deductions=payroll_model.deductions,
            bonuses=payroll_model.bonuses,
            net_amount=payroll_model.net_amount,
            created_at=payroll_model.created_at,
            updated_at=payroll_model.updated_at,
        )


class FinancialSummaryRepositoryImpl(FinancialSummaryRepository):
    """Django implementation of FinancialSummaryRepository."""

    def get_by_business(
        self,
        business_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> FinancialSummary | None:
        """Get financial summary for a business in a period."""
        try:
            summary_model = FinancialSummaryModel.objects.get(
                business_id=business_id,
                period_start=start_date,
                period_end=end_date,
            )
            return self._to_entity(summary_model)
        except FinancialSummaryModel.DoesNotExist:
            return None

    def create(self, summary: FinancialSummary) -> FinancialSummary:
        """Create a new financial summary."""
        summary_model = FinancialSummaryModel(
            business_id=summary.business_id,
            period_start=summary.period_start,
            period_end=summary.period_end,
            total_revenue=summary.total_revenue,
            total_expenses=summary.total_expenses,
            total_salaries=summary.total_salaries,
            net_profit=summary.net_profit,
            tax_amount=summary.tax_amount,
        )
        summary_model.save()
        return self._to_entity(summary_model)

    def _to_entity(self, summary_model: FinancialSummaryModel) -> FinancialSummary:
        """Convert Django model to domain entity."""
        return FinancialSummary(
            business_id=summary_model.business_id,
            period_start=summary_model.period_start,
            period_end=summary_model.period_end,
            total_revenue=summary_model.total_revenue,
            total_expenses=summary_model.total_expenses,
            total_salaries=summary_model.total_salaries,
            net_profit=summary_model.net_profit,
            tax_amount=summary_model.tax_amount,
            created_at=summary_model.created_at,
        )
