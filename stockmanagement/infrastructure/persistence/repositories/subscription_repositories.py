"""Subscription repository implementations."""

from uuid import UUID

from django.utils import timezone

from domain.subscription.entities import (
    BillingPeriod,
    PaymentProvider,
    PaymentTransaction,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    TransactionStatus,
)
from domain.subscription.repositories import (
    PaymentTransactionRepository,
    SubscriptionPlanRepository,
    SubscriptionRepository,
)
from infrastructure.persistence.models.subscription_models import (
    PaymentTransaction as PaymentTransactionModel,
)
from infrastructure.persistence.models.subscription_models import (
    Subscription as SubscriptionModel,
)
from infrastructure.persistence.models.subscription_models import (
    SubscriptionPlan as SubscriptionPlanModel,
)


class SubscriptionPlanRepositoryImpl(SubscriptionPlanRepository):
    """Django implementation of SubscriptionPlanRepository."""

    def get_by_id(self, plan_id: UUID) -> SubscriptionPlan | None:
        """Get subscription plan by ID."""
        try:
            plan_model = SubscriptionPlanModel.objects.get(id=plan_id)
            return self._to_entity(plan_model)
        except SubscriptionPlanModel.DoesNotExist:
            return None

    def get_by_code(self, code: str) -> SubscriptionPlan | None:
        """Get subscription plan by code."""
        try:
            plan_model = SubscriptionPlanModel.objects.get(code=code)
            return self._to_entity(plan_model)
        except SubscriptionPlanModel.DoesNotExist:
            return None

    def get_all(self, active_only: bool = True) -> list[SubscriptionPlan]:
        """Get all subscription plans."""
        query = SubscriptionPlanModel.objects.all()
        if active_only:
            query = query.filter(is_active=True)
        plans = query.order_by("monthly_price")
        return [self._to_entity(plan) for plan in plans]

    def create(self, plan: SubscriptionPlan) -> SubscriptionPlan:
        """Create a new subscription plan."""
        plan_model = SubscriptionPlanModel(
            id=plan.id,
            name=plan.name,
            code=plan.code,
            description=plan.description,
            monthly_price=plan.monthly_price,
            annual_price=plan.annual_price,
            features=plan.features or {},
            is_active=plan.is_active,
        )
        plan_model.save()
        return self._to_entity(plan_model)

    def update(self, plan: SubscriptionPlan) -> SubscriptionPlan:
        """Update an existing subscription plan."""
        plan_model = SubscriptionPlanModel.objects.get(id=plan.id)
        plan_model.name = plan.name
        plan_model.code = plan.code
        plan_model.description = plan.description
        plan_model.monthly_price = plan.monthly_price
        plan_model.annual_price = plan.annual_price
        plan_model.features = plan.features or {}
        plan_model.is_active = plan.is_active
        plan_model.save()
        return self._to_entity(plan_model)

    def delete(self, plan_id: UUID) -> None:
        """Delete a subscription plan."""
        SubscriptionPlanModel.objects.filter(id=plan_id).delete()

    def _to_entity(self, plan_model: SubscriptionPlanModel) -> SubscriptionPlan:
        """Convert Django model to domain entity."""
        return SubscriptionPlan(
            id=plan_model.id,
            name=plan_model.name,
            code=plan_model.code,
            description=plan_model.description,
            monthly_price=plan_model.monthly_price,
            annual_price=plan_model.annual_price,
            features=plan_model.features,
            is_active=plan_model.is_active,
            created_at=plan_model.created_at,
            updated_at=plan_model.updated_at,
        )


