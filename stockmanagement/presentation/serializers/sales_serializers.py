"""Sales serializers."""

from decimal import Decimal

from rest_framework import serializers

from application.dto.sales_dto import (
    BarcodeScanResponseDTO,
    CreditApplicationDTO,
    InvoiceCreateDTO,
    InvoiceLineCreateDTO,
    InvoiceLineResponseDTO,
    InvoiceResponseDTO,
    InvoiceUpdateDTO,
    PaymentCreateDTO,
    PaymentResponseDTO,
    ProductSearchResponseDTO,
    RefundCreateDTO,
    RefundResponseDTO,
)


class InvoiceLineCreateSerializer(serializers.Serializer):
    """Serializer for invoice line creation."""

    product_id = serializers.UUIDField(required=True)
    quantity = serializers.IntegerField(required=True, min_value=1)

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
            discount=self.validated_data.get("discount", Decimal("0.00")),
        )


class InvoiceCreateSerializer(serializers.Serializer):
    """Serializer for invoice creation."""

    business_id = serializers.UUIDField(required=True)
    customer_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    # Fields for creating a new customer during sale
    customer_email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    customer_phone = serializers.CharField(
        max_length=30, required=False, allow_blank=True, allow_null=True
    )
    customer_address = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    customer_type = serializers.ChoiceField(
        choices=["REGULAR", "WHOLESALER"],
        default="REGULAR",
        required=False,
    )
    lines = InvoiceLineCreateSerializer(many=True, required=True)
    tax = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        required=False,
        default=Decimal("0.00"),
        min_value=Decimal("0.00"),
    )
    advance_paid = serializers.DecimalField(
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
        lines_dto = []
        for line_data in self.validated_data.get("lines", []):
            lines_dto.append(
                InvoiceLineCreateDTO(
                    product_id=line_data["product_id"],
                    quantity=line_data["quantity"],
                    discount=line_data.get("discount", Decimal("0.00")),
                )
            )

        return InvoiceCreateDTO(
            customer_name=self.validated_data.get("customer_name"),
            customer_id=self.validated_data.get("customer_id"),
            customer_email=self.validated_data.get("customer_email"),
            customer_phone=self.validated_data.get("customer_phone"),
            customer_address=self.validated_data.get("customer_address"),
            customer_type=self.validated_data.get("customer_type", "REGULAR"),
            lines=lines_dto,
            tax=self.validated_data.get("tax", Decimal("0.00")),
            advance_paid=self.validated_data.get("advance_paid", Decimal("0.00")),
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


class InvoiceUpdateSerializer(serializers.Serializer):
    """Serializer for updating an invoice."""

    status = serializers.ChoiceField(
        choices=["COMPLETED", "CANCELLED", "CREDIT", "PENDING"], required=False
    )
    tax = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False, min_value=Decimal("0.00")
    )
    discount = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False, min_value=Decimal("0.00")
    )
    advance_paid = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False, min_value=Decimal("0.00")
    )
    payment_method = serializers.ChoiceField(
        choices=["cash", "card", "mobile_money", "stripe", "paypal", "credit"],
        required=False,
    )
    due_date = serializers.DateField(required=False, allow_null=True)
    is_credit_settled = serializers.BooleanField(required=False)
    reason = serializers.CharField(required=False, allow_blank=True)

    def to_dto(self) -> InvoiceUpdateDTO:
        """Convert to DTO."""
        return InvoiceUpdateDTO(
            status=self.validated_data.get("status"),
            tax=self.validated_data.get("tax"),
            discount=self.validated_data.get("discount"),
            advance_paid=self.validated_data.get("advance_paid"),
            payment_method=self.validated_data.get("payment_method"),
            due_date=self.validated_data.get("due_date"),
            is_credit_settled=self.validated_data.get("is_credit_settled"),
            reason=self.validated_data.get("reason"),
        )


class PaymentCreateSerializer(serializers.Serializer):
    """Serializer for creating a payment."""

    amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=True, min_value=Decimal("0.01")
    )
    payment_method = serializers.ChoiceField(
        choices=["cash", "card", "mobile_money", "stripe", "paypal", "credit"],
        default="cash",
        required=False,
    )
    payment_date = serializers.DateTimeField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    idempotency_key = serializers.UUIDField(required=False, allow_null=True)

    def to_dto(self) -> PaymentCreateDTO:
        """Convert to DTO."""
        return PaymentCreateDTO(
            amount=self.validated_data["amount"],
            payment_method=self.validated_data.get("payment_method", "cash"),
            payment_date=self.validated_data.get("payment_date"),
            notes=self.validated_data.get("notes"),
            idempotency_key=self.validated_data.get("idempotency_key"),
        )


class PaymentResponseSerializer(serializers.Serializer):
    """Serializer for payment response."""

    id = serializers.UUIDField()
    invoice_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    payment_method = serializers.CharField()
    change_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    refund_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    payment_date = serializers.DateTimeField()
    notes = serializers.CharField(allow_null=True, required=False)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    created_by = serializers.UUIDField(allow_null=True, required=False)

    @classmethod
    def from_dto(cls, dto: PaymentResponseDTO) -> dict:
        serializer = cls(
            data={
                "id": dto.id,
                "invoice_id": dto.invoice_id,
                "amount": dto.amount,
                "payment_method": dto.payment_method,
                "change_amount": dto.change_amount,
                "refund_amount": dto.refund_amount,
                "payment_date": dto.payment_date,
                "notes": dto.notes,
                "created_at": dto.created_at,
                "updated_at": dto.updated_at,
                "created_by": dto.created_by,
            }
        )
        serializer.is_valid(raise_exception=True)
        return serializer.data


