"""Helper class for using APIResponseMixin in functional views."""

from __future__ import annotations

from typing import Any

from rest_framework.request import Request
from rest_framework.response import Response

from shared.views.api_response_mixin import APIResponseMixin


class FunctionalViewHelper(APIResponseMixin):
    """
    Helper class that provides APIResponseMixin methods for functional views.
    
    Usage:
        helper = FunctionalViewHelper()
        return helper.success(message="Success", data={...})
        return helper.error(message="Error", errors={...})
        return helper.handle_validation_error(serializer, message="Validation failed")
    """

    def __init__(self, request: Request | None = None):
        """
        Initialize the helper.
        
        Args:
            request: Optional request object for context
        """
        self.request = request

    def handle_serializer_validation(
        self,
        serializer: Any,
        message: str = "Validation failed",
        code: str = "VALIDATION_ERROR",
    ) -> Response | None:
        """
        Check if serializer is valid and return error response if not.
        
        Args:
            serializer: DRF serializer instance
            message: Error message
            code: Error code
            
        Returns:
            Response with validation errors if invalid, None if valid
        """
        if not serializer.is_valid():
            return self.handle_validation_error(
                serializer=serializer,
                message=message,
                code=code,
            )
        return None

