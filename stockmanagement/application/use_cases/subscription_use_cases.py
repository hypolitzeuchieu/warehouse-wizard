"""Subscription use cases."""

import logging
from decimal import Decimal
from uuid import UUID, uuid4

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from application.dto.subscription_dto import (
    PaymentInitiateDTO,
    PaymentResponseDTO,
    SubscriptionCancelDTO,
    SubscriptionCreateDTO,
    SubscriptionPlanResponseDTO,
    SubscriptionRenewDTO,
    SubscriptionResponseDTO,
    WebhookPayloadDTO,
)
from domain.business.repositories import BusinessRepository
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
from domain.subscription.services import (
    PaymentValidationService,
    SubscriptionDomainService,
)
from infrastructure.external.payment_providers import (
    MTNMobileMoneyService,
    OrangeMobileMoneyService,
    PaymentProviderInterface,
    StripeService,
)
from shared.exceptions.specific import BadRequestError, ForbiddenError, NotFoundError

logger = logging.getLogger(__name__)

# Get trial days from settings, default to 14
TRIAL_DAYS = getattr(settings, "SUBSCRIPTION_TRIAL_DAYS", 14)


def _subscription_plan_to_dto(plan: SubscriptionPlan) -> SubscriptionPlanResponseDTO:
    """Convert subscription plan entity to DTO."""
    return SubscriptionPlanResponseDTO(
        id=plan.id,
        name=plan.name,
        code=plan.code,
        description=plan.description,
        monthly_price=plan.monthly_price,
        annual_price=plan.annual_price,
        features=plan.features,
        is_active=plan.is_active,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


def _subscription_to_dto(
    subscription: Subscription, plan: SubscriptionPlan | None = None
) -> SubscriptionResponseDTO:
    """Convert subscription entity to DTO."""
    plan_dto = None
    if plan:
        plan_dto = _subscription_plan_to_dto(plan)
    elif subscription.plan_id:
        # Plan will be loaded separately if needed
        pass

    return SubscriptionResponseDTO(
        id=subscription.id,
        business_id=subscription.business_id,
        plan_id=subscription.plan_id,
        plan=plan_dto,
        status=subscription.status,
        billing_period=subscription.billing_period,
        start_date=subscription.start_date,
        end_date=subscription.end_date,
        trial_end_date=subscription.trial_end_date,
        cancelled_at=subscription.cancelled_at,
        cancellation_reason=subscription.cancellation_reason,
        external_subscription_id=subscription.external_subscription_id,
        created_at=subscription.created_at,
        updated_at=subscription.updated_at,
        is_active=subscription.is_active(),
        days_until_expiry=subscription.days_until_expiry(),
    )


def _payment_transaction_to_dto(transaction: PaymentTransaction) -> PaymentResponseDTO:
    """Convert payment transaction entity to DTO."""
    return PaymentResponseDTO(
        id=transaction.id,
        subscription_id=transaction.subscription_id,
        provider=transaction.provider,
        amount=transaction.amount,
        currency=transaction.currency,
        status=transaction.status,
        external_transaction_id=transaction.external_transaction_id,
        payment_url=None,
        initiated_at=transaction.initiated_at,
        completed_at=transaction.completed_at,
        failure_reason=transaction.failure_reason,
        created_at=transaction.created_at,
        updated_at=transaction.updated_at,
    )


def _get_payment_provider(provider: PaymentProvider) -> PaymentProviderInterface:
    """Get payment provider service instance."""
    if provider == PaymentProvider.STRIPE:
        return StripeService(
            secret_key=settings.STRIPE_SECRET_KEY,
            publishable_key=settings.STRIPE_PUBLISHABLE_KEY,
            webhook_secret=getattr(settings, "STRIPE_WEBHOOK_SECRET", None),
        )
    elif provider == PaymentProvider.MTN_MOBILE_MONEY:
        return MTNMobileMoneyService(
            api_key=settings.MTN_MOBILE_MONEY_API_KEY,
            api_url=settings.MTN_MOBILE_MONEY_API_URL,
            api_user_id=getattr(settings, "MTN_MOBILE_MONEY_API_USER_ID", None),
        )
    elif provider == PaymentProvider.ORANGE_MOBILE_MONEY:
        return OrangeMobileMoneyService(
            api_key=settings.ORANGE_MOBILE_MONEY_API_KEY,
            api_url=settings.ORANGE_MOBILE_MONEY_API_URL,
            merchant_key=getattr(settings, "ORANGE_MOBILE_MONEY_MERCHANT_KEY", None),
        )
    else:
        raise BadRequestError(
            detail=f"Unsupported payment provider: {provider}",
            code="UNSUPPORTED_PAYMENT_PROVIDER",
        )


class ListSubscriptionPlansUseCase:
    """Use case for listing subscription plans."""

    def __init__(self, plan_repository: SubscriptionPlanRepository) -> None:
        """Initialize use case."""
        self.plan_repository = plan_repository

    def execute(self, active_only: bool = True) -> list[SubscriptionPlanResponseDTO]:
        """Execute listing subscription plans."""
        plans = self.plan_repository.get_all(active_only=active_only)
        return [_subscription_plan_to_dto(plan) for plan in plans]


class CreateSubscriptionUseCase:
    """Use case for creating a subscription."""

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        plan_repository: SubscriptionPlanRepository,
        business_repository: BusinessRepository,
        subscription_domain_service: SubscriptionDomainService,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.subscription_repository = subscription_repository
        self.plan_repository = plan_repository
        self.business_repository = business_repository
        self.subscription_domain_service = subscription_domain_service
        self.business_id = business_id
        self.user_id = user_id

    @transaction.atomic
    def execute(self, dto: SubscriptionCreateDTO) -> SubscriptionResponseDTO:
        """Execute subscription creation."""
        business = self.business_repository.get_by_id(self.business_id)
        if not business:
            raise NotFoundError(
                detail="Business not found",
                code="BUSINESS_NOT_FOUND",
            )

        if business.owner_id != self.user_id:
            raise ForbiddenError(
                detail="Only the business owner can create subscriptions",
                code="PERMISSION_DENIED",
            )

        # Check if business already has an active subscription
        existing_subscription = self.subscription_repository.get_by_business(
            self.business_id
        )
        if existing_subscription and existing_subscription.is_active():
            raise BadRequestError(
                detail="Business already has an active subscription",
                code="SUBSCRIPTION_ALREADY_EXISTS",
            )

        # Get plan
        plan = self.plan_repository.get_by_id(dto.plan_id)
        if not plan:
            raise NotFoundError(
                detail="Subscription plan not found",
                code="PLAN_NOT_FOUND",
            )

        if not plan.is_active:
            raise BadRequestError(
                detail="Subscription plan is not active",
                code="PLAN_INACTIVE",
            )

        # Calculate dates
        now = timezone.now()
        start_date = now

        # Calculate trial end date if trial is enabled
        trial_end_date = None
        if dto.start_trial:
            trial_end_date = self.subscription_domain_service.calculate_trial_end_date(
                start_date, TRIAL_DAYS
            )

        # Calculate subscription end date
        end_date = self.subscription_domain_service.calculate_subscription_end_date(
            start_date,
            dto.billing_period.value,
            trial_days=TRIAL_DAYS if dto.start_trial else 0,
        )

        # Create subscription
        subscription = Subscription(
            id=uuid4(),
            business_id=self.business_id,
            plan_id=dto.plan_id,
            status=(
                SubscriptionStatus.TRIAL
                if dto.start_trial
                else SubscriptionStatus.ACTIVE
            ),
            billing_period=dto.billing_period,
            start_date=start_date,
            end_date=end_date,
            trial_end_date=trial_end_date,
            cancelled_at=None,
            cancellation_reason=None,
            created_at=now,
            updated_at=now,
            external_subscription_id=None,
        )

        subscription = self.subscription_repository.create(subscription)

        # Update business with subscription
        business.subscription_id = subscription.id
        self.business_repository.update(business)

        logger.info(
            f"Subscription created - subscription_id: {subscription.id}, "
            f"business_id: {self.business_id}, plan_id: {dto.plan_id}"
        )

        return _subscription_to_dto(subscription, plan)


class ProcessPaymentUseCase:
    """Use case for processing a payment."""

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        plan_repository: SubscriptionPlanRepository,
        transaction_repository: PaymentTransactionRepository,
        subscription_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.subscription_repository = subscription_repository
        self.plan_repository = plan_repository
        self.transaction_repository = transaction_repository
        self.subscription_id = subscription_id
        self.user_id = user_id

    @transaction.atomic
    def execute(self, dto: PaymentInitiateDTO) -> PaymentResponseDTO:
        """Execute payment processing."""
        subscription = self.subscription_repository.get_by_id(self.subscription_id)
        if not subscription:
            raise NotFoundError(
                detail="Subscription not found", code="SUBSCRIPTION_NOT_FOUND"
            )

        if dto.idempotency_key:
            existing_transaction = self.transaction_repository.get_by_idempotency_key(
                dto.idempotency_key
            )
            if existing_transaction:
                logger.info(
                    f"Duplicate payment detected with idempotency_key {dto.idempotency_key}"
                )
                return _payment_transaction_to_dto(existing_transaction)

        # Get plan to calculate amount
        plan = self.plan_repository.get_by_id(subscription.plan_id)
        if not plan:
            raise NotFoundError(
                detail="Subscription plan not found", code="PLAN_NOT_FOUND"
            )

        # Calculate expected amount
        expected_amount = plan.get_price(subscription.billing_period)

        # Validate amount
        validation = PaymentValidationService.validate_payment_amount(
            dto.amount, expected_amount
        )
        if not validation["is_valid"]:
            raise BadRequestError(
                detail=f"Payment amount validation failed: {validation['errors']}",
                code="INVALID_PAYMENT_AMOUNT",
            )

        # Get payment provider
        payment_provider = _get_payment_provider(dto.provider)

        # Create payment transaction
        now = timezone.now()
        transaction = PaymentTransaction(
            id=uuid4(),
            subscription_id=self.subscription_id,
            provider=dto.provider,
            amount=dto.amount,
            currency=dto.currency,
            status=TransactionStatus.PENDING,
            external_transaction_id=None,
            provider_response=None,
            failure_reason=None,
            initiated_at=now,
            completed_at=None,
            created_at=now,
            updated_at=now,
            idempotency_key=dto.idempotency_key,
        )

        # Initiate payment with provider
        try:
            provider_response = payment_provider.initiate_payment(
                amount=dto.amount,
                currency=dto.currency,
                subscription_id=self.subscription_id,
                return_url=dto.return_url,
                cancel_url=dto.cancel_url,
                metadata={"user_id": str(self.user_id)},
            )

            transaction.external_transaction_id = provider_response.get(
                "transaction_id"
            )
            transaction.provider_response = provider_response
            transaction = self.transaction_repository.create(transaction)

            # Create response DTO
            payment_dto = _payment_transaction_to_dto(transaction)
            payment_dto.payment_url = provider_response.get("payment_url")

            logger.info(
                f"Payment initiated - transaction_id: {transaction.id}, "
                f"provider: {dto.provider}, amount: {dto.amount}"
            )

            return payment_dto

        except Exception as e:
            logger.error(f"Payment initiation failed: {e}", exc_info=True)
            transaction.status = TransactionStatus.FAILED
            transaction.failure_reason = str(e)
            self.transaction_repository.create(transaction)

            user_message = (
                "Unable to process payment. Please try again later or contact support."
            )
            technical_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
            }

            raise BadRequestError(
                detail=user_message,
                code="PAYMENT_INITIATION_FAILED",
                details=technical_details,
            ) from e


