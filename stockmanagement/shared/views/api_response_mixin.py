"""APIResponseMixin for standardized API responses in DRF views."""

from __future__ import annotations

import logging
from typing import Any

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

logger = logging.getLogger(__name__)


class APIResponseMixin:
    """Mixin class for standardized API responses in DRF views."""

    def success(
        self,
        message: str = "Success",
        data: Any = None,
        status_code: int = status.HTTP_200_OK,
    ) -> Response:
        """
        Return a successful response.

        Args:
            message: Success message
            data: Response data
            status_code: HTTP status code

        Returns:
            Response with success format
        """
        response_data: dict[str, Any] = {
            "success": True,
            "message": message,
            "data": data,
            "status_code": status_code,
        }
        return Response(response_data, status=status_code)

    def error(
        self,
        message: str = "Error",
        errors: Any = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        code: str = "ERROR",
    ) -> Response:
        """
        Return an error response.

        Args:
            message: Error message
            errors: Error details (string, list, or dict)
            status_code: HTTP status code
            code: Error code

        Returns:
            Response with error format
        """
        details: dict[str, Any] = {}

        if isinstance(errors, str):
            details = {"message": errors}
        elif isinstance(errors, list):
            details = {"messages": errors}
        elif isinstance(errors, dict):
            details = errors

        response_data: dict[str, Any] = {
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": details,
            },
            "status_code": status_code,
        }
        return Response(response_data, status=status_code)

    def format_validation_errors(self, errors: dict[str, Any]) -> dict[str, Any]:
        """
        Format Django/DRF validation errors into a concise and precise format.

        Args:
            errors: Validation errors from serializer or form

        Returns:
            Formatted error dictionary with concise messages
        """
        formatted_errors: dict[str, Any] = {}

        for field, error_list in errors.items():
            if isinstance(error_list, list):
                # Get the first error message for each field (most relevant)
                if error_list:
                    error_msg = error_list[0]
                    # If it's a dict, extract the message
                    if isinstance(error_msg, dict):
                        # Handle nested errors
                        nested_errors = []
                        for key, value in error_msg.items():
                            if isinstance(value, list):
                                nested_errors.append(f"{key}: {value[0]}")
                            else:
                                nested_errors.append(f"{key}: {value}")
                        formatted_errors[field] = "; ".join(nested_errors)
                    else:
                        formatted_errors[field] = str(error_msg)
            elif isinstance(error_list, dict):
                # Handle nested validation errors
                nested = self.format_validation_errors(error_list)
                formatted_errors[field] = nested
            else:
                formatted_errors[field] = str(error_list)

        return formatted_errors

    def handle_validation_error(
        self,
        serializer: Any,
        message: str = "Validation error",
        code: str = "VALIDATION_ERROR",
    ) -> Response:
        """
        Handle validation errors from a serializer and return a formatted error response.

        Args:
            serializer: DRF serializer instance with errors
            message: Custom error message (will be overridden if meaningful errors found)
            code: Error code

        Returns:
            Response with formatted validation errors
        """
        formatted_errors = self.format_validation_errors(serializer.errors)

        error_messages = []
        for field, error_msg in formatted_errors.items():
            if error_msg:
                error_text = str(error_msg)
                if field.lower() not in error_text.lower():
                    field_name = field.replace("_", " ").title()
                    error_messages.append(f"{field_name}: {error_text}")
                else:
                    error_messages.append(error_text)

        meaningful_message = ". ".join(error_messages) if error_messages else message

        logger.warning(
            f"Validation error: {meaningful_message}",
            extra={"errors": formatted_errors, "raw_errors": serializer.errors},
        )

        return self.error(
            message=meaningful_message,
            errors=formatted_errors,
            status_code=status.HTTP_400_BAD_REQUEST,
            code=code,
        )

    def paginated_response(
        self,
        request: Any,
        queryset: Any,
        serializer_class: Any,
        message: str = "Data retrieved successfully",
        context: dict[str, Any] | None = None,
    ) -> Response:
        """
        Return a paginated response.

        Args:
            request: DRF request object
            queryset: QuerySet to paginate
            serializer_class: Serializer class to use
            message: Success message
            context: Optional context for serializer

        Returns:
            Response with paginated format
        """
        paginator = PageNumberPagination()
        page_size = request.query_params.get("page_size", 10)
        try:
            page_size = int(page_size)
        except (ValueError, TypeError):
            page_size = 10

        paginator.page_size = page_size
        page = paginator.paginate_queryset(queryset, request)

        if page is not None:
            serializer = serializer_class(page, many=True, context=context or {"request": request})
            paginated_data = paginator.get_paginated_response(serializer.data)

            response_data: dict[str, Any] = {
                "success": True,
                "message": message,
                "data": serializer.data,
                "status_code": status.HTTP_200_OK,
                "pagination": {
                    "count": paginated_data.data.get("count", 0),
                    "next": paginated_data.data.get("next"),
                    "previous": paginated_data.data.get("previous"),
                    "current_page": paginator.page.number if paginator.page else 1,
                    "total_pages": paginator.page.paginator.num_pages if paginator.page else 0,
                    "page_size": page_size,
                },
            }
            return Response(response_data, status=status.HTTP_200_OK)

        # If no pagination needed, return all data
        serializer = serializer_class(queryset, many=True, context=context or {"request": request})
        return self.success(
            message=message,
            data=serializer.data,
            status_code=status.HTTP_200_OK,
        )

    def handle_exception(self, exc: Exception) -> Response:
        """
        Handle exceptions and return standardized error response.

        Args:
            exc: Exception to handle

        Returns:
            Response with error format
        """
        from shared.exceptions.base import BaseAPIException

        # Handle BaseAPIException
        if isinstance(exc, BaseAPIException):
            # Only log with traceback for server errors (500+), not for business logic errors
            if exc.status_code >= 500:
                logger.error(
                    f"[{exc.code}] {exc.detail}",
                    exc_info=True,
                    extra={
                        "error_code": exc.code,
                        "status_code": exc.status_code,
                        "details": exc.details,
                    },
                )
            else:
                # Business logic errors: log without traceback, just structured info
                logger.warning(
                    f"[{exc.code}] {exc.detail}",
                    extra={
                        "error_code": exc.code,
                        "status_code": exc.status_code,
                        "details": exc.details,
                    },
                )
            return self.error(
                message=exc.detail,
                status_code=exc.status_code,
                code=exc.code,
                errors=exc.details,
            )

        # Handle DRF ValidationError
        if isinstance(exc, ValidationError):
            formatted_errors = self.format_validation_errors(exc.detail)
            logger.warning(f"ValidationError: {str(exc)}", extra={"errors": formatted_errors})
            return self.error(
                message="Validation error",
                errors=formatted_errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
            )

        # Handle other exceptions
        logger.exception(f"Unhandled exception: {type(exc).__name__}", exc_info=exc)
        return self.error(
            message="An internal server error occurred",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_ERROR",
        )
