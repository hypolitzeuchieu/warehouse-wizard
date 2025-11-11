"""Rate limiting decorators for API endpoints."""

from __future__ import annotations

from functools import wraps
from typing import Callable

from rest_framework.request import Request
from rest_framework.response import Response

from shared.rate_limiting.service import RateLimitingService
from shared.response.mixin import ResponseMixin


def rate_limit(
    requests_per_period: int,
    period_seconds: int,
    key_func: Callable[[Request], str] | None = None,
):
    """
    Decorator to rate limit an API endpoint.

    Args:
        requests_per_period: Maximum number of requests allowed
        period_seconds: Time period in seconds
        key_func: Function to generate rate limit key from request (default: IP address)

    Example:
        @rate_limit(requests_per_period=5, period_seconds=3600)  # 5 requests per hour
        def signup_view(request):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(request: Request, *args, **kwargs) -> Response:
            # Get rate limit key (default: IP address)
            if key_func:
                key = key_func(request)
            else:
                key = get_client_ip(request)

            # Check rate limit
            rate_limiter = RateLimitingService()
            is_allowed, remaining, reset_time = rate_limiter.check_rate_limit(
                key=key,
                requests_per_period=requests_per_period,
                period_seconds=period_seconds,
            )

            if not is_allowed:
                return ResponseMixin.error(
                    message="Rate limit exceeded. Please try again later.",
                    status_code=429,
                    code="RATE_LIMIT_EXCEEDED",
                    errors={
                        "retry_after": reset_time,
                        "limit": requests_per_period,
                        "period_seconds": period_seconds,
                    },
                )

            # Call the original function
            response = func(request, *args, **kwargs)

            # Add rate limit headers
            if hasattr(response, "headers"):
                response.headers["X-RateLimit-Limit"] = str(requests_per_period)
                response.headers["X-RateLimit-Remaining"] = str(remaining)
                response.headers["X-RateLimit-Reset"] = str(reset_time)

            return response

        return wrapper

    return decorator


def get_client_ip(request: Request) -> str:
    """Get client IP address from request."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR", "unknown")
    return ip


def rate_limit_by_user(
    requests_per_period: int,
    period_seconds: int,
):
    """
    Decorator to rate limit by user ID (for authenticated endpoints).

    Args:
        requests_per_period: Maximum number of requests allowed
        period_seconds: Time period in seconds
    """

    def key_func(request: Request) -> str:
        """Generate key from user ID."""
        if request.user and request.user.is_authenticated:
            return f"user:{request.user.id}"
        return get_client_ip(request)

    return rate_limit(
        requests_per_period=requests_per_period,
        period_seconds=period_seconds,
        key_func=key_func,
    )


