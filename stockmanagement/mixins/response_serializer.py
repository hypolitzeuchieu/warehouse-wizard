from rest_framework import serializers


class BaseResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=True)
    message = serializers.CharField()


class PaginationSerializer(serializers.Serializer):
    next = serializers.URLField(allow_null=True, required=False)
    previous = serializers.URLField(allow_null=True, required=False)
    count = serializers.IntegerField()
    current_page = serializers.IntegerField()
    total_pages = serializers.IntegerField()
    page_size = serializers.IntegerField()


class ErrorDetailSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    details = serializers.DictField(required=False)


class ErrorResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=False)
    error = ErrorDetailSerializer()


class ValidationErrorFieldSerializer(serializers.Serializer):
    field_name = serializers.CharField()
    error_message = serializers.CharField()


class ValidationErrorDetailsSerializer(serializers.Serializer):
    fields = serializers.DictField(child=serializers.CharField())


class ValidationErrorResponseSerializer(ErrorResponseSerializer):
    error = ErrorDetailSerializer(
        default={
            "code": "VALIDATION_FAILED",
            "message": "Input validation failed",
            "details": {"fields": {}},
        }
    )


def create_response_serializer(data_serializer=None, many=False):
    """Factory for creating dynamic success response serializers"""

    class DynamicSuccessResponseSerializer(BaseResponseSerializer):
        data = (
            data_serializer(many=many) if data_serializer else serializers.DictField(required=False)
        )

    return DynamicSuccessResponseSerializer


def create_paginated_response_serializer(item_serializer):
    """Factory for creating dynamic paginated response serializers"""

    class DynamicPaginatedResponseSerializer(BaseResponseSerializer):
        data = item_serializer(many=True)
        pagination = PaginationSerializer()

    return DynamicPaginatedResponseSerializer


def create_list_response_serializer(item_serializer):
    """Factory for creating list response serializers"""

    class DynamicListResponseSerializer(BaseResponseSerializer):
        data = item_serializer(many=True)

    return DynamicListResponseSerializer


# Common response serializers
SuccessResponseSerializer = create_response_serializer()
DeletedResponseSerializer = create_response_serializer()
PaginatedResponseSerializer = create_paginated_response_serializer(serializers.DictField())
