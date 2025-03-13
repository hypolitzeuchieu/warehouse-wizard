from __future__ import annotations

from reports.models import InventoryReport
from reports.models import Invoice
from reports.models import InvoiceArchive
from reports.models import InvoiceArchiveLine
from reports.models import InvoiceLine
from reports.models import Report
from reports.models import SalesReport
from rest_framework import serializers


class InvoiceLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = InvoiceLine
        fields = [
            'id',
            'invoice',
            'product',
            'product_name',
            'quantity',
            'unit_price',
            'discount',
            'line_total',
        ]


class InvoiceSerializer(serializers.ModelSerializer):
    lines = InvoiceLineSerializer(many=True, read_only=True)
    cashier_name = serializers.CharField(
        source='cashier.username', read_only=True
    )
    remaining_amount = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            'id',
            'number',
            'created_at',
            'client_name',
            'cashier',
            'cashier_name',
            'status',
            'total',
            'tax',
            'advance_paid',
            'remaining_amount',
            'refund_amount',
            'due_date',
            'is_credit_settled',
            'lines',
        ]

    def get_remaining_amount(self, obj):
        """
        Renvoie le montant restant à payer pour la facture.
        """
        return obj.remaining_amount

    def create(self, validated_data):
        # Gestion des lignes de facture lors de la création
        lines_data = self.context['request'].data.pop('lines', [])
        invoice = Invoice.objects.create(**validated_data)

        for line_data in lines_data:
            line_data['invoice'] = invoice
            InvoiceLine.objects.create(**line_data)
        return invoice


class ReportSerializer(serializers.ModelSerializer):
    generated_by_name = serializers.CharField(
        source='generated_by.username', read_only=True
    )

    class Meta:
        model = Report
        fields = [
            'id',
            'type',
            'generated_at',
            'generated_by',
            'generated_by_name',
            'file_path',
            'description',
        ]


class InventoryReportSerializer(serializers.ModelSerializer):
    generated_by_name = serializers.CharField(
        source='generated_by.username', read_only=True
    )

    class Meta:
        model = InventoryReport
        fields = [
            'id',
            'created_at',
            'generated_by',
            'generated_by_name',
            'total_products',
            'expired_products',
            'low_stock_products',
            'date_range',
        ]


class SalesReportSerializer(serializers.ModelSerializer):
    generated_by_name = serializers.CharField(
        source='generated_by.username', read_only=True
    )

    class Meta:
        model = SalesReport
        fields = [
            'id',
            'date',
            'total_sales',
            'total_invoices',
            'generated_by',
            'generated_by_name',
        ]


class SalesSummaryQuerySerializer(serializers.Serializer):
    date = serializers.DateField(required=False)


class InvoiceLineInputSerializer(serializers.Serializer):
    product_id = serializers.CharField()
    quantity = serializers.IntegerField(min_value=1)
    discount = serializers.DecimalField(
        max_digits=10, decimal_places=2, default=0.00
    )


class CreateInvoiceSerializer(serializers.Serializer):
    client_name = serializers.CharField()
    tax = serializers.DecimalField(
        max_digits=10, decimal_places=2, default=0.00
    )
    status = serializers.ChoiceField(choices=['COMPLETED', 'CANCELLED', 'CREDIT'])
    reason = serializers.CharField(required=False, allow_blank=True)
    due_date = serializers.DateField(
        required=False, allow_null=True, default=None
    )
    advance_paid = serializers.DecimalField(
        max_digits=10, decimal_places=2, default=0.00
    )
    remaining_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    lines = serializers.ListSerializer(child=InvoiceLineInputSerializer())

    def validate_lines(self, value):
        if not value:
            raise serializers.ValidationError(
                'At least one line item is required.'
            )
        return value

    def validate(self, data):
        if data.get('status') == 'CREDIT':
            if not data.get('due_date'):
                raise serializers.ValidationError(
                    {
                        'due_date': 'This field is required when the status is CREDIT.'
                    }
                )
            if not data.get('reason'):
                raise serializers.ValidationError(
                    {
                        'reason': 'This field is required when the status is CREDIT.'
                    }
                )
        return data


class InventoryQuerySerializer(serializers.Serializer):
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    page_size = serializers.IntegerField(required=False, min_value=1, default=10)


class InvoiceQuerySerializer(serializers.Serializer):
    invoice_id = serializers.CharField(required=True)


class PayDebtSerializer(serializers.Serializer):
    invoice_id = serializers.CharField(required=True)
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=True
    )


class InvoiceArchiveLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = InvoiceArchiveLine
        fields = '__all__'


class InvoiceArchiveSerializer(serializers.ModelSerializer):
    lines = InvoiceArchiveLineSerializer(many=True, read_only=True)
    cashier_name = serializers.CharField(
        source='cashier.username', read_only=True
    )

    class Meta:
        model = InvoiceArchive
        fields = [
            'id', 'number', 'invoice_id', 'created_at', 'client_name', 'cashier',
            'cashier_name', 'status', 'total', 'tax', 'advance_paid', 'remaining_amount',
            'refund_amount', 'due_date', 'is_credit_settled', 'lines',
        ]
