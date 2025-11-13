"""OTP domain Django models."""

from __future__ import annotations

from django.db import models

from infrastructure.persistence.models.base_model import BaseModel


class OTP(BaseModel):
    """OTP model for one-time password verification.

    OTPs expire after 10 minutes (OTP_EXPIRY_MINUTES in OTPService).
    Each OTP has a maximum of 3 verification attempts.
    """

    user = models.ForeignKey(
        "persistence_models.retailpulseuser",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="otps",
    )
    email = models.EmailField(null=True, blank=True, db_index=True)
    phone_number = models.CharField(max_length=30, null=True, blank=True, db_index=True)
    otp_code = models.CharField(max_length=6)
    otp_type = models.CharField(max_length=10, choices=[("email", "Email"), ("sms", "SMS")])
    expires_at = models.DateTimeField(
        db_index=True, help_text="OTP expires 10 minutes after creation"
    )
    verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(
        default=3, help_text="Maximum 3 verification attempts allowed"
    )

    class Meta:
        db_table = "otps"
        verbose_name = "OTP"
        verbose_name_plural = "OTPs"
        indexes = [
            models.Index(fields=["email", "otp_type", "-created_at"]),
            models.Index(fields=["phone_number", "otp_type", "-created_at"]),
            models.Index(fields=["otp_code", "verified"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self) -> str:
        identifier = self.email or self.phone_number or "Unknown"
        return f"OTP for {identifier}"
