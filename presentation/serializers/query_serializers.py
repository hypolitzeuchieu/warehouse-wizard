"""Query serializers for common query parameters."""

from __future__ import annotations

from uuid import UUID

from rest_framework import serializers


class BusinessIdQuerySerializer(serializers.Serializer):
    """Serializer for validating business_id query parameter."""

    business_id = serializers.UUIDField(required=True, help_text="Business UUID")

    def validate_business_id(self, value: UUID) -> UUID:
        """Validate business_id format."""
        if not value:
            raise serializers.ValidationError("business_id is required")
        return value


class OptionalBusinessIdQuerySerializer(serializers.Serializer):
    """Serializer for optional business_id query parameter."""

    business_id = serializers.UUIDField(
        required=False, allow_null=True, help_text="Business UUID (optional)"
    )
