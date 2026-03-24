"""Credit serializers."""

from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers


class CreditCreateSerializer(serializers.Serializer):
    """Serializer for creating a credit."""

    customer_id = serializers.UUIDField(required=True)
    invoice_id = serializers.UUIDField(required=False, allow_null=True)
    amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=True, min_value=Decimal("0.01")
    )
    due_date = serializers.DateTimeField(required=True)
    notes = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class CreditUpdateSerializer(serializers.Serializer):
    """Serializer for updating a credit."""

    amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False, min_value=Decimal("0.01")
    )
    due_date = serializers.DateTimeField(required=False)
    notes = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    status = serializers.ChoiceField(
        choices=["PENDING", "OVERDUE", "PARTIALLY_PAID", "SETTLED", "CANCELLED"],
        required=False,
    )


class CreditResponseSerializer(serializers.Serializer):
    """Serializer for credit response."""

    id = serializers.UUIDField()
    business_id = serializers.UUIDField()
    customer_id = serializers.UUIDField()
    invoice_id = serializers.UUIDField(allow_null=True)
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    paid_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    remaining_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    due_date = serializers.DateTimeField()
    status = serializers.CharField()
    notes = serializers.CharField(allow_null=True)
    is_overdue = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class CreditPaymentCreateSerializer(serializers.Serializer):
    """Serializer for creating a credit payment."""

    amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=True, min_value=Decimal("0.01")
    )
    payment_method = serializers.CharField(required=False, default="cash")
    notes = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    payment_date = serializers.DateTimeField(required=False, allow_null=True)


class CreditPaymentResponseSerializer(serializers.Serializer):
    """Serializer for credit payment response."""

    id = serializers.UUIDField()
    credit_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    payment_date = serializers.DateTimeField()
    payment_method = serializers.CharField()
    notes = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField()
