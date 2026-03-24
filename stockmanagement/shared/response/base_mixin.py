"""Base response mixin with common logic for Django and DRF responses."""

from __future__ import annotations

from typing import Any


class BaseResponseMixin:
    """Base mixin with common response logic for both Django and DRF."""

    @staticmethod
    def _format_error_details(errors: str | list[str] | dict[str, Any] | None) -> dict[str, Any]:
        """
        Format error details into a consistent structure.

        Args:
            errors: Error details (string, list, or dict)

        Returns:
            Formatted error details dictionary
        """
        details: dict[str, Any] = {}

        if isinstance(errors, str):
            details = {"message": errors}
        elif isinstance(errors, list):
            details = {"messages": errors}
        elif isinstance(errors, dict):
            details = errors

        return details

    @staticmethod
    def _format_validation_errors(errors: dict[str, Any]) -> dict[str, Any]:
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
                nested = BaseResponseMixin._format_validation_errors(error_list)
                formatted_errors[field] = nested
            else:
                formatted_errors[field] = str(error_list)

        return formatted_errors

    @staticmethod
    def _build_success_response(
        message: str,
        data: Any = None,
        status_code: int = 200,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Build success response data structure.

        Args:
            message: Success message
            data: Response data
            status_code: HTTP status code
            **kwargs: Additional fields

        Returns:
            Response data dictionary
        """
        return {
            "success": True,
            "message": message,
            "data": data,
            "status_code": status_code,
            **kwargs,
        }

    @staticmethod
    def _build_error_response(
        message: str,
        code: str,
        errors: str | list[str] | dict[str, Any] | None = None,
        status_code: int = 400,
    ) -> dict[str, Any]:
        """
        Build error response data structure.

        Args:
            message: Error message
            code: Error code
            errors: Error details
            status_code: HTTP status code

        Returns:
            Error response data dictionary
        """
        details = BaseResponseMixin._format_error_details(errors)

        return {
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": details,
            },
            "status_code": status_code,
        }
