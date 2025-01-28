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
            "date",
            "client_name",
            "cashier",
            "cashier_name",
            "status",
            "total",
            "tax",
            "paid_amount",
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
            "date",
            "generated_by",
            "generated_by_name",
            "total_products",
            "expired_products",
            "low_stock_products",
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
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    date = serializers.DateField(required=False)


class CreateInvoiceSerializer(serializers.Serializer):
    client_name = serializers.CharField()
    tax = serializers.FloatField(required=False)
    lines = serializers.ListField(
        child=serializers.DictField()
    )


class InventoryQuerySerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
