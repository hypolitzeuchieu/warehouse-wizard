"""Django-specific response mixin using JsonResponse."""

from __future__ import annotations

from typing import Any

from django.http import JsonResponse

from shared.response.base_mixin import BaseResponseMixin


class DjangoResponseMixin(BaseResponseMixin):
    """Mixin for standardized API responses using Django JsonResponse."""

    @staticmethod
    def success(
        message: str,
        data: dict[str, Any] | list[Any] | Any | None = None,
        status_code: int = 200,
        **kwargs: Any,
    ) -> JsonResponse:
        """
        Return a successful response using JsonResponse.

        Args:
            message: Success message (required)
            data: Response data (dict, list, or any serializable object)
            status_code: HTTP status code (default: 200)
            **kwargs: Additional fields to include in response

        Returns:
            JsonResponse with standardized format
        """
        response_data = DjangoResponseMixin._build_success_response(
            message=message,
            data=data,
            status_code=status_code,
            **kwargs,
        )
        return JsonResponse(response_data, status=status_code)

    @staticmethod
    def error(
        message: str,
        errors: str | list[str] | dict[str, Any] | None = None,
        status_code: int = 400,
        code: str = "BAD_REQUEST",
    ) -> JsonResponse:
        """
        Return an error response using JsonResponse.

        Args:
            message: Error message (required)
            errors: Error details (string, list of strings, or dict)
            status_code: HTTP status code (default: 400)
            code: Error code (default: "BAD_REQUEST")

        Returns:
            JsonResponse with standardized error format
        """
        response_data = DjangoResponseMixin._build_error_response(
            message=message,
            code=code,
            errors=errors,
            status_code=status_code,
        )
        return JsonResponse(data=response_data, status=status_code)

    @staticmethod
    def paginated_response(
        data: list[Any],
        message: str = "Success",
        page: int = 1,
        page_size: int = 10,
        total: int = 0,
        status_code: int = 200,
        **kwargs: Any,
    ) -> JsonResponse:
        """
        Return a paginated response using JsonResponse.

        Args:
            data: List of items for current page
            message: Success message (default: "Success")
            page: Current page number (1-indexed)
            page_size: Number of items per page
            total: Total number of items
            status_code: HTTP status code (default: 200)
            **kwargs: Additional fields to include in response

        Returns:
            JsonResponse with paginated format
        """
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0

        response_data = DjangoResponseMixin._build_success_response(
            message=message,
            data=data,
            status_code=status_code,
            pagination={
                "next": None,
                "previous": None,
                "count": total,
                "current_page": page,
                "total_pages": total_pages,
            },
            **kwargs,
        )
        return JsonResponse(response_data, status=status_code)

    @staticmethod
    def from_exception(exception: Exception) -> JsonResponse:
        """
        Convert an exception to a standardized error response.

        Args:
            exception: Exception instance (preferably BaseAPIException)

        Returns:
            JsonResponse with error format
        """
        from shared.exceptions.base import BaseAPIException

        if isinstance(exception, BaseAPIException):
            return DjangoResponseMixin.error(
                message=exception.detail,
                status_code=exception.status_code,
                code=exception.code,
                errors=exception.details if exception.details else None,
            )

        return DjangoResponseMixin.error(
            message=str(exception), status_code=500, code="INTERNAL_ERROR"
        )
