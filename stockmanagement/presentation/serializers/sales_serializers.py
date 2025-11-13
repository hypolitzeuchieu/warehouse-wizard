"""Sales serializers."""

from decimal import Decimal

from rest_framework import serializers

from application.dto.sales_dto import (
    InvoiceCreateDTO,
    InvoiceLineCreateDTO,
)


class InvoiceLineCreateSerializer(serializers.Serializer):
    """Serializer for invoice line creation."""

    product_id = serializers.UUIDField(required=True)
    quantity = serializers.IntegerField(required=True, min_value=1)
    unit_price = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=True, min_value=Decimal("0.01")
    )
    discount = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False, default=Decimal("0.00"), min_value=Decimal("0.00")
    )

    def to_dto(self) -> InvoiceLineCreateDTO:
        """Convert to DTO."""
        return InvoiceLineCreateDTO(
            product_id=self.validated_data["product_id"],
            quantity=self.validated_data["quantity"],
            unit_price=self.validated_data["unit_price"],
            discount=self.validated_data.get("discount", Decimal("0.00")),
        )


class InvoiceCreateSerializer(serializers.Serializer):
    """Serializer for invoice creation."""

    customer_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    lines = InvoiceLineCreateSerializer(many=True, required=True)
    tax = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False, default=Decimal("0.00"), min_value=Decimal("0.00")
    )
    discount = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False, default=Decimal("0.00"), min_value=Decimal("0.00")
    )
    payment_method = serializers.ChoiceField(
        choices=["cash", "card", "mobile_money", "stripe", "paypal", "credit"],
        default="cash",
        required=False,
    )
    due_date = serializers.DateField(required=False, allow_null=True)
    reason = serializers.CharField(required=False, allow_blank=True)

    def to_dto(self) -> InvoiceCreateDTO:
        """Convert to DTO."""
        return InvoiceCreateDTO(
            customer_name=self.validated_data.get("customer_name"),
            customer_id=self.validated_data.get("customer_id"),
            lines=[
                line_serializer.to_dto()
                for line_serializer in self.validated_data["lines"]
            ],
            tax=self.validated_data.get("tax", Decimal("0.00")),
            discount=self.validated_data.get("discount", Decimal("0.00")),
            payment_method=self.validated_data.get("payment_method", "cash"),
            due_date=self.validated_data.get("due_date"),
            reason=self.validated_data.get("reason"),
        )