class HandleWebhookUseCase:
    """Use case for handling payment webhooks."""

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        transaction_repository: PaymentTransactionRepository,
        business_repository: BusinessRepository,
        subscription_domain_service: SubscriptionDomainService,
    ) -> None:
        """Initialize use case."""
        self.subscription_repository = subscription_repository
        self.transaction_repository = transaction_repository
        self.business_repository = business_repository
        self.subscription_domain_service = subscription_domain_service

    @transaction.atomic
    def execute(self, dto: WebhookPayloadDTO) -> dict:
        """Execute webhook handling."""
        event_type = dto.event_type

        if event_type in ("v2.core.event_destination.ping", "ping"):
            logger.info(f"Ignoring ping/test event: {event_type}")
            return {
                "status": "ignored",
                "reason": "Ping/test event - no transaction data",
                "event_type": event_type,
            }

        # Get payment provider
        payment_provider = _get_payment_provider(dto.provider)

        # Handle webhook
        try:
            webhook_data = payment_provider.handle_webhook(dto.payload, dto.signature)
        except Exception as e:
            logger.error(f"Webhook handling failed: {e}", exc_info=True)
            raise BadRequestError(
                detail=f"Webhook handling failed: {str(e)}",
                code="WEBHOOK_HANDLING_FAILED",
            ) from e

        def convert_decimals_to_float(obj):
            """Recursively convert Decimal values to float for JSON serialization."""
            if isinstance(obj, Decimal):
                return float(obj)
            elif isinstance(obj, dict):
                return {k: convert_decimals_to_float(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_decimals_to_float(item) for item in obj]
            return obj

        webhook_data = convert_decimals_to_float(webhook_data)

        transaction_id = webhook_data.get("transaction_id")
        if not transaction_id:
            raise BadRequestError(
                detail="Transaction ID not found in webhook data",
                code="TRANSACTION_ID_NOT_FOUND",
            )

        # Find transaction by external ID
        transaction = self.transaction_repository.get_by_external_id(
            transaction_id, dto.provider.value
        )

        if not transaction:
            logger.warning(
                f"Transaction not found for external_id: {transaction_id}, provider: {dto.provider}"
            )
            return {"status": "ignored", "reason": "Transaction not found"}

        # Update transaction status based on event type and status
        event_type = webhook_data.get("event_type", "")
        status = webhook_data.get("status", "")

        # Improved event type detection for Stripe events
        completed_events = (
            "checkout.session.completed",
            "payment_intent.succeeded",
            "charge.succeeded",
        )
        failed_events = (
            "payment_intent.payment_failed",
            "charge.failed",
            "checkout.session.async_payment_failed",
        )
        cancelled_events = ("checkout.session.async_payment_failed",)

        if (
            status == "completed"
            or event_type in completed_events
            or "completed" in event_type.lower()
        ):
            transaction.status = TransactionStatus.COMPLETED
            transaction.completed_at = timezone.now()
            transaction.provider_response = webhook_data
        elif (
            status == "failed"
            or event_type in failed_events
            or "failed" in event_type.lower()
        ):
            transaction.status = TransactionStatus.FAILED
            transaction.failure_reason = webhook_data.get(
                "failure_reason", "Payment failed"
            )
            transaction.provider_response = webhook_data
        elif (
            status == "cancelled"
            or event_type in cancelled_events
            or "cancelled" in event_type.lower()
        ):
            transaction.status = TransactionStatus.CANCELLED
            transaction.provider_response = webhook_data
        else:
            # Log unhandled event types for debugging
            logger.info(
                f"Unhandled webhook event type: {event_type}, status: {status}. "
                f"Transaction {transaction.id} status unchanged."
            )

        transaction = self.transaction_repository.update(transaction)

        # If payment completed, activate subscription and business
        if transaction.status == TransactionStatus.COMPLETED:
            subscription = self.subscription_repository.get_by_id(
                transaction.subscription_id
            )
            if subscription:
                # Update subscription status to ACTIVE if it was in TRIAL
                if subscription.status == SubscriptionStatus.TRIAL:
                    subscription.status = SubscriptionStatus.ACTIVE

                now = timezone.now()
                if not subscription.start_date:
                    subscription.start_date = now

                # Calculate end_date if not set
                if not subscription.end_date:
                    if subscription.billing_period == BillingPeriod.MONTHLY:
                        from datetime import timedelta

                        subscription.end_date = now + timedelta(days=30)
                    elif subscription.billing_period == BillingPeriod.YEARLY:
                        from datetime import timedelta

                        subscription.end_date = now + timedelta(days=365)

                # Update subscription updated_at
                subscription.updated_at = now
                subscription = self.subscription_repository.update(subscription)

                # Activate business and link subscription
                business = self.business_repository.get_by_id(subscription.business_id)
                if business:
                    business.is_active = True
                    business.subscription_id = subscription.id
                    business.updated_at = now
                    business = self.business_repository.update(business)

                logger.info(
                    f"Subscription activated via webhook - subscription_id: {subscription.id}, "
                    f"transaction_id: {transaction.id}, business_id: {business.id if business else None}"
                )

        return {
            "status": "processed",
            "transaction_id": str(transaction.id),
            "subscription_id": str(transaction.subscription_id),
        }


class RenewSubscriptionUseCase:
    """Use case for renewing a subscription."""

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        plan_repository: SubscriptionPlanRepository,
        subscription_domain_service: SubscriptionDomainService,
        subscription_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.subscription_repository = subscription_repository
        self.plan_repository = plan_repository
        self.subscription_domain_service = subscription_domain_service
        self.subscription_id = subscription_id
        self.user_id = user_id

    @transaction.atomic
    def execute(self, dto: SubscriptionRenewDTO) -> SubscriptionResponseDTO:
        """Execute subscription renewal."""
        subscription = self.subscription_repository.get_by_id(self.subscription_id)
        if not subscription:
            raise NotFoundError(
                detail="Subscription not found",
                code="SUBSCRIPTION_NOT_FOUND",
            )

        # Use provided billing period or current one
        billing_period = dto.billing_period or subscription.billing_period

        # Calculate new end date
        start_date = subscription.end_date or timezone.now()
        end_date = self.subscription_domain_service.calculate_subscription_end_date(
            start_date, billing_period.value, trial_days=0
        )

        # Update subscription
        subscription.billing_period = billing_period
        subscription.end_date = end_date
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.updated_at = timezone.now()

        subscription = self.subscription_repository.update(subscription)

        plan = self.plan_repository.get_by_id(subscription.plan_id)
        return _subscription_to_dto(subscription, plan)


class CancelSubscriptionUseCase:
    """Use case for cancelling a subscription."""

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        business_repository: BusinessRepository,
        subscription_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.subscription_repository = subscription_repository
        self.business_repository = business_repository
        self.subscription_id = subscription_id
        self.user_id = user_id

    @transaction.atomic
    def execute(self, dto: SubscriptionCancelDTO) -> SubscriptionResponseDTO:
        """Execute subscription cancellation."""
        subscription = self.subscription_repository.get_by_id(self.subscription_id)
        if not subscription:
            raise NotFoundError(
                detail="Subscription not found",
                code="SUBSCRIPTION_NOT_FOUND",
            )

        if subscription.status == SubscriptionStatus.CANCELLED:
            raise BadRequestError(
                detail="Subscription is already cancelled",
                code="SUBSCRIPTION_ALREADY_CANCELLED",
            )

        # Cancel subscription
        subscription.status = SubscriptionStatus.CANCELLED
        subscription.cancelled_at = timezone.now()
        subscription.cancellation_reason = dto.reason
        subscription.updated_at = timezone.now()

        if dto.cancel_immediately:
            subscription.end_date = timezone.now()

        subscription = self.subscription_repository.update(subscription)

        # Deactivate business if cancel immediately
        if dto.cancel_immediately:
            business = self.business_repository.get_by_id(subscription.business_id)
            if business:
                business.is_active = False
                business = self.business_repository.update(business)

        logger.info(f"Subscription cancelled - subscription_id: {subscription.id}")

        return _subscription_to_dto(subscription)


class ListSubscriptionsUseCase:
    """Use case for listing subscriptions."""

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        plan_repository: SubscriptionPlanRepository,
        business_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.subscription_repository = subscription_repository
        self.plan_repository = plan_repository
        self.business_id = business_id

    def execute(self) -> list[SubscriptionResponseDTO]:
        """Execute listing subscriptions."""
        subscriptions = self.subscription_repository.get_by_business_all(
            self.business_id
        )
        plans = {
            sub.plan_id: self.plan_repository.get_by_id(sub.plan_id)
            for sub in subscriptions
        }
        return [
            _subscription_to_dto(sub, plans.get(sub.plan_id)) for sub in subscriptions
        ]


class GetSubscriptionStatusUseCase:
    """Use case for getting subscription status."""

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        plan_repository: SubscriptionPlanRepository,
        subscription_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.subscription_repository = subscription_repository
        self.plan_repository = plan_repository
        self.subscription_id = subscription_id

    def execute(self) -> SubscriptionResponseDTO:
        """Execute getting subscription status."""
        subscription = self.subscription_repository.get_by_id(self.subscription_id)
        if not subscription:
            raise NotFoundError(
                detail="Subscription not found",
                code="SUBSCRIPTION_NOT_FOUND",
            )

        plan = self.plan_repository.get_by_id(subscription.plan_id)
        return _subscription_to_dto(subscription, plan)
