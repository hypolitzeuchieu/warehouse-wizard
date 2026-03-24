"""User domain Django models."""

from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from domain.users.entities import UserRole
from infrastructure.persistence.models.base_model import BaseModel


class RetailPulseUser(AbstractUser, BaseModel):
    """RetailPulse User model."""

    email = models.EmailField(unique=True, null=True, blank=True)
    username = models.CharField(
        max_length=150,
        null=True,
        blank=True,
        unique=False,
        help_text="Deprecated: Use name instead",
    )
    name = models.CharField(
        max_length=150, null=True, blank=True, help_text="User's display name (not unique)"
    )

    phone_number = models.CharField(
        max_length=30,
        unique=True,
        null=True,
        blank=True,
        help_text="Unique phone number for login (required if email is not provided)",
    )
    address = models.TextField(null=True, blank=True)
    avatar_url = models.URLField(max_length=500, null=True, blank=True)
    auth_method = models.CharField(
        max_length=20,
        choices=[
            ("email_password", "Email/Password"),
            ("google_oauth", "Google OAuth"),
            ("phone_otp", "Phone OTP"),
        ],
        default="email_password",
        help_text="Authentication method used to create/login to account",
    )
    role = models.CharField(
        max_length=30,
        choices=[(role.value, role.name) for role in UserRole],
        default=UserRole.CUSTOMER.value,
    )
    is_active = models.BooleanField(default=True, help_text="Account status")
    email_verified = models.BooleanField(default=False, help_text="Email/phone verification status")
    google_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        help_text="Google OAuth user ID",
    )
    last_login = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        db_table = "retailpulse_users"
        verbose_name = "RetailPulse User"
        verbose_name_plural = "RetailPulse Users"
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(email__isnull=False) | models.Q(phone_number__isnull=False),
                name="user_must_have_email_or_phone",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name or self.email} ({self.role})"

    def is_owner(self) -> bool:
        """Check if user is an owner."""
        return self.role == UserRole.OWNER.value

    def is_manager(self) -> bool:
        """Check if user is a manager."""
        return self.role == UserRole.MANAGER.value

    def can_manage_business(self) -> bool:
        """Check if user can manage business."""
        return self.role in (UserRole.OWNER.value, UserRole.MANAGER.value)

    def can_delete_business(self) -> bool:
        """Check if user can delete business (only owner)."""
        return self.role == UserRole.OWNER.value

    def can_manage_managers(self) -> bool:
        """Check if user can manage managers (only owner)."""
        return self.role == UserRole.OWNER.value


class Session(BaseModel):
    """User session model for tracking time spent on platform."""

    user = models.ForeignKey(RetailPulseUser, on_delete=models.CASCADE, related_name="sessions")
    device_id = models.CharField(max_length=255, null=True, blank=True)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "sessions"
        verbose_name = "Session"
        verbose_name_plural = "Sessions"
        ordering = ["-start_time"]
        # Override BaseModel ordering
        get_latest_by = "start_time"
        indexes = [
            models.Index(fields=["user", "-start_time"]),
            models.Index(fields=["device_id"]),
        ]

    def __str__(self) -> str:
        return f"Session {self.id} - {self.user.name or self.user.email}"

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


class RefreshToken(BaseModel):
    """Refresh token model."""

    user = models.ForeignKey(
        RetailPulseUser, on_delete=models.CASCADE, related_name="refresh_tokens"
    )
    token = models.TextField(unique=True)
    device_id = models.CharField(max_length=255, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    expires_at = models.DateTimeField()
    revoked = models.BooleanField(default=False)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "refresh_tokens"
        verbose_name = "Refresh Token"
        verbose_name_plural = "Refresh Tokens"
        indexes = [
            models.Index(fields=["user", "device_id"]),
            models.Index(fields=["token"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self) -> str:
        return f"RefreshToken {self.id} - {self.user.name or self.user.email}"

    def is_expired(self) -> bool:
        """Check if token is expired."""
        return timezone.now() > self.expires_at

    def is_valid(self) -> bool:
        """Check if token is valid (not expired and not revoked)."""
        return not self.revoked and not self.is_expired()


class Device(BaseModel):
    """User device model for multi-device management."""

    user = models.ForeignKey(RetailPulseUser, on_delete=models.CASCADE, related_name="devices")
    device_id = models.CharField(max_length=255, unique=True)
    device_name = models.CharField(max_length=255, null=True, blank=True)
    device_type = models.CharField(max_length=50, null=True, blank=True)  # mobile, tablet, desktop
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    last_used_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "devices"
        verbose_name = "Device"
        verbose_name_plural = "Devices"
        indexes = [
            models.Index(fields=["user", "device_id"]),
            models.Index(fields=["device_id"]),
        ]

    def __str__(self) -> str:
        return f"Device {self.device_id} - {self.user.name or self.user.email}"
