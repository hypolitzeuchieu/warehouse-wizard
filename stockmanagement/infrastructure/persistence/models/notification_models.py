"""Notifications domain Django models."""

from __future__ import annotations

from django.db import models

from infrastructure.persistence.models.base_model import BaseModel
from infrastructure.persistence.models.business_models import Business
from infrastructure.persistence.models.user_models import RetailPulseUser


class Notification(BaseModel):
    """Notification model."""

    NOTIFICATION_TYPES = [
        ("CRITICAL_STOCK", "Critical Stock"),
        ("EXPIRED", "Expired Product"),
        ("NEAR_EXPIRY", "Near Expiry"),
        ("ORDER", "Order"),
        ("MEETING", "Meeting"),
        ("SYSTEM", "System"),
    ]

    STATUS_CHOICES = [
        ("UNREAD", "Unread"),
        ("READ", "Read"),
        ("ARCHIVED", "Archived"),
    ]

    user = models.ForeignKey(
        RetailPulseUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    notification_type = models.CharField(
        max_length=20, choices=NOTIFICATION_TYPES, default="SYSTEM"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="UNREAD")
    title = models.CharField(max_length=255)
    message = models.TextField()
    related_entity_type = models.CharField(
        max_length=50, null=True, blank=True
    )  # product, order, meeting, etc.
    related_entity_id = models.UUIDField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notifications"
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        indexes = [
            models.Index(fields=["user", "-updated_at"]),
            models.Index(fields=["user", "status"]),
            models.Index(fields=["business", "-updated_at"]),
            models.Index(fields=["notification_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.notification_type} - {self.title}"

    def mark_as_read(self) -> None:
        """Mark notification as read."""
        from datetime import datetime

        self.status = "READ"
        self.read_at = datetime.utcnow()
        self.save(update_fields=["status", "read_at"])

    def archive(self) -> None:
        """Archive notification."""
        self.status = "ARCHIVED"
        self.save(update_fields=["status"])

