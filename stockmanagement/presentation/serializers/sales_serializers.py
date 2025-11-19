"""Sales serializers."""

from decimal import Decimal

from rest_framework import serializers

from application.dto.sales_dto import (
    InvoiceCreateDTO,
    InvoiceLineCreateDTO,
    InvoiceLineResponseDTO,
    InvoiceResponseDTO,
)


class InvoiceLineCreateSerializer(serializers.Serializer):
    """Serializer for invoice line creation."""

    product_id = serializers.UUIDField(required=True)
    quantity = serializers.IntegerField(required=True, min_value=1)
    unit_price = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=True, min_value=Decimal("0.01")
    )
    discount = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        required=False,
        default=Decimal("0.00"),
        min_value=Decimal("0.00"),
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
        max_digits=15,
        decimal_places=2,
        required=False,
        default=Decimal("0.00"),
        min_value=Decimal("0.00"),
    )
    discount = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        required=False,
        default=Decimal("0.00"),
        min_value=Decimal("0.00"),
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
            lines=[line_serializer.to_dto() for line_serializer in self.validated_data["lines"]],
            tax=self.validated_data.get("tax", Decimal("0.00")),
            discount=self.validated_data.get("discount", Decimal("0.00")),
            payment_method=self.validated_data.get("payment_method", "cash"),
            due_date=self.validated_data.get("due_date"),
            reason=self.validated_data.get("reason"),
        )


class InvoiceLineResponseSerializer(serializers.Serializer):
    """Serializer for invoice line responses."""

    id = serializers.UUIDField()
    invoice_id = serializers.UUIDField()
    product_id = serializers.UUIDField()
    quantity = serializers.IntegerField()
    unit_price = serializers.DecimalField(max_digits=15, decimal_places=2)
    discount = serializers.DecimalField(max_digits=15, decimal_places=2)
    line_total = serializers.DecimalField(max_digits=15, decimal_places=2)
    created_at = serializers.DateTimeField()
    product_name = serializers.CharField(allow_null=True, required=False)

    @classmethod
    def from_dto(cls, dto: InvoiceLineResponseDTO) -> dict:
        serializer = cls(
            data={
                "id": dto.id,
                "invoice_id": dto.invoice_id,
                "product_id": dto.product_id,
                "quantity": dto.quantity,
                "unit_price": dto.unit_price,
                "discount": dto.discount,
                "line_total": dto.line_total,
                "created_at": dto.created_at,
                "product_name": dto.product_name,
            }
        )
        serializer.is_valid(raise_exception=True)
        return serializer.data


class InvoiceResponseSerializer(serializers.Serializer):
    """Serializer for invoice responses."""

    id = serializers.UUIDField()
    business_id = serializers.UUIDField()
    number = serializers.IntegerField()
    cashier_id = serializers.UUIDField()
    status = serializers.CharField()
    total = serializers.DecimalField(max_digits=15, decimal_places=2)
    tax = serializers.DecimalField(max_digits=15, decimal_places=2)
    discount = serializers.DecimalField(max_digits=15, decimal_places=2)
    advance_paid = serializers.DecimalField(max_digits=15, decimal_places=2)
    remaining_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    payment_method = serializers.CharField()
    is_credit_settled = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    customer_name = serializers.CharField(allow_null=True, required=False)
    customer_id = serializers.UUIDField(allow_null=True, required=False)
    cashier_name = serializers.CharField(allow_null=True, required=False)
    due_date = serializers.DateTimeField(allow_null=True, required=False)
    reason = serializers.CharField(allow_null=True, required=False)
    lines = InvoiceLineResponseSerializer(many=True, required=False)

    @classmethod
    def from_dto(cls, dto: InvoiceResponseDTO) -> dict:
        line_data = [
            InvoiceLineResponseSerializer.from_dto(line_dto) for line_dto in (dto.lines or [])
        ]
        serializer = cls(
            data={
                "id": dto.id,
                "business_id": dto.business_id,
                "number": dto.number,
                "cashier_id": dto.cashier_id,
                "status": dto.status,
                "total": dto.total,
                "tax": dto.tax,
                "discount": dto.discount,
                "advance_paid": dto.advance_paid,
                "remaining_amount": dto.remaining_amount,
                "payment_method": dto.payment_method,
                "is_credit_settled": dto.is_credit_settled,
                "created_at": dto.created_at,
                "updated_at": dto.updated_at,
                "customer_name": dto.customer_name,
                "customer_id": dto.customer_id,
                "cashier_name": dto.cashier_name,
                "due_date": dto.due_date,
                "reason": dto.reason,
                "lines": line_data,
            }
        )
        serializer.is_valid(raise_exception=True)
        return serializer.data
