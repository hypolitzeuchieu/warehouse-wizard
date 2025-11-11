from rest_framework.response import Response
from rest_framework.views import exception_handler
from rest_framework import status
from django.core.exceptions import (
    ValidationError as DjangoValidationError,
    ObjectDoesNotExist,
    PermissionDenied as DjangoPermissionDenied
)
from rest_framework.exceptions import (
    ValidationError as DRFValidationError,
    PermissionDenied as DRFPermissionDenied,
    NotAuthenticated,
    NotFound,
    )
import logging

logger = logging.getLogger(__name__)


def stock_exception_handler(exc, context):
    """
    Custom exception handler for stock management system
    """
    view = context.get('view')

    # Handle validation errors
    if isinstance(exc, (DjangoValidationError, DRFValidationError)):
        if hasattr(view, 'validation_error_response'):
            return view.validation_error_response(exc.detail)
        return _default_validation_error(exc)

    # Handle not found errors
    if isinstance(exc, (ObjectDoesNotExist, NotFound)):
        if hasattr(view, 'not_found_response'):
            return view.not_found_response()
        return _default_not_found_error()

    # Handle permission errors
    if isinstance(exc, (DjangoPermissionDenied, DRFPermissionDenied, NotAuthenticated)):
        if hasattr(view, 'permission_denied_response'):
            return view.permission_denied_response()
        return _default_permission_error()

    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)

    # Handle other DRF exceptions
    if response is not None:
        if hasattr(view, 'error_response'):
            error_code = getattr(exc, 'code', 'REQUEST_ERROR')
            return view.error_response(
                code=error_code,
                message=response.data.get('detail', 'Request error'),
                details=response.data,
                status_code=response.status_code
            )
        return _default_api_error(response)

    # Handle unhandled exceptions
    if hasattr(view, 'internal_error_response'):
        return view.internal_error_response(exc)

    # Fallback for unhandled exceptions
    logger.error(f"Unhandled exception: {str(exc)}")
    return Response({
        "success": False,
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "details": {"error": str(exc)}
        }
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _default_validation_error(exc):
    return Response({
        "success": False,
        "error": {
            "code": "VALIDATION_FAILED",
            "message": "Validation error",
            "details": exc.detail if hasattr(exc, 'detail') else str(exc)
        }
    }, status=status.HTTP_400_BAD_REQUEST)


def _default_not_found_error():
    return Response({
        "success": False,
        "error": {
            "code": "NOT_FOUND",
            "message": "Resource not found",
            "details": {}
        }
    }, status=status.HTTP_404_NOT_FOUND)


def _default_permission_error():
    return Response({
        "success": False,
        "error": {
            "code": "PERMISSION_DENIED",
            "message": "You don't have permission to perform this action",
            "details": {}
        }
    }, status=status.HTTP_403_FORBIDDEN)


def _default_api_error(response):
    return Response({
        "success": False,
        "error": {
            "code": "API_ERROR",
            "message": response.data.get('detail', 'API error'),
            "details": response.data
        }
    }, status=response.status_code)