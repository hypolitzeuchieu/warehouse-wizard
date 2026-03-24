from __future__ import annotations

from django.http import JsonResponse


def mahplan_404_view(request, exception):
    """
    Custom view for 404 errors (Endpoint not found).

    This view is called when a URL pattern doesn't match any route.
    It raises a NotFoundError which will be handled by the custom exception
    handler to return a standardized error response.

    Args:
        request: The HTTP request object
        exception: The Django Http404 exception

    Returns:
        JsonResponse: Standardized 404 response
    """
    return JsonResponse(
        {
            "detail": "The requested endpoint was not found on this server.",
            "code": "RESOURCE_NOT_FOUND",
            "details": {
                "resource_type": "Endpoint",
                "path": request.path,
            },
        },
        status=404,
    )


def mahplan_500_view(request):
    """
    Custom view for 500 errors (Internal server error).

    This view is called when an unhandled exception occurs in the application.
    IMPORTANT: Do NOT raise another exception here. Django is already handling
    an unhandled exception; re-raising will mask the original error and can
    cause recursive 500 handling.

    Args:
        request: The HTTP request object

    Returns:
        JsonResponse: Standardized 500 response
    """
    return JsonResponse(
        {
            "detail": "Internal server error",
            "code": "INTERNAL_SERVER_ERROR",
            "details": {
                "path": request.path,
                "method": request.method,
            },
        },
        status=500,
    )
