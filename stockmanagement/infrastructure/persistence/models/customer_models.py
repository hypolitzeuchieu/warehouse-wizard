"""Customer domain Django models."""

from __future__ import annotations

from decimal import Decimal

from django.db import models

from infrastructure.persistence.models.base_model import BaseModel
from infrastructure.persistence.models.business_models import Business


class Customer(BaseModel):
    """Customer model."""

    CUSTOMER_TYPE_CHOICES = [
        ("REGULAR", "Regular"),
        ("WHOLESALER", "Wholesaler"),
    ]

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="customers",
    )
    name = models.CharField(max_length=255)
    email = models.EmailField(null=True, blank=True)
    phone_number = models.CharField(max_length=30, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    customer_type = models.CharField(
        max_length=20, choices=CUSTOMER_TYPE_CHOICES, default="REGULAR"
    )
    loyalty_points = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))
    total_purchases = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        db_table = "customers"
        verbose_name = "Customer"
        verbose_name_plural = "Customers"
        indexes = [
            models.Index(fields=["business", "name"]),
            models.Index(fields=["email"]),
            models.Index(fields=["phone_number"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.business.name if self.business else 'Platform'})"


class CustomerPurchaseHistory(BaseModel):
    """Customer purchase history model."""

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="purchase_history"
    )
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="customer_purchases"
    )
    invoice = models.ForeignKey(
        "Invoice",
        on_delete=models.CASCADE,
        related_name="customer_purchase_history",
    )
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    purchase_date = models.DateTimeField()

    class Meta:
        db_table = "customer_purchase_history"
        verbose_name = "Customer Purchase History"
        verbose_name_plural = "Customer Purchase Histories"
        ordering = ["-updated_at"]  # Use BaseModel ordering
        indexes = [
            models.Index(fields=["customer", "-purchase_date"]),
            models.Index(fields=["business", "-purchase_date"]),
        ]

    def __str__(self) -> str:
        return f"{self.customer.name} - {self.total_amount} ({self.purchase_date.date()})"
