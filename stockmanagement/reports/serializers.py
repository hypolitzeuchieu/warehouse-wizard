from rest_framework import serializers
from reports.models import (
    Invoice,
    InvoiceLine,
    Report,
    Notification,
    InventoryReport,
    SalesReport,
)


class InvoiceLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = InvoiceLine
        fields = [
            "id",
            "invoice",
            "product",
            "product_name",
            "quantity",
            "unit_price",
            "discount",
            "line_total",
        ]


class InvoiceSerializer(serializers.ModelSerializer):
    lines = InvoiceLineSerializer(many=True, read_only=True)
    cashier_name = serializers.CharField(source="cashier.username", read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "number",
            "created_at",
            "client_name",
            "cashier",
            "cashier_name",
            "status",
            "total",
            "tax",
            "advance_paid",
            "due_date",
            "is_credit_settled",
            "lines",
        ]

    def create(self, validated_data):
        # Gestion des lignes de facture lors de la création
        lines_data = self.context["request"].data.pop("lines", [])
        invoice = Invoice.objects.create(**validated_data)
        for line_data in lines_data:
            line_data["invoice"] = invoice
            InvoiceLine.objects.create(**line_data)
        return invoice


class ReportSerializer(serializers.ModelSerializer):
    generated_by_name = serializers.CharField(source="generated_by.username", read_only=True)

    class Meta:
        model = Report
        fields = [
            "id",
            "type",
            "generated_at",
            "generated_by",
            "generated_by_name",
            "file_path",
            "description",
        ]


class NotificationSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "product",
            "product_name",
            "type",
            "message",
            "created_at",
            "resolved",
        ]


class InventoryReportSerializer(serializers.ModelSerializer):
    generated_by_name = serializers.CharField(source="generated_by.username", read_only=True)

    class Meta:
        model = InventoryReport
        fields = [
            "id",
            "created_at",
            "generated_by",
            "generated_by_name",
            "total_products",
            "expired_products",
            "low_stock_products",
            'date_range'
        ]


class SalesReportSerializer(serializers.ModelSerializer):
    generated_by_name = serializers.CharField(source="generated_by.username", read_only=True)

    class Meta:
        model = SalesReport
        fields = [
            "id",
            "date",
            "total_sales",
            "total_invoices",
            "generated_by",
            "generated_by_name",
        ]


class SalesSummaryQuerySerializer(serializers.Serializer):
    date = serializers.DateField(required=False)


class InvoiceLineInputSerializer(serializers.Serializer):
    product_id = serializers.CharField()
    quantity = serializers.IntegerField(min_value=1)
    discount = serializers.DecimalField(max_digits=10, decimal_places=2, default=0.00)


class CreateInvoiceSerializer(serializers.Serializer):
    client_name = serializers.CharField()
    tax = serializers.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = serializers.ChoiceField(choices=["PENDING", "COMPLETED", "CANCELLED", "CREDIT"], default="PENDING")
    reason = serializers.CharField(required=False, allow_blank=True)
    advance_paid = serializers.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    lines = serializers.ListSerializer(child=InvoiceLineInputSerializer())
    due_date = serializers.DateField(required=False)

    def validate_lines(self, value):
        if not value:
            raise serializers.ValidationError("At least one line item is required.")
        return value


class InventoryQuerySerializer(serializers.Serializer):
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