class SubscriptionRepositoryImpl(SubscriptionRepository):
    """Django implementation of SubscriptionRepository."""

    def get_by_id(self, subscription_id: UUID) -> Subscription | None:
        """Get subscription by ID."""
        try:
            subscription_model = SubscriptionModel.objects.select_related(
                "business", "plan"
            ).get(id=subscription_id)
            return self._to_entity(subscription_model)
        except SubscriptionModel.DoesNotExist:
            return None

    def get_by_business(self, business_id: UUID) -> Subscription | None:
        """Get active subscription for a business."""
        try:
            subscription_model = (
                SubscriptionModel.objects.filter(business_id=business_id)
                .exclude(status=SubscriptionStatus.CANCELLED)
                .exclude(status=SubscriptionStatus.EXPIRED)
                .select_related("business", "plan")
                .order_by("-created_at")
                .first()
            )
            if subscription_model:
                return self._to_entity(subscription_model)
            return None
        except SubscriptionModel.DoesNotExist:
            return None

    def get_by_business_all(self, business_id: UUID) -> list[Subscription]:
        """Get all subscriptions for a business."""
        subscriptions = (
            SubscriptionModel.objects.filter(business_id=business_id)
            .select_related("business", "plan")
            .order_by("-created_at")
        )
        return [self._to_entity(sub) for sub in subscriptions]

    def get_by_external_id(self, external_id: str) -> Subscription | None:
        """Get subscription by external ID."""
        try:
            subscription_model = SubscriptionModel.objects.select_related(
                "business", "plan"
            ).get(external_subscription_id=external_id)
            return self._to_entity(subscription_model)
        except SubscriptionModel.DoesNotExist:
            return None

    def get_expired_subscriptions(self) -> list[Subscription]:
        """Get all expired subscriptions."""
        now = timezone.now()
        subscriptions = (
            SubscriptionModel.objects.filter(
                status=SubscriptionStatus.ACTIVE, end_date__lt=now
            )
            .select_related("business", "plan")
            .order_by("end_date")
        )
        return [self._to_entity(sub) for sub in subscriptions]

    def get_subscriptions_by_status(
        self, status: SubscriptionStatus
    ) -> list[Subscription]:
        """Get subscriptions by status."""
        subscriptions = (
            SubscriptionModel.objects.filter(status=status.value)
            .select_related("business", "plan")
            .order_by("-created_at")
        )
        return [self._to_entity(sub) for sub in subscriptions]

    def create(self, subscription: Subscription) -> Subscription:
        """Create a new subscription."""
        subscription_model = SubscriptionModel(
            id=subscription.id,
            business_id=subscription.business_id,
            plan_id=subscription.plan_id,
            status=subscription.status.value,
            billing_period=subscription.billing_period.value,
            start_date=subscription.start_date,
            end_date=subscription.end_date,
            trial_end_date=subscription.trial_end_date,
            cancelled_at=subscription.cancelled_at,
            cancellation_reason=subscription.cancellation_reason,
            external_subscription_id=subscription.external_subscription_id,
        )
        subscription_model.save()
        return self._to_entity(subscription_model)

    def update(self, subscription: Subscription) -> Subscription:
        """Update an existing subscription."""
        subscription_model = SubscriptionModel.objects.get(id=subscription.id)
        subscription_model.business_id = subscription.business_id
        subscription_model.plan_id = subscription.plan_id
        subscription_model.status = subscription.status.value
        subscription_model.billing_period = subscription.billing_period.value
        subscription_model.start_date = subscription.start_date
        subscription_model.end_date = subscription.end_date
        subscription_model.trial_end_date = subscription.trial_end_date
        subscription_model.cancelled_at = subscription.cancelled_at
        subscription_model.cancellation_reason = subscription.cancellation_reason
        subscription_model.external_subscription_id = (
            subscription.external_subscription_id
        )
        subscription_model.save()
        return self._to_entity(subscription_model)

    def delete(self, subscription_id: UUID) -> None:
        """Delete a subscription."""
        SubscriptionModel.objects.filter(id=subscription_id).delete()

    def _to_entity(self, subscription_model: SubscriptionModel) -> Subscription:
        """Convert Django model to domain entity."""

        return Subscription(
            id=subscription_model.id,
            business_id=subscription_model.business_id,
            plan_id=subscription_model.plan_id,
            status=SubscriptionStatus(subscription_model.status),
            billing_period=BillingPeriod(subscription_model.billing_period),
            start_date=subscription_model.start_date,
            end_date=subscription_model.end_date,
            trial_end_date=subscription_model.trial_end_date,
            cancelled_at=subscription_model.cancelled_at,
            cancellation_reason=subscription_model.cancellation_reason,
            created_at=subscription_model.created_at,
            updated_at=subscription_model.updated_at,
            external_subscription_id=subscription_model.external_subscription_id,
        )


