from __future__ import annotations

from datetime import datetime, timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from infrastructure.persistence.models.base_model import BaseModel


class PasswordResetToken(BaseModel):
    """Password reset token model."""

    user = models.ForeignKey(
        "persistence_models.retailpulseuser",
        on_delete=models.CASCADE,
        related_name="password_reset_tokens",
    )
    email = models.EmailField(null=True, blank=True, db_index=True)
    phone_number = models.CharField(max_length=30, null=True, blank=True, db_index=True)
    token = models.CharField(max_length=255, unique=True, db_index=True)
    code = models.CharField(max_length=6, null=True, blank=True)  # For SMS OTP
    reset_type = models.CharField(
        max_length=10, choices=[("email", "Email"), ("sms", "SMS")]
    )
    expires_at = models.DateTimeField(db_index=True)
    used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=3)

    class Meta:
        db_table = "password_reset_tokens"
        verbose_name = "Password Reset Token"
        verbose_name_plural = "Password Reset Tokens"
        indexes = [
            models.Index(fields=["token", "used"]),
            models.Index(fields=["code", "used"]),
            models.Index(fields=["email", "reset_type", "-updated_at"]),
            models.Index(fields=["phone_number", "reset_type", "-updated_at"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self) -> str:
        identifier = self.email or self.phone_number or "Unknown"
        return f"Password reset token for {identifier}"

    def is_valid(self) -> bool:
        """Check if token is valid (not expired and not used)."""
        return (
            not self.used
            and self.expires_at > timezone.now()
            and self.attempts < self.max_attempts
        )

