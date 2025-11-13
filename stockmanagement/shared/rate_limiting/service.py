"""Rate limiting service implementation."""

from __future__ import annotations

import time

from django.core.cache import cache


class RateLimitingService:
    """Service for rate limiting API requests."""

    def __init__(self, cache_backend=None):
        """
        Initialize rate limiting service.

        Args:
            cache_backend: Cache backend to use (default: Django cache)
        """
        self.cache = cache_backend or cache

    def check_rate_limit(
        self, key: str, requests_per_period: int, period_seconds: int
    ) -> tuple[bool, int, int]:
        """
        Check if request is within rate limit.

        Args:
            key: Unique key for rate limiting (e.g., IP address, user ID)
            requests_per_period: Maximum number of requests allowed
            period_seconds: Time period in seconds

        Returns:
            Tuple of (is_allowed, remaining_requests, reset_time)
        """
        cache_key = f"rate_limit:{key}"
        current_time = int(time.time())

        # Get current request count
        request_data = self.cache.get(cache_key)

        if request_data is None:
            # First request in period
            self.cache.set(
                cache_key,
                {"count": 1, "reset_time": current_time + period_seconds},
                period_seconds,
            )
            return True, requests_per_period - 1, current_time + period_seconds

        # Check if period has expired
        if current_time >= request_data["reset_time"]:
            # Reset period
            self.cache.set(
                cache_key,
                {"count": 1, "reset_time": current_time + period_seconds},
                period_seconds,
            )
            return True, requests_per_period - 1, current_time + period_seconds

        # Increment count
        request_data["count"] += 1
        remaining = max(0, requests_per_period - request_data["count"])
        is_allowed = request_data["count"] <= requests_per_period

        # Update cache
        ttl = request_data["reset_time"] - current_time
        self.cache.set(cache_key, request_data, ttl)

        return is_allowed, remaining, request_data["reset_time"]

    def reset_rate_limit(self, key: str) -> None:
        """
        Reset rate limit for a key.

        Args:
            key: Rate limit key to reset
        """
        cache_key = f"rate_limit:{key}"
        self.cache.delete(cache_key)
