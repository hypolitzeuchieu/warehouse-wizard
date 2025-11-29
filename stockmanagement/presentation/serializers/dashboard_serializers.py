"""Dashboard serializers."""

from rest_framework import serializers


class DashboardSummaryQuerySerializer(serializers.Serializer):
    """Serializer for dashboard summary query parameters."""

    business_id = serializers.UUIDField(required=True)
    start_date = serializers.DateTimeField(
        required=False,
        allow_null=True,
        help_text="Start date (ISO format, optional, defaults to start of current week)",
    )
    end_date = serializers.DateTimeField(
        required=False,
        allow_null=True,
        help_text="End date (ISO format, optional, defaults to now)",
    )


class DashboardDailyQuerySerializer(serializers.Serializer):
    """Serializer for daily dashboard query parameters."""

    business_id = serializers.UUIDField(required=True)
    start_date = serializers.DateTimeField(
        required=False,
        allow_null=True,
        help_text="Start date (ISO format, optional, defaults to start of current week)",
    )
    end_date = serializers.DateTimeField(
        required=False,
        allow_null=True,
        help_text="End date (ISO format, optional, defaults to now)",
    )
    recent_sales_limit = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        default=10,
        help_text="Number of recent sales to return (1-100, default: 10)",
    )
