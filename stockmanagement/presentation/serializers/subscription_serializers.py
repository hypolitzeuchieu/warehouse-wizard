"""Subscription serializers."""

from django.conf import settings
from rest_framework import serializers

from application.dto.subscription_dto import (
    PaymentInitiateDTO,
    PaymentResponseDTO,
    SubscriptionCancelDTO,
    SubscriptionCreateDTO,
    SubscriptionPlanResponseDTO,
    SubscriptionRenewDTO,
    SubscriptionResponseDTO,
)
from domain.subscription.entities import BillingPeriod, PaymentProvider


class SubscriptionPlanSerializer(serializers.Serializer):
    """Serializer for subscription plan response."""

    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    code = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True, allow_null=True, required=False)
    monthly_price = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )
    annual_price = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )
    features = serializers.JSONField(read_only=True, allow_null=True, required=False)
    is_active = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    @staticmethod
    def from_dto(dto: SubscriptionPlanResponseDTO) -> dict:
        """Convert DTO to dictionary."""
        return {
            "id": str(dto.id),
            "name": dto.name,
            "code": dto.code,
            "description": dto.description,
            "monthly_price": str(dto.monthly_price),
            "annual_price": str(dto.annual_price),
            "features": dto.features,
            "is_active": dto.is_active,
            "created_at": dto.created_at.isoformat(),
            "updated_at": dto.updated_at.isoformat(),
        }


class SubscriptionCreateSerializer(serializers.Serializer):
    """Serializer for creating a subscription."""

    plan_id = serializers.UUIDField(required=True)
    billing_period = serializers.ChoiceField(
        choices=[(bp.value, bp.value) for bp in BillingPeriod], required=True
    )
    start_trial = serializers.BooleanField(default=True, required=False)

    def to_dto(self, business_id: str) -> SubscriptionCreateDTO:
        """Convert to DTO."""

        return SubscriptionCreateDTO(
            business_id=business_id,
            plan_id=self.validated_data["plan_id"],
            billing_period=BillingPeriod(self.validated_data["billing_period"]),
            start_trial=self.validated_data.get("start_trial", True),
        )


class SubscriptionSerializer(serializers.Serializer):
    """Serializer for subscription response."""

    id = serializers.UUIDField(read_only=True)
    business_id = serializers.UUIDField(read_only=True)
    plan_id = serializers.UUIDField(read_only=True)
    plan = serializers.JSONField(read_only=True, allow_null=True, required=False)

    status = serializers.CharField(read_only=True)
    billing_period = serializers.CharField(read_only=True)
    start_date = serializers.DateTimeField(read_only=True)
    end_date = serializers.DateTimeField(
        read_only=True, allow_null=True, required=False
    )
    trial_end_date = serializers.DateTimeField(
        read_only=True, allow_null=True, required=False
    )
    cancelled_at = serializers.DateTimeField(
        read_only=True, allow_null=True, required=False
    )
    cancellation_reason = serializers.CharField(
        read_only=True, allow_null=True, required=False
    )
    external_subscription_id = serializers.CharField(
        read_only=True, allow_null=True, required=False
    )
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    days_until_expiry = serializers.IntegerField(
        read_only=True, allow_null=True, required=False
    )

    @staticmethod
    def from_dto(dto: SubscriptionResponseDTO) -> dict:
        """Convert DTO to dictionary."""
        return {
            "id": str(dto.id),
            "business_id": str(dto.business_id),
            "plan_id": str(dto.plan_id),
            "plan": SubscriptionPlanSerializer.from_dto(dto.plan) if dto.plan else None,
            "status": dto.status.value,
            "billing_period": dto.billing_period.value,
            "start_date": dto.start_date.isoformat(),
            "end_date": dto.end_date.isoformat() if dto.end_date else None,
            "trial_end_date": (
                dto.trial_end_date.isoformat() if dto.trial_end_date else None
            ),
            "cancelled_at": dto.cancelled_at.isoformat() if dto.cancelled_at else None,
            "cancellation_reason": dto.cancellation_reason,
            "external_subscription_id": dto.external_subscription_id,
            "created_at": dto.created_at.isoformat(),
            "updated_at": dto.updated_at.isoformat(),
            "is_active": dto.is_active,
            "days_until_expiry": dto.days_until_expiry,
        }


