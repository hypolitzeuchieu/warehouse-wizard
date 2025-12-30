"""Subscription domain services."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.utils import timezone

from domain.business.repositories import BusinessRepository
from domain.subscription.entities import (
    PaymentTransaction,
    Subscription,
    SubscriptionStatus,
    TransactionStatus,
)
from domain.subscription.repositories import SubscriptionRepository

logger = logging.getLogger(__name__)


class SubscriptionDomainService:
    """
    Domain service for managing subscriptions.

    This service handles subscription business logic including:
    - Checking subscription expiration
    - Activating/deactivating businesses based on subscription status
    - Managing trial periods
    - Calculating subscription renewal dates
    """

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        business_repository: BusinessRepository,
    ) -> None:
        """Initialize subscription domain service."""
        self.subscription_repository = subscription_repository
        self.business_repository = business_repository

    def is_business_subscription_active(self, business_id: UUID) -> bool:
        """Check if business has an active subscription."""
        subscription = self.subscription_repository.get_by_business(business_id)
        if not subscription:
            return False
        return subscription.is_active()

    def check_and_update_expired_subscriptions(self) -> list[Subscription]:
        """
        Check for expired subscriptions and update their status.

        Returns:
            List of subscriptions that were expired
        """
        expired_subscriptions = self.subscription_repository.get_expired_subscriptions()
        updated_subscriptions = []

        now = timezone.now()
        for subscription in expired_subscriptions:
            if subscription.status == SubscriptionStatus.ACTIVE:
                # Check if subscription has actually expired
                if subscription.end_date and now > subscription.end_date:
                    subscription.status = SubscriptionStatus.EXPIRED
                    subscription.updated_at = now
                    subscription = self.subscription_repository.update(subscription)
                    updated_subscriptions.append(subscription)
                    logger.info(
                        f"Subscription {subscription.id} expired for business {subscription.business_id}"
                    )

        return updated_subscriptions

    def deactivate_businesses_with_expired_subscriptions(self) -> list[UUID]:
        """
        Deactivate businesses that have expired subscriptions.

        Returns:
            List of business IDs that were deactivated
        """
        expired_subscriptions = (
            self.subscription_repository.get_subscriptions_by_status(
                SubscriptionStatus.EXPIRED
            )
        )
        deactivated_businesses = []

        for subscription in expired_subscriptions:
            business = self.business_repository.get_by_id(subscription.business_id)
            if business and business.is_active:
                business.is_active = False
                business.updated_at = timezone.now()
                self.business_repository.update(business)
                deactivated_businesses.append(business.id)
                logger.info(
                    f"Business {business.id} deactivated due to expired subscription"
                )

        return deactivated_businesses

    def calculate_subscription_end_date(
        self, start_date: datetime, billing_period: str, trial_days: int = 0
    ) -> datetime:
        """
        Calculate subscription end date based on billing period.

        Args:
            start_date: Subscription start date
            billing_period: 'monthly' or 'annual'
            trial_days: Number of trial days (if any)

        Returns:
            End date for the subscription
        """
        if billing_period == "monthly":
            delta = timedelta(days=30)
        elif billing_period == "annual":
            delta = timedelta(days=365)
        else:
            raise ValueError(f"Invalid billing period: {billing_period}")

        if trial_days > 0:
            delta += timedelta(days=trial_days)

        return start_date + delta

    def calculate_trial_end_date(
        self, start_date: datetime, trial_days: int
    ) -> datetime:
        """Calculate trial end date."""
        return start_date + timedelta(days=trial_days)

    def can_business_access_features(self, business_id: UUID) -> bool:
        """
        Check if business can access features based on subscription.

        Returns:
            True if business has active subscription or is in trial period
        """
        subscription = self.subscription_repository.get_by_business(business_id)
        if not subscription:
            return False

        # Check if subscription is active or in trial
        if subscription.is_active() or subscription.is_trial():
            return True

        return False

    def get_subscription_status_for_business(
        self, business_id: UUID
    ) -> SubscriptionStatus | None:
        """Get subscription status for a business."""
        subscription = self.subscription_repository.get_by_business(business_id)
        if not subscription:
            return None
        return subscription.status


class PaymentValidationService:
    """Service for validating payment transactions."""

    @staticmethod
    def validate_payment_amount(
        amount: Decimal, expected_amount: Decimal
    ) -> dict[str, Any]:
        """
        Validate payment amount matches expected amount.

        Args:
            amount: Payment amount received
            expected_amount: Expected payment amount

        Returns:
            Dictionary with validation result
        """
        if amount <= 0:
            return {
                "is_valid": False,
                "errors": ["Payment amount must be greater than zero"],
            }

        if amount != expected_amount:
            return {
                "is_valid": False,
                "errors": [
                    f"Payment amount {amount} does not match expected amount {expected_amount}"
                ],
            }

        return {"is_valid": True, "errors": []}

    @staticmethod
    def validate_transaction_status(transaction: PaymentTransaction) -> bool:
        """Validate transaction status is valid for processing."""
        if transaction.status == TransactionStatus.COMPLETED:
            return True
        if transaction.status == TransactionStatus.FAILED:
            return False
        if transaction.status == TransactionStatus.CANCELLED:
            return False
        return transaction.status in (
            TransactionStatus.PENDING,
            TransactionStatus.PROCESSING,
        )

    @staticmethod
    def can_process_payment(transaction: PaymentTransaction) -> bool:
        """Check if payment transaction can be processed."""
        if transaction.is_completed():
            return False  # Already completed
        if transaction.is_failed():
            return False  # Already failed
        return transaction.is_pending()
