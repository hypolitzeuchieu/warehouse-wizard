"""Rate limiting service implementation."""

from __future__ import annotations

import time
from typing import Any

from django.core.cache import cache


class RateLimitingService:
    """Service for rate limiting API requests."""

    def __init__(self, cache_backend: Any = None):
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

        # Try to get existing data
        request_data = self.cache.get(cache_key)

        if request_data is None:
            reset_time = current_time + period_seconds
            initial_data = {"count": 1, "reset_time": reset_time}

            if self.cache.add(cache_key, initial_data, period_seconds):

                return True, requests_per_period - 1, reset_time
            else:
                request_data = self.cache.get(cache_key)
                if request_data is None:
                    if self.cache.add(cache_key, initial_data, period_seconds):
                        return True, requests_per_period - 1, reset_time
                    request_data = self.cache.get(cache_key)
                    if request_data is None:
                        self.cache.set(cache_key, initial_data, period_seconds)
                        return True, requests_per_period - 1, reset_time

        if current_time >= request_data["reset_time"]:
            reset_time = current_time + period_seconds
            new_data = {"count": 1, "reset_time": reset_time}
            self.cache.set(cache_key, new_data, period_seconds)
            return True, requests_per_period - 1, reset_time

        request_data["count"] += 1
        remaining = max(0, requests_per_period - request_data["count"])
        is_allowed = request_data["count"] <= requests_per_period

        ttl = max(1, request_data["reset_time"] - current_time)

        self.cache.set(cache_key, request_data, ttl)

        return is_allowed, remaining, request_data["reset_time"]

    def reset_rate_limit(self, key: str) -> None:
        """
        Reset rate limit for a key.

        This deletes the cache key, effectively resetting the rate limit counter.

        Args:
            key: Rate limit key to reset
        """
        cache_key = f"rate_limit:{key}"
        self.cache.delete(cache_key)

    def get_rate_limit_status(self, key: str) -> dict[str, Any] | None:
        """
        Get current rate limit status without incrementing.

        Useful for checking remaining requests without consuming one.

        Args:
            key: Rate limit key

        Returns:
            Dictionary with count, reset_time, or None if not set
        """
        cache_key = f"rate_limit:{key}"
        return self.cache.get(cache_key)
