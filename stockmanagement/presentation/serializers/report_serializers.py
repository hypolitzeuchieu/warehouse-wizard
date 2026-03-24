"""Report serializers."""

from rest_framework import serializers

from application.dto.report_dto import ReportCreateDTO, ReportResponseDTO


class SalesReportQuerySerializer(serializers.Serializer):
    """Serializer for sales report query parameters."""

    business_id = serializers.UUIDField(required=True)
    start_date = serializers.DateTimeField(required=False, allow_null=True)
    end_date = serializers.DateTimeField(required=False, allow_null=True)
    output_format = serializers.ChoiceField(
        choices=["pdf", "word"],
        required=False,
        default="pdf",
        help_text="Output format: 'pdf' for PDF, 'word' for Word document",
    )
    report_type = serializers.ChoiceField(
        choices=["sales", "inventory", "stock"],
        required=False,
        default="sales",
        help_text="Type of report: 'sales' for sales report, 'inventory' for inventory report, 'stock' for stock report",
    )

    def to_dto(self) -> ReportCreateDTO:
        """Convert validated data to ReportCreateDTO."""
        return ReportCreateDTO(
            business_id=self.validated_data["business_id"],
            report_type=self.validated_data.get("report_type", "sales"),
            format=self.validated_data.get("output_format", "pdf"),
            start_date=self.validated_data.get("start_date"),
            end_date=self.validated_data.get("end_date"),
        )


class TopProductReportSerializer(serializers.Serializer):
    """Serializer for top product in sales report."""

    product_id = serializers.UUIDField()
    product_name = serializers.CharField()
    total_quantity_sold = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    number_of_sales = serializers.IntegerField()


class TopCustomerReportSerializer(serializers.Serializer):
    """Serializer for top customer in sales report."""

    customer_id = serializers.UUIDField(allow_null=True)
    customer_name = serializers.CharField()
    total_purchases = serializers.DecimalField(max_digits=15, decimal_places=2)
    number_of_invoices = serializers.IntegerField()


class SalesByPaymentMethodSerializer(serializers.Serializer):
    """Serializer for sales breakdown by payment method."""

    payment_method = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    number_of_invoices = serializers.IntegerField()


class SalesByStatusSerializer(serializers.Serializer):
    """Serializer for sales breakdown by status."""

    status = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    number_of_invoices = serializers.IntegerField()


class SalesReportResponseSerializer(serializers.Serializer):
    """Serializer for sales report response."""

    business_id = serializers.UUIDField()
    period_start = serializers.DateTimeField()
    period_end = serializers.DateTimeField()
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_invoices = serializers.IntegerField()
    total_items_sold = serializers.IntegerField()
    average_invoice_value = serializers.DecimalField(max_digits=15, decimal_places=2)
    sales_by_payment_method = SalesByPaymentMethodSerializer(many=True)
    sales_by_status = SalesByStatusSerializer(many=True)
    top_products = TopProductReportSerializer(many=True)
    top_customers = TopCustomerReportSerializer(many=True)
    generated_at = serializers.DateTimeField()


class ReportCreateSerializer(serializers.Serializer):
    """Serializer for creating a report."""

    business_id = serializers.UUIDField(required=True)
    report_type = serializers.ChoiceField(
        choices=["sales", "inventory", "stock"],
        required=True,
        help_text="Type of report: 'sales' for sales report, 'inventory' for inventory report, 'stock' for stock report",
    )
    format = serializers.ChoiceField(
        choices=["pdf", "word"],
        required=False,
        default="pdf",
        help_text="Report format: 'pdf' or 'word'",
    )
    start_date = serializers.DateTimeField(required=False, allow_null=True)
    end_date = serializers.DateTimeField(required=False, allow_null=True)

    def to_dto(self) -> ReportCreateDTO:
        """Convert to DTO."""
        return ReportCreateDTO(
            business_id=self.validated_data["business_id"],
            report_type=self.validated_data.get("report_type", "sales"),
            format=self.validated_data.get("format", "pdf"),
            start_date=self.validated_data.get("start_date"),
            end_date=self.validated_data.get("end_date"),
        )


class ReportResponseSerializer(serializers.Serializer):
    """Serializer for report response."""

    id = serializers.UUIDField()
    business_id = serializers.UUIDField()
    report_type = serializers.CharField()
    format = serializers.CharField()
    status = serializers.CharField()
    start_date = serializers.DateTimeField(allow_null=True, required=False)
    end_date = serializers.DateTimeField(allow_null=True, required=False)
    file_url = serializers.URLField(allow_null=True, required=False)
    file_size = serializers.IntegerField(allow_null=True, required=False)
    generated_by = serializers.UUIDField(allow_null=True, required=False)
    error_message = serializers.CharField(allow_null=True, required=False)
    metadata = serializers.DictField(required=False)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    @classmethod
    def from_dto(cls, dto: ReportResponseDTO) -> dict:
        """Convert DTO to serializer data."""
        serializer = cls(
            data={
                "id": dto.id,
                "business_id": dto.business_id,
                "report_type": dto.report_type,
                "format": dto.format,
                "status": dto.status,
                "start_date": dto.start_date,
                "end_date": dto.end_date,
                "file_url": dto.file_url,
                "file_size": dto.file_size,
                "generated_by": dto.generated_by,
                "error_message": dto.error_message,
                "metadata": dto.metadata,
                "created_at": dto.created_at,
                "updated_at": dto.updated_at,
            }
        )
        serializer.is_valid(raise_exception=True)
        return serializer.data


class ReportListQuerySerializer(serializers.Serializer):
    """Serializer for report list query parameters."""

    business_id = serializers.UUIDField(required=True)
    report_type = serializers.ChoiceField(
        choices=["sales", "inventory", "stock"],
        required=False,
        allow_null=True,
    )
    status = serializers.ChoiceField(
        choices=["generating", "completed", "failed"],
        required=False,
        allow_null=True,
    )
    start_date = serializers.DateTimeField(required=False, allow_null=True)
    end_date = serializers.DateTimeField(required=False, allow_null=True)
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    page_size = serializers.IntegerField(required=False, min_value=1, max_value=500, default=20)
