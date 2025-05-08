from __future__ import annotations

from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """Custom Exception Handler"""
    response = exception_handler(exc, context)

    if isinstance(exc, DRFValidationError) and response is not None:
        errors = []
        detail = exc.detail

        if isinstance(detail, dict):
            for field, messages in detail.items():
                for message in messages:
                    errors.append({
                        'field': field,
                        'message': str(message),
                        'code': getattr(message, 'code', 'invalid')
                    })

        elif isinstance(detail, list):
            for message in detail:
                errors.append({
                    'field': 'non_field_error',
                    'message': str(message),
                    'code': getattr(message, 'code', 'invalid')
                })

        return Response({'errors': errors}, status=response.status_code)

    return response
