"""User domain entities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from django.utils import timezone


class UserRole(str, Enum):
    """User role enumeration."""

    OWNER = "owner"
    MANAGER = "manager"
    CASHIER = "cashier"
    STOCK_KEEPER = "stock_keeper"
    DELIVERY = "delivery"
    CUSTOMER = "customer"
    WHOLESALER = "wholesaler"
    PARTNER = "partner"


class AuthMethod(str, Enum):
    """Authentication method enumeration."""

    EMAIL_PASSWORD = "email_password"
    GOOGLE_OAUTH = "google_oauth"
    PHONE_OTP = "phone_otp"


@dataclass
class User:
    """User entity."""

    id: UUID
    email: str | None
    name: str
    phone_number: str | None
    role: UserRole
    is_active: bool
    email_verified: bool
    is_staff: bool
    is_superuser: bool
    last_login: datetime | None
    address: str | None
    avatar_url: str | None
    created_at: datetime
    updated_at: datetime
    auth_method: AuthMethod = AuthMethod.EMAIL_PASSWORD
    google_id: str | None = None

    def can_manage_managers(self) -> bool:
        """Check if user can manage managers."""
        return self.role == UserRole.OWNER


@dataclass
class Session:
    """User session entity for tracking time spent on platform."""

    id: UUID
    user_id: UUID
    device_id: str | None
    start_time: datetime
    end_time: datetime | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime
    updated_at: datetime

    @property
    def duration_seconds(self) -> float | None:
        """Calculate session duration in seconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    @property
    def is_active(self) -> bool:
        """Check if session is currently active."""
        return self.end_time is None


@dataclass
class RefreshToken:
    """Refresh token entity."""

    id: UUID
    user_id: UUID
    token: str
    device_id: str | None
    ip_address: str | None
    expires_at: datetime
    revoked: bool
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime

    def is_valid(self) -> bool:
        """Check if refresh token is valid."""

        return not self.revoked and self.expires_at > timezone.now()


@dataclass
class Device:
    """Device entity for tracking user devices."""

    id: UUID
    user_id: UUID
    device_id: str
    device_name: str | None
    device_type: str | None
    ip_address: str | None
    user_agent: str | None
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass
class OTP:
    """OTP entity for one-time password verification."""

    id: UUID
    user_id: UUID | None
    email: str | None
    phone_number: str | None
    otp_code: str
    otp_type: str
    expires_at: datetime
    verified: bool
    verified_at: datetime | None
    attempts: int
    max_attempts: int
    created_at: datetime
    updated_at: datetime

    def is_valid(self) -> bool:
        """Check if OTP is valid (not expired and not verified)."""

        return (
            not self.verified
            and self.expires_at > timezone.now()
            and self.attempts < self.max_attempts
        )

    def verify(self, code: str) -> bool:
        """Verify OTP code."""

        if not self.is_valid():
            return False

        if self.otp_code != code:
            self.attempts += 1
            return False

        self.verified = True
        self.verified_at = timezone.now()
        return True