class PaymentTransactionRepositoryImpl(PaymentTransactionRepository):
    """Django implementation of PaymentTransactionRepository."""

    def get_by_id(self, transaction_id: UUID) -> PaymentTransaction | None:
        """Get payment transaction by ID."""
        try:
            transaction_model = PaymentTransactionModel.objects.select_related(
                "subscription"
            ).get(id=transaction_id)
            return self._to_entity(transaction_model)
        except PaymentTransactionModel.DoesNotExist:
            return None

    def get_by_subscription(self, subscription_id: UUID) -> list[PaymentTransaction]:
        """Get all transactions for a subscription."""
        transactions = (
            PaymentTransactionModel.objects.filter(subscription_id=subscription_id)
            .select_related("subscription")
            .order_by("-created_at")
        )
        return [self._to_entity(transaction) for transaction in transactions]

    def get_by_external_id(
        self, external_id: str, provider: str
    ) -> PaymentTransaction | None:
        """Get transaction by external ID and provider."""
        try:
            transaction_model = PaymentTransactionModel.objects.select_related(
                "subscription"
            ).get(external_transaction_id=external_id, provider=provider)
            return self._to_entity(transaction_model)
        except PaymentTransactionModel.DoesNotExist:
            return None

    def get_by_idempotency_key(
        self, idempotency_key: UUID
    ) -> PaymentTransaction | None:
        """Get transaction by idempotency key."""
        try:
            transaction_model = PaymentTransactionModel.objects.select_related(
                "subscription"
            ).get(idempotency_key=idempotency_key)
            return self._to_entity(transaction_model)
        except PaymentTransactionModel.DoesNotExist:
            return None

    def get_transactions_by_status(
        self, status: TransactionStatus
    ) -> list[PaymentTransaction]:
        """Get transactions by status."""
        transactions = (
            PaymentTransactionModel.objects.filter(status=status.value)
            .select_related("subscription")
            .order_by("-created_at")
        )
        return [self._to_entity(transaction) for transaction in transactions]

    def create(self, transaction: PaymentTransaction) -> PaymentTransaction:
        """Create a new payment transaction."""
        transaction_model = PaymentTransactionModel(
            id=transaction.id,
            subscription_id=transaction.subscription_id,
            provider=transaction.provider.value,
            amount=transaction.amount,
            currency=transaction.currency,
            status=transaction.status.value,
            external_transaction_id=transaction.external_transaction_id,
            provider_response=transaction.provider_response or {},
            failure_reason=transaction.failure_reason,
            initiated_at=transaction.initiated_at,
            completed_at=transaction.completed_at,
            idempotency_key=transaction.idempotency_key,
        )
        transaction_model.save()
        return self._to_entity(transaction_model)

    def update(self, transaction: PaymentTransaction) -> PaymentTransaction:
        """Update an existing payment transaction."""
        transaction_model = PaymentTransactionModel.objects.get(id=transaction.id)
        transaction_model.subscription_id = transaction.subscription_id
        transaction_model.provider = transaction.provider.value
        transaction_model.amount = transaction.amount
        transaction_model.currency = transaction.currency
        transaction_model.status = transaction.status.value
        transaction_model.external_transaction_id = transaction.external_transaction_id
        transaction_model.provider_response = transaction.provider_response or {}
        transaction_model.failure_reason = transaction.failure_reason
        transaction_model.initiated_at = transaction.initiated_at
        transaction_model.completed_at = transaction.completed_at
        transaction_model.idempotency_key = transaction.idempotency_key
        transaction_model.save()
        return self._to_entity(transaction_model)

    def _to_entity(
        self, transaction_model: PaymentTransactionModel
    ) -> PaymentTransaction:
        """Convert Django model to domain entity."""

        return PaymentTransaction(
            id=transaction_model.id,
            subscription_id=transaction_model.subscription_id,
            provider=PaymentProvider(transaction_model.provider),
            amount=transaction_model.amount,
            currency=transaction_model.currency,
            status=TransactionStatus(transaction_model.status),
            external_transaction_id=transaction_model.external_transaction_id,
            provider_response=transaction_model.provider_response,
            failure_reason=transaction_model.failure_reason,
            initiated_at=transaction_model.initiated_at,
            completed_at=transaction_model.completed_at,
            created_at=transaction_model.created_at,
            updated_at=transaction_model.updated_at,
            idempotency_key=transaction_model.idempotency_key,
        )