class PaymentInitiateSerializer(serializers.Serializer):
    """Serializer for initiating a payment."""

    provider = serializers.ChoiceField(
        choices=[(pp.value, pp.value) for pp in PaymentProvider], required=True
    )
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, required=True)
    currency = serializers.CharField(max_length=10, default="XAF", required=False)
    idempotency_key = serializers.UUIDField(allow_null=True, required=False)

    def to_dto(self, subscription_id: str) -> PaymentInitiateDTO:
        """Convert to DTO."""
        return PaymentInitiateDTO(
            subscription_id=subscription_id,
            provider=PaymentProvider(self.validated_data["provider"]),
            amount=self.validated_data["amount"],
            currency=self.validated_data.get("currency", "XAF"),
            return_url=getattr(settings, "PAYMENT_RETURN_URL", None),
            cancel_url=getattr(settings, "PAYMENT_CANCEL_URL", None),
            idempotency_key=self.validated_data.get("idempotency_key"),
        )


class PaymentResponseSerializer(serializers.Serializer):
    """Serializer for payment response."""

    id = serializers.UUIDField(read_only=True)
    subscription_id = serializers.UUIDField(read_only=True)
    provider = serializers.CharField(read_only=True)
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    currency = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    external_transaction_id = serializers.CharField(
        read_only=True, allow_null=True, required=False
    )
    payment_url = serializers.URLField(read_only=True, allow_null=True, required=False)
    initiated_at = serializers.DateTimeField(read_only=True)
    completed_at = serializers.DateTimeField(
        read_only=True, allow_null=True, required=False
    )
    failure_reason = serializers.CharField(
        read_only=True, allow_null=True, required=False
    )
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    class Meta:
        ref_name = "SubscriptionPaymentResponse"

    @staticmethod
    def from_dto(dto: PaymentResponseDTO) -> dict:
        """Convert DTO to dictionary."""
        return {
            "id": str(dto.id),
            "subscription_id": str(dto.subscription_id),
            "provider": dto.provider.value,
            "amount": str(dto.amount),
            "currency": dto.currency,
            "status": dto.status.value,
            "external_transaction_id": dto.external_transaction_id,
            "payment_url": dto.payment_url,
            "initiated_at": dto.initiated_at.isoformat(),
            "completed_at": dto.completed_at.isoformat() if dto.completed_at else None,
            "failure_reason": dto.failure_reason,
            "created_at": dto.created_at.isoformat(),
            "updated_at": dto.updated_at.isoformat(),
        }


class SubscriptionCancelSerializer(serializers.Serializer):
    """Serializer for cancelling a subscription."""

    reason = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    cancel_immediately = serializers.BooleanField(default=False, required=False)

    def to_dto(self) -> SubscriptionCancelDTO:
        """Convert to DTO."""
        return SubscriptionCancelDTO(
            reason=self.validated_data.get("reason"),
            cancel_immediately=self.validated_data.get("cancel_immediately", False),
        )


class SubscriptionRenewSerializer(serializers.Serializer):
    """Serializer for renewing a subscription."""

    billing_period = serializers.ChoiceField(
        choices=[(bp.value, bp.value) for bp in BillingPeriod],
        required=False,
        allow_null=True,
    )

    def to_dto(self) -> SubscriptionRenewDTO:
        """Convert to DTO."""

        billing_period = self.validated_data.get("billing_period")
        return SubscriptionRenewDTO(
            billing_period=BillingPeriod(billing_period) if billing_period else None
        )
