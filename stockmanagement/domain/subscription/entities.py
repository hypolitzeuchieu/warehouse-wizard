"""Subscription domain entities."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID


class SubscriptionStatus(str, Enum):
    """Subscription status enumeration."""

    TRIAL = "trial"
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"


class BillingPeriod(str, Enum):
    """Billing period enumeration."""

    MONTHLY = "monthly"
    ANNUAL = "annual"


class PaymentProvider(str, Enum):
    """Payment provider enumeration."""

    STRIPE = "stripe"
    MTN_MOBILE_MONEY = "mtn_mobile_money"
    ORANGE_MOBILE_MONEY = "orange_mobile_money"


class TransactionStatus(str, Enum):
    """Payment transaction status enumeration."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


@dataclass
class SubscriptionPlan:
    """Subscription plan entity."""

    id: UUID
    name: str
    code: str  # e.g., "basic", "pro"
    description: str | None
    monthly_price: Decimal
    annual_price: Decimal
    features: dict | None  # JSON field for plan features
    is_active: bool
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        """Validate subscription plan data."""
        if not self.name:
            raise ValueError("Plan name is required")
        if not self.code:
            raise ValueError("Plan code is required")
        if self.monthly_price < 0:
            raise ValueError("Monthly price cannot be negative")
        if self.annual_price < 0:
            raise ValueError("Annual price cannot be negative")

    def get_price(self, period: BillingPeriod) -> Decimal:
        """Get price for a specific billing period."""
        if period == BillingPeriod.MONTHLY:
            return self.monthly_price
        return self.annual_price


@dataclass
class Subscription:
    """Subscription entity."""

    id: UUID
    business_id: UUID
    plan_id: UUID
    status: SubscriptionStatus
    billing_period: BillingPeriod
    start_date: datetime
    end_date: datetime | None
    trial_end_date: datetime | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    created_at: datetime
    updated_at: datetime
    external_subscription_id: str | None = None  # Stripe subscription ID, etc.

    def __post_init__(self) -> None:
        """Validate subscription data."""
        if (
            self.trial_end_date
            and self.start_date
            and self.trial_end_date < self.start_date
        ):
            raise ValueError("Trial end date cannot be before start date")
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValueError("End date cannot be before start date")

    def is_active(self) -> bool:
        """Check if subscription is currently active."""
        if self.status == SubscriptionStatus.CANCELLED:
            return False
        if self.status == SubscriptionStatus.EXPIRED:
            return False
        if self.status == SubscriptionStatus.SUSPENDED:
            return False

        now = (
            datetime.now(self.start_date.tzinfo)
            if self.start_date.tzinfo
            else datetime.now()
        )

        # Check if in trial period
        if self.status == SubscriptionStatus.TRIAL and self.trial_end_date:
            return now <= self.trial_end_date

        # Check if subscription has ended
        if self.end_date and now > self.end_date:
            return False

        return self.status == SubscriptionStatus.ACTIVE

    def is_trial(self) -> bool:
        """Check if subscription is in trial period."""
        if self.status != SubscriptionStatus.TRIAL:
            return False
        if not self.trial_end_date:
            return False

        now = (
            datetime.now(self.trial_end_date.tzinfo)
            if self.trial_end_date.tzinfo
            else datetime.now()
        )
        return now <= self.trial_end_date

    def days_until_expiry(self) -> int | None:
        """Get number of days until subscription expires."""
        if not self.end_date:
            return None

        now = (
            datetime.now(self.end_date.tzinfo)
            if self.end_date.tzinfo
            else datetime.now()
        )
        if now > self.end_date:
            return 0

        delta = self.end_date - now
        return delta.days


@dataclass
class PaymentTransaction:
    """Payment transaction entity."""

    id: UUID
    subscription_id: UUID
    provider: PaymentProvider
    amount: Decimal
    currency: str
    status: TransactionStatus
    external_transaction_id: (
        str | None
    )  # Stripe payment intent ID, Mobile Money transaction ID
    provider_response: dict | None  # JSON field for provider-specific response
    failure_reason: str | None
    initiated_at: datetime
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    idempotency_key: UUID | None = None

    def __post_init__(self) -> None:
        """Validate payment transaction data."""
        if self.amount <= 0:
            raise ValueError("Payment amount must be greater than zero")
        if not self.currency:
            raise ValueError("Currency is required")
        if (
            self.completed_at
            and self.initiated_at
            and self.completed_at < self.initiated_at
        ):
            raise ValueError("Completed date cannot be before initiated date")

    def is_completed(self) -> bool:
        """Check if transaction is completed."""
        return self.status == TransactionStatus.COMPLETED

    def is_failed(self) -> bool:
        """Check if transaction failed."""
        return self.status == TransactionStatus.FAILED

    def is_pending(self) -> bool:
        """Check if transaction is pending."""
        return self.status in (TransactionStatus.PENDING, TransactionStatus.PROCESSING)
