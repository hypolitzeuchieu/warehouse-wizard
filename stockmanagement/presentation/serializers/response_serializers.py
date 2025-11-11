"""Response serializers for Swagger documentation."""

from __future__ import annotations

from typing import Any

from drf_yasg import openapi
from rest_framework import serializers


class SuccessResponseSerializer(serializers.Serializer):
    """Serializer for success responses."""

    success = serializers.BooleanField(default=True)
    message = serializers.CharField()
    data = serializers.JSONField(required=False, allow_null=True)
    status_code = serializers.IntegerField()


class ErrorResponseSerializer(serializers.Serializer):
    """Serializer for error responses."""

    success = serializers.BooleanField(default=False)
    error = serializers.DictField(
        child=serializers.JSONField(),
        help_text="Error details with code, message, and details",
    )
    status_code = serializers.IntegerField()


class PaginatedResponseSerializer(serializers.Serializer):
    """Serializer for paginated responses."""

    success = serializers.BooleanField(default=True)
    message = serializers.CharField()
    data = serializers.ListField(child=serializers.JSONField())
    status_code = serializers.IntegerField()
    pagination = serializers.DictField(
        child=serializers.IntegerField(),
        help_text="Pagination metadata",
    )


# Helper functions for Swagger schema generation
def get_success_response_schema(data_schema: Any = None) -> openapi.Schema:
    """Generate success response schema for Swagger."""
    properties = {
        "success": openapi.Schema(type=openapi.TYPE_BOOLEAN, default=True),
        "message": openapi.Schema(type=openapi.TYPE_STRING),
        "status_code": openapi.Schema(type=openapi.TYPE_INTEGER),
    }
    
    if data_schema:
        properties["data"] = data_schema
    else:
        properties["data"] = openapi.Schema(
            type=openapi.TYPE_OBJECT,
            description="Response data",
        )
    
    return openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties=properties,
    )


def get_error_response_schema() -> openapi.Schema:
    """Generate error response schema for Swagger."""
    return openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "success": openapi.Schema(type=openapi.TYPE_BOOLEAN, default=False),
            "error": openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "code": openapi.Schema(type=openapi.TYPE_STRING),
                    "message": openapi.Schema(type=openapi.TYPE_STRING),
                    "details": openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        description="Additional error details",
                    ),
                },
            ),
            "status_code": openapi.Schema(type=openapi.TYPE_INTEGER),
        },
    )


def get_paginated_response_schema(item_schema: Any = None) -> openapi.Schema:
    """Generate paginated response schema for Swagger."""
    return openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "success": openapi.Schema(type=openapi.TYPE_BOOLEAN, default=True),
            "message": openapi.Schema(type=openapi.TYPE_STRING),
            "data": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=item_schema or openapi.Schema(type=openapi.TYPE_OBJECT),
            ),
            "status_code": openapi.Schema(type=openapi.TYPE_INTEGER),
            "pagination": openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "count": openapi.Schema(type=openapi.TYPE_INTEGER),
                    "current_page": openapi.Schema(type=openapi.TYPE_INTEGER),
                    "total_pages": openapi.Schema(type=openapi.TYPE_INTEGER),
                    "page_size": openapi.Schema(type=openapi.TYPE_INTEGER),
                    "next": openapi.Schema(type=openapi.TYPE_STRING, x_nullable=True),
                    "previous": openapi.Schema(type=openapi.TYPE_STRING, x_nullable=True),
                },
            ),
        },
    )

