"""Credit domain Django models."""

from __future__ import annotations

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from infrastructure.persistence.models.base_model import BaseModel
from infrastructure.persistence.models.business_models import Business
from infrastructure.persistence.models.customer_models import Customer
from infrastructure.persistence.models.sales_models import Invoice
from infrastructure.persistence.models.user_models import RetailPulseUser


class Credit(BaseModel):
    """Credit model for customer debts."""

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("OVERDUE", "Overdue"),
        ("PARTIALLY_PAID", "Partially Paid"),
        ("SETTLED", "Settled"),
        ("CANCELLED", "Cancelled"),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="credits")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="credits")
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="credits",
    )
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    paid_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))
    remaining_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))
    due_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    notes = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(
        RetailPulseUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_credits",
    )

    class Meta:
        db_table = "credits"
        verbose_name = "Credit"
        verbose_name_plural = "Credits"
        indexes = [
            models.Index(fields=["business", "customer"]),
            models.Index(fields=["status"]),
            models.Index(fields=["due_date"]),
            models.Index(fields=["business", "status"]),
        ]

    def __str__(self) -> str:
        return f"Credit {self.id} - {self.customer.name} - {self.amount}"

    def is_overdue(self) -> bool:
        """Check if credit is overdue."""
        from django.utils import timezone

        return self.status not in ["SETTLED", "CANCELLED"] and timezone.now() > self.due_date


class CreditPayment(BaseModel):
    """Credit payment model."""

    credit = models.ForeignKey(Credit, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    payment_date = models.DateTimeField()
    payment_method = models.CharField(max_length=30, default="cash")
    notes = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(
        RetailPulseUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_credit_payments",
    )

    class Meta:
        db_table = "credit_payments"
        verbose_name = "Credit Payment"
        verbose_name_plural = "Credit Payments"
        indexes = [
            models.Index(fields=["credit", "-payment_date"]),
            models.Index(fields=["payment_date"]),
        ]

    def __str__(self) -> str:
        return f"Payment {self.amount} for Credit {self.credit.id}"
