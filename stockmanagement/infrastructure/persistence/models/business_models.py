"""Business domain Django models."""

from __future__ import annotations

from django.db import models

from infrastructure.persistence.models.base_model import BaseModel
from infrastructure.persistence.models.user_models import RetailPulseUser


class Business(BaseModel):
    """Business model."""

    name = models.CharField(max_length=255)
    unique_name = models.CharField(max_length=100, unique=True)  # Unique identifier for QR code
    owner = models.ForeignKey(
        RetailPulseUser,
        on_delete=models.CASCADE,
        related_name="owned_businesses",
        db_column="owner_id",
    )
    description = models.TextField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    phone_number = models.CharField(max_length=30, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    qr_code_url = models.URLField(max_length=500, null=True, blank=True)
    logo_url = models.URLField(max_length=500, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    settings = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "businesses"
        verbose_name = "Business"
        verbose_name_plural = "Businesses"
        indexes = [
            models.Index(fields=["owner"]),
            models.Index(fields=["unique_name"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.unique_name})"


class BusinessMember(BaseModel):
    """Business member model (employees, managers, etc.)."""

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        RetailPulseUser, on_delete=models.CASCADE, related_name="business_memberships"
    )
    role = models.CharField(max_length=50)  # manager, cashier, stock_keeper, delivery
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "business_members"
        verbose_name = "Business Member"
        verbose_name_plural = "Business Members"
        unique_together = [["business", "user"]]
        indexes = [
            models.Index(fields=["business", "is_active"]),
            models.Index(fields=["user"]),
            models.Index(fields=["role"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.name or self.user.email} - {self.business.name} ({self.role})"

    def is_manager(self) -> bool:
        """Check if member is a manager."""
        return self.role == "manager"

    def is_active_member(self) -> bool:
        """Check if member is currently active."""
        return self.is_active and self.left_at is None