class PaymentProcessedResponseSerializer(serializers.Serializer):
    """Serializer for payment processed response (invoice + payment)."""

    invoice = InvoiceResponseSerializer()
    payment = PaymentResponseSerializer()


class RefundCreateSerializer(serializers.Serializer):
    """Serializer for creating a refund."""

    amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=True, min_value=Decimal("0.01")
    )
    reason = serializers.CharField(required=False, allow_blank=True)
    restore_stock = serializers.BooleanField(default=True, required=False)

    def to_dto(self) -> RefundCreateDTO:
        """Convert to DTO."""
        return RefundCreateDTO(
            amount=self.validated_data["amount"],
            reason=self.validated_data.get("reason"),
            restore_stock=self.validated_data.get("restore_stock", True),
        )


class RefundResponseSerializer(serializers.Serializer):
    """Serializer for refund response."""

    id = serializers.UUIDField()
    invoice_id = serializers.UUIDField()
    refund_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    new_paid_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    new_remaining_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    created_at = serializers.DateTimeField()

    @classmethod
    def from_dto(cls, dto: RefundResponseDTO) -> dict:
        serializer = cls(
            data={
                "id": dto.id,
                "invoice_id": dto.invoice_id,
                "refund_amount": dto.refund_amount,
                "new_paid_amount": dto.new_paid_amount,
                "new_remaining_amount": dto.new_remaining_amount,
                "created_at": dto.created_at,
            }
        )
        serializer.is_valid(raise_exception=True)
        return serializer.data


class InvoiceListQuerySerializer(serializers.Serializer):
    """Serializer for invoice list query parameters."""

    business_id = serializers.UUIDField(required=True)
    status = serializers.ChoiceField(
        choices=["PENDING", "PAID", "PARTIAL", "CANCELLED", "REFUNDED"],
        required=False,
        allow_null=True,
    )
    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)
    search = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    page_size = serializers.IntegerField(required=False, min_value=1, max_value=1000, default=20)
    order_by = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class ProductSearchSerializer(serializers.Serializer):
    """Serializer for product search request."""

    query = serializers.CharField(required=True, max_length=255)
    limit = serializers.IntegerField(default=20, min_value=1, max_value=100, required=False)


class ProductSearchResponseSerializer(serializers.Serializer):
    """Serializer for product search response."""

    id = serializers.UUIDField()
    name = serializers.CharField()
    barcode = serializers.CharField(allow_null=True, required=False)
    unit_price = serializers.DecimalField(max_digits=15, decimal_places=2)
    promo_price = serializers.DecimalField(
        max_digits=15, decimal_places=2, allow_null=True, required=False
    )
    quantity = serializers.IntegerField()
    category_name = serializers.CharField(allow_null=True, required=False)
    subcategory_name = serializers.CharField(allow_null=True, required=False)

    @classmethod
    def from_dto(cls, dto: ProductSearchResponseDTO) -> dict:
        serializer = cls(
            data={
                "id": dto.id,
                "name": dto.name,
                "barcode": dto.barcode,
                "unit_price": dto.unit_price,
                "promo_price": dto.promo_price,
                "quantity": dto.quantity,
                "category_name": dto.category_name,
                "subcategory_name": dto.subcategory_name,
            }
        )
        serializer.is_valid(raise_exception=True)
        return serializer.data


class BarcodeScanSerializer(serializers.Serializer):
    """Serializer for barcode scan request."""

    barcode = serializers.CharField(required=True, max_length=255)


class BarcodeScanResponseSerializer(serializers.Serializer):
    """Serializer for barcode scan response."""

    id = serializers.UUIDField()
    name = serializers.CharField()
    barcode = serializers.CharField()
    unit_price = serializers.DecimalField(max_digits=15, decimal_places=2)
    promo_price = serializers.DecimalField(
        max_digits=15, decimal_places=2, allow_null=True, required=False
    )
    quantity = serializers.IntegerField()
    category_name = serializers.CharField(allow_null=True, required=False)
    subcategory_name = serializers.CharField(allow_null=True, required=False)
    is_available = serializers.BooleanField()

    @classmethod
    def from_dto(cls, dto: BarcodeScanResponseDTO) -> dict:
        serializer = cls(
            data={
                "id": dto.id,
                "name": dto.name,
                "barcode": dto.barcode,
                "unit_price": dto.unit_price,
                "promo_price": dto.promo_price,
                "quantity": dto.quantity,
                "category_name": dto.category_name,
                "subcategory_name": dto.subcategory_name,
                "is_available": dto.is_available,
            }
        )
        serializer.is_valid(raise_exception=True)
        return serializer.data


class CreditApplicationSerializer(serializers.Serializer):
    """Serializer for applying credit to invoice."""

    credit_id = serializers.UUIDField(required=True)
    amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False, min_value=Decimal("0.01")
    )

    def to_dto(self) -> CreditApplicationDTO:
        """Convert to DTO."""
        return CreditApplicationDTO(
            credit_id=self.validated_data["credit_id"],
            amount=self.validated_data.get("amount"),
        )
