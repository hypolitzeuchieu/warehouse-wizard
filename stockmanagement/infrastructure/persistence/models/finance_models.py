"""Finance domain Django models."""

from __future__ import annotations

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from infrastructure.persistence.models.base_model import BaseModel
from infrastructure.persistence.models.business_models import Business
from infrastructure.persistence.models.user_models import RetailPulseUser


class Expense(BaseModel):
    """Expense model."""

    EXPENSE_TYPES = [
        ("REPLENISHMENT", "Replenishment"),
        ("MISCELLANEOUS", "Miscellaneous"),
        ("ELECTRICITY", "Electricity Bill"),
        ("WATER", "Water Bill"),
        ("SALARY", "Salary"),
        ("EXTRA", "Extra"),
        ("MAINTENANCE", "Maintenance"),
        ("TAX", "Tax"),
        ("RENT", "Rent"),
    ]

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="expenses"
    )
    expense_type = models.CharField(max_length=20, choices=EXPENSE_TYPES)
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    reason = models.TextField()
    user = models.ForeignKey(
        RetailPulseUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_expenses",
    )
    approved_by = models.ForeignKey(
        RetailPulseUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_expenses",
    )
    is_approved = models.BooleanField(default=False)

    class Meta:
        db_table = "expenses"
        verbose_name = "Expense"
        verbose_name_plural = "Expenses"
        indexes = [
            models.Index(fields=["business", "-updated_at"]),
            models.Index(fields=["expense_type"]),
            models.Index(fields=["is_approved"]),
        ]

    def __str__(self) -> str:
        return f"{self.expense_type} - {self.amount} ({self.business.name})"


class Salary(BaseModel):
    """Employee salary model."""

    PAYMENT_FREQUENCY_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
    ]
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="salaries"
    )
    user = models.ForeignKey(
        RetailPulseUser, on_delete=models.CASCADE, related_name="salaries"
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    currency = models.CharField(max_length=10, default="USD")
    payment_frequency = models.CharField(
        max_length=20, choices=PAYMENT_FREQUENCY_CHOICES, default="monthly"
    )
    deductions = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    bonuses = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "salaries"
        verbose_name = "Salary"
        verbose_name_plural = "Salaries"
        indexes = [
            models.Index(fields=["business", "user"]),
            models.Index(fields=["effective_from", "effective_to"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.name or self.user.email} - {self.amount} {self.currency}"

    def calculate_net_salary(self) -> Decimal:
        """Calculate net salary."""
        return self.amount - self.deductions + self.bonuses


class Payroll(BaseModel):
    """Payroll model for salary payments."""
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="payrolls"
    )
    user = models.ForeignKey(
        RetailPulseUser, on_delete=models.CASCADE, related_name="payrolls"
    )
    salary = models.ForeignKey(
        Salary, on_delete=models.CASCADE, related_name="payrolls"
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    payment_date = models.DateTimeField()
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    deductions = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    bonuses = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    net_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        db_table = "payrolls"
        verbose_name = "Payroll"
        verbose_name_plural = "Payrolls"
        ordering = ["-updated_at"]  # Use BaseModel ordering
        indexes = [
            models.Index(fields=["business", "-updated_at"]),
            models.Index(fields=["user", "-updated_at"]),
        ]

    def __str__(self) -> str:
        return f"Payroll {self.id} - {self.user.name or self.user.email}"


class FinancialSummary(BaseModel):
    """Financial summary model."""
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="financial_summaries"
    )
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    total_revenue = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    total_expenses = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    total_salaries = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    net_profit = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    tax_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )

    class Meta:
        db_table = "financial_summaries"
        verbose_name = "Financial Summary"
        verbose_name_plural = "Financial Summaries"
        indexes = [
            models.Index(fields=["business", "period_start", "period_end"]),
        ]

    def __str__(self) -> str:
        return f"Financial Summary {self.business.name} - {self.period_start.date()}"

    def calculate_profit_margin(self) -> Decimal:
        """Calculate profit margin percentage."""
        if self.total_revenue == 0:
            return Decimal("0.00")
        return (self.net_profit / self.total_revenue) * 100

