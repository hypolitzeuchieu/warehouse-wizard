"""Subscription domain Django models."""

from __future__ import annotations

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from infrastructure.persistence.models.base_model import BaseModel
from infrastructure.persistence.models.business_models import Business


class SubscriptionPlan(BaseModel):
    """Subscription plan model."""

    name = models.CharField(max_length=100)
    code = models.CharField(
        max_length=50, unique=True, help_text="e.g., 'basic', 'pro'"
    )
    description = models.TextField(null=True, blank=True)
    monthly_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Monthly subscription price",
    )
    annual_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Annual subscription price",
    )
    features = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON field for plan features (e.g., max_users, max_products)",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "subscription_plans"
        verbose_name = "Subscription Plan"
        verbose_name_plural = "Subscription Plans"
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class Subscription(BaseModel):
    """Subscription model."""

    STATUS_CHOICES = [
        ("trial", "Trial"),
        ("active", "Active"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled"),
        ("suspended", "Suspended"),
    ]

    BILLING_PERIOD_CHOICES = [
        ("monthly", "Monthly"),
        ("annual", "Annual"),
    ]

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="subscriptions",
        db_column="business_id",
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
        db_column="plan_id",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="trial")
    billing_period = models.CharField(max_length=20, choices=BILLING_PERIOD_CHOICES)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    trial_end_date = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(null=True, blank=True)
    external_subscription_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="External subscription ID (e.g., Stripe subscription ID)",
    )

    class Meta:
        db_table = "subscriptions"
        verbose_name = "Subscription"
        verbose_name_plural = "Subscriptions"
        indexes = [
            models.Index(fields=["business", "-created_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["external_subscription_id"]),
            models.Index(fields=["end_date"]),
            models.Index(fields=["trial_end_date"]),
        ]

    def __str__(self) -> str:
        return f"Subscription {self.id} - {self.business.name} ({self.status})"


class PaymentTransaction(BaseModel):
    """Payment transaction model."""

    PROVIDER_CHOICES = [
        ("stripe", "Stripe"),
        ("mtn_mobile_money", "MTN Mobile Money"),
        ("orange_mobile_money", "Orange Mobile Money"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
        ("refunded", "Refunded"),
    ]

    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="payment_transactions",
        db_column="subscription_id",
    )
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES)
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    currency = models.CharField(max_length=10, default="XAF")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    external_transaction_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="External transaction ID (e.g., Stripe payment intent ID, Mobile Money transaction ID)",
    )
    provider_response = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON field for provider-specific response data",
    )
    failure_reason = models.TextField(null=True, blank=True)
    initiated_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    idempotency_key = models.UUIDField(
        null=True,
        blank=True,
        unique=True,
        help_text="Prevents duplicate payments if payment is retried",
    )

    class Meta:
        db_table = "payment_transactions"
        verbose_name = "Payment Transaction"
        verbose_name_plural = "Payment Transactions"
        indexes = [
            models.Index(fields=["subscription", "-created_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["provider"]),
            models.Index(fields=["external_transaction_id"]),
            models.Index(fields=["idempotency_key"]),
        ]

    def __str__(self) -> str:
        return (
            f"Payment {self.amount} {self.currency} - {self.provider} ({self.status})"
        )
