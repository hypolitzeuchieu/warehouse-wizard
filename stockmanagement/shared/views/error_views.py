from __future__ import annotations

from shared.exceptions.specific import InternalServerError, NotFoundError


def mahplan_404_view(request, exception):
    """
    Custom view for 404 errors (Endpoint not found).

    This view is called when a URL pattern doesn't match any route.
    It raises a NotFoundError which will be handled by the custom exception
    handler to return a standardized error response.

    Args:
        request: The HTTP request object
        exception: The Django Http404 exception

    Raises:
        NotFoundError: Custom exception with standardized format
    """
    raise NotFoundError(
        detail="The requested endpoint was not found on this server.",
        code="RESOURCE_NOT_FOUND",
        details={
            "resource_type": "Endpoint",
            "path": request.path,
        },
    )


def mahplan_500_view(request):
    """
    Custom view for 500 errors (Internal server error).

    This view is called when an unhandled exception occurs in the application.
    It raises an InternalServerError which will be handled by the custom exception
    handler to return a standardized error response.

    Args:
        request: The HTTP request object

    Raises:
        InternalServerError: Custom exception with standardized format
    """
    raise InternalServerError(
        detail="An unexpected error occurred on the server. Please try again later or contact support if the problem persists.",
        code="INTERNAL_SERVER_ERROR",
        details={
            "originalError": "Internal server error",
            "path": request.path,
            "method": request.method,
        },
    )
