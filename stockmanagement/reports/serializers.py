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
            'reason',
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


class InvoiceLineInputSerializer(serializers.Serializer):
    product_id = serializers.CharField()
    quantity = serializers.IntegerField(min_value=1)
    discount = serializers.DecimalField(
        max_digits=10, decimal_places=3, default=0.00
    )


class CreateInvoiceSerializer(serializers.Serializer):
    client_name = serializers.CharField()
    tax = serializers.DecimalField(
        max_digits=10, decimal_places=3, default=0.00
    )
    status = serializers.ChoiceField(choices=['COMPLETED', 'CANCELLED', 'CREDIT'])
    reason = serializers.CharField(required=False, allow_blank=True)
    due_date = serializers.DateField(
        required=False, allow_null=True, default=None
    )
    advance_paid = serializers.DecimalField(
        max_digits=15, decimal_places=3, default=0.00
    )
    remaining_amount = serializers.DecimalField(
        max_digits=15, decimal_places=3, read_only=True
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

    def validate(self, data):
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {'end_date': 'End date must be greater than start date.'}
            )
        return data


class InvoiceQuerySerializer(serializers.Serializer):
    invoice_id = serializers.CharField(required=True)


class PayDebtSerializer(serializers.Serializer):
    invoice_id = serializers.CharField(required=True)
    amount = serializers.DecimalField(
        max_digits=15, decimal_places=3, required=True
    )


class ReportQuerySerializer(serializers.Serializer):
    report_type = serializers.ChoiceField(choices=Report.REPORT_TYPE_CHOICES)
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)

    def validate(self, data):
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {'end_date': 'End date must be greater than start date.'}
            )
        return data


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


class InventoryReportSerializers(serializers.ModelSerializer):
    class Meta:
        model = InventoryReport
        fields = [
            'id',
            'start_date',
            'end_date',
            'total_products',
            'expired_products',
            'low_stock_products',
            'data',
            'notes',
            'created_at'
        ]


class SalesReportSerializers(serializers.ModelSerializer):
    class Meta:
        model = SalesReport
        fields = [
            'id',
            'date',
            'start_date',
            'end_date',
            'total_sales',
            'total_invoices',
            'data',
            'notes'
        ]


class ReportListSerializer(serializers.ModelSerializer):
    inventory_report = InventoryReportSerializers(read_only=True)
    sales_report = SalesReportSerializers(read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            'id',
            'type',
            'generated_at',
            'generated_by',
            'description',
            'file_url',
            'inventory_report',
            'sales_report',
        ]

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file_path and request:
            return request.build_absolute_uri(obj.file_path.url)
        return None


class DownloadReportSerializer(serializers.Serializer):
    report_id = serializers.UUIDField(required=True)


class UpdateInvoiceSerializer(serializers.Serializer):
    invoice_id = serializers.UUIDField(required=True)
    client_name = serializers.CharField(required=False)
    status = serializers.ChoiceField(
        choices=['COMPLETED', 'CANCELLED', 'CREDIT'], required=False
    )
    reason = serializers.CharField(required=False, allow_blank=True)
    due_date = serializers.DateField(required=False, allow_null=True)
    advance_paid = serializers.DecimalField(max_digits=15, decimal_places=3, required=False)
    lines = serializers.ListSerializer(child=InvoiceLineInputSerializer(), required=False)

    def validate_lines(self, value):
        if value is not None and not value:
            raise serializers.ValidationError(
                'At least one line item is required if lines are provided.'
            )
        return value

    def validate(self, data):
        if data.get('status') == 'CREDIT':
            if not data.get('due_date'):
                raise serializers.ValidationError(
                    {'due_date': 'This field is required when the status is CREDIT.'}
                )
            if not data.get('reason'):
                raise serializers.ValidationError(
                    {'reason': 'This field is required when the status is CREDIT.'}
                )
        return data
