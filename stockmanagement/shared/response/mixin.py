"""ResponseMixin for standardized API responses."""

from typing import Any

from django.http import JsonResponse


class ResponseMixin:
    """Mixin class for standardized API responses."""

    @staticmethod
    def success(
        message: str,
        data: dict[str, Any] | list[Any] | Any | None = None,
        status_code: int = 200,
        **kwargs: Any,
    ) -> JsonResponse:
        """Return a successful response.

        Args:
            message: Success message (required)
            data: Response data (dict, list, or any serializable object)
            status_code: HTTP status code (default: 200)
            **kwargs: Additional fields to include in response

        Returns:
            JsonResponse with standardized format

        Example:
            return ResponseMixin.success(
                message="Item created successfully",
                data={"id": 1, "name": "Test"},
                status_code=201
            )
        """
        response_data: dict[str, Any] = {
            "status": True,
            "message": message,
            "data": data,
            "status_code": status_code,
            **kwargs,
        }

        response = JsonResponse(response_data, status=status_code)
        return response

    @staticmethod
    def error(
        message: str,
        errors: str | list[str] | dict[str, Any] | None = None,
        status_code: int = 400,
        code: str = "BAD_REQUEST",
    ) -> JsonResponse:
        """Return an error response.

        Args:
            message: Error message (required)
            errors: Error details (string, list of strings, or dict)
            status_code: HTTP status code (default: 400)
            code: Error code (default: "BAD_REQUEST")

        Returns:
            JsonResponse with standardized error format

        Example:
            return ResponseMixin.error(
                message="Resource not found",
                errors={"id": "Invalid ID"},
                status_code=404,
                code="NOT_FOUND"
            )
        """
        details: dict[str, Any] = {}

        if isinstance(errors, str):
            details = {"message": errors}
        elif isinstance(errors, list):
            details = {"messages": errors}
        elif isinstance(errors, dict):
            details = errors

        response_data: dict[str, Any] = {
            "error": {
                "code": code,
                "message": message,
                "details": details,
            }
        }

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
        """Return a paginated response.

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

        Example:
            return ResponseMixin.paginated_response(
                data=items,
                message="Items retrieved successfully",
                page=1,
                page_size=10,
                total=100
            )
        """
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0

        response_data: dict[str, Any] = {
            "status": True,
            "message": message,
            "data": data,
            "status_code": status_code,
            "pagination": {
                "next": None,  # Could be enhanced with actual URLs
                "previous": None,  # Could be enhanced with actual URLs
                "count": total,
                "current_page": page,
                "total_pages": total_pages,
            },
            **kwargs,
        }

        response = JsonResponse(response_data, status=status_code)
        return response

    @staticmethod
    def from_exception(exception: Exception) -> JsonResponse:
        """Convert an exception to a standardized error response.

        Args:
            exception: Exception instance (preferably BaseAPIException)

        Returns:
            JsonResponse with error format
        """
        from shared.exceptions.base import BaseAPIException

        if isinstance(exception, BaseAPIException):
            return ResponseMixin.error(
                message=exception.detail,
                status_code=exception.status_code,
                code=exception.code,
                errors=exception.details if exception.details else None,
            )

        return ResponseMixin.error(
            message=str(exception), status_code=500, code="INTERNAL_ERROR"
        )

