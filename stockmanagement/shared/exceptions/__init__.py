"""Custom exceptions for RetailPulse API."""

from shared.exceptions.base import BaseAPIException
from shared.exceptions.specific import (
    BadRequestError,
    ForbiddenError,
    InternalServerError,
    NotFoundError,
    RateLimitExceededError,
    UnauthorizedError,
)

__all__ = [
    "BaseAPIException",
    "NotFoundError",
    "ForbiddenError",
    "BadRequestError",
    "UnauthorizedError",
    "InternalServerError",
    "RateLimitExceededError",
]
