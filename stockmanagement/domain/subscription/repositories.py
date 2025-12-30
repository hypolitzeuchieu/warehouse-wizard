"""Subscription domain repositories (interfaces)."""

from abc import ABC, abstractmethod
from uuid import UUID

from domain.subscription.entities import (
    PaymentTransaction,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    TransactionStatus,
)


class SubscriptionPlanRepository(ABC):
    """Subscription plan repository interface."""

    @abstractmethod
    def get_by_id(self, plan_id: UUID) -> SubscriptionPlan | None:
        """Get subscription plan by ID."""
        pass

    @abstractmethod
    def get_by_code(self, code: str) -> SubscriptionPlan | None:
        """Get subscription plan by code."""
        pass

    @abstractmethod
    def get_all(self, active_only: bool = True) -> list[SubscriptionPlan]:
        """Get all subscription plans."""
        pass

    @abstractmethod
    def create(self, plan: SubscriptionPlan) -> SubscriptionPlan:
        """Create a new subscription plan."""
        pass

    @abstractmethod
    def update(self, plan: SubscriptionPlan) -> SubscriptionPlan:
        """Update an existing subscription plan."""
        pass

    @abstractmethod
    def delete(self, plan_id: UUID) -> None:
        """Delete a subscription plan."""
        pass


class SubscriptionRepository(ABC):
    """Subscription repository interface."""

    @abstractmethod
    def get_by_id(self, subscription_id: UUID) -> Subscription | None:
        """Get subscription by ID."""
        pass

    @abstractmethod
    def get_by_business(self, business_id: UUID) -> Subscription | None:
        """Get active subscription for a business."""
        pass

    @abstractmethod
    def get_by_business_all(self, business_id: UUID) -> list[Subscription]:
        """Get all subscriptions for a business."""
        pass

    @abstractmethod
    def get_by_external_id(self, external_id: str) -> Subscription | None:
        """Get subscription by external ID (e.g., Stripe subscription ID)."""
        pass

    @abstractmethod
    def get_expired_subscriptions(self) -> list[Subscription]:
        """Get all expired subscriptions."""
        pass

    @abstractmethod
    def get_subscriptions_by_status(
        self, status: SubscriptionStatus
    ) -> list[Subscription]:
        """Get subscriptions by status."""
        pass

    @abstractmethod
    def create(self, subscription: Subscription) -> Subscription:
        """Create a new subscription."""
        pass

    @abstractmethod
    def update(self, subscription: Subscription) -> Subscription:
        """Update an existing subscription."""
        pass

    @abstractmethod
    def delete(self, subscription_id: UUID) -> None:
        """Delete a subscription."""
        pass


class PaymentTransactionRepository(ABC):
    """Payment transaction repository interface."""

    @abstractmethod
    def get_by_id(self, transaction_id: UUID) -> PaymentTransaction | None:
        """Get payment transaction by ID."""
        pass

    @abstractmethod
    def get_by_subscription(self, subscription_id: UUID) -> list[PaymentTransaction]:
        """Get all transactions for a subscription."""
        pass

    @abstractmethod
    def get_by_external_id(
        self, external_id: str, provider: str
    ) -> PaymentTransaction | None:
        """Get transaction by external ID and provider."""
        pass

    @abstractmethod
    def get_by_idempotency_key(
        self, idempotency_key: UUID
    ) -> PaymentTransaction | None:
        """Get transaction by idempotency key."""
        pass

    @abstractmethod
    def get_transactions_by_status(
        self, status: TransactionStatus
    ) -> list[PaymentTransaction]:
        """Get transactions by status."""
        pass

    @abstractmethod
    def create(self, transaction: PaymentTransaction) -> PaymentTransaction:
        """Create a new payment transaction."""
        pass

    @abstractmethod
    def update(self, transaction: PaymentTransaction) -> PaymentTransaction:
        """Update an existing payment transaction."""
        pass
