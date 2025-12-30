"""Subscription DTOs."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from domain.subscription.entities import (
    BillingPeriod,
    PaymentProvider,
    SubscriptionStatus,
    TransactionStatus,
)


@dataclass
class SubscriptionPlanResponseDTO:
    """DTO for subscription plan response."""

    id: UUID
    name: str
    code: str
    description: str | None
    monthly_price: Decimal
    annual_price: Decimal
    features: dict | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class SubscriptionCreateDTO:
    """DTO for creating a subscription."""

    business_id: UUID
    plan_id: UUID
    billing_period: BillingPeriod
    start_trial: bool = True


@dataclass
class SubscriptionResponseDTO:
    """DTO for subscription response."""

    id: UUID
    business_id: UUID
    plan_id: UUID
    plan: SubscriptionPlanResponseDTO | None
    status: SubscriptionStatus
    billing_period: BillingPeriod
    start_date: datetime
    end_date: datetime | None
    trial_end_date: datetime | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    external_subscription_id: str | None
    created_at: datetime
    updated_at: datetime
    is_active: bool
    days_until_expiry: int | None = None


@dataclass
class PaymentInitiateDTO:
    """DTO for initiating a payment."""

    subscription_id: UUID
    provider: PaymentProvider
    amount: Decimal
    currency: str = "XAF"  # Default currency for Mobile Money
    return_url: str | None = None
    cancel_url: str | None = None
    idempotency_key: UUID | None = None


@dataclass
class PaymentResponseDTO:
    """DTO for payment response."""

    id: UUID
    subscription_id: UUID
    provider: PaymentProvider
    amount: Decimal
    currency: str
    status: TransactionStatus
    external_transaction_id: str | None
    payment_url: str | None  # URL for redirect (Stripe checkout, Mobile Money)
    initiated_at: datetime
    completed_at: datetime | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime


@dataclass
class WebhookPayloadDTO:
    """DTO for webhook payload."""

    provider: PaymentProvider
    event_type: str
    payload: dict[str, Any]
    signature: str | None = None
    timestamp: datetime | None = None


@dataclass
class SubscriptionCancelDTO:
    """DTO for cancelling a subscription."""

    reason: str | None = None
    cancel_immediately: bool = False


@dataclass
class SubscriptionRenewDTO:
    """DTO for renewing a subscription."""

    billing_period: BillingPeriod | None = None  # If None, use current period
