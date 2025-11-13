from __future__ import annotations

import uuid

from django.db import models

from apps.authentication.models import User
from apps.stock.models import Product


class Notification(models.Model):
    NOTIFICATION_TYPE_CHOICES = [
        ("CRITICAL_STOCK", "Critical Stock"),
        ("EXPIRED", "Expired Product"),
        ("NEAR_EXPIRY", "Near Expiry"),
    ]
    NOTIFICATION_STATUS = [
        ("UNREAD", "Unread"),
        ("READ", "Read"),
        ("ARCHIVED", "Archived"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPE_CHOICES,
        default="CRITICAL_STOCK",
    )
    status = models.CharField(
        max_length=20,
        choices=NOTIFICATION_STATUS,
        default="UNREAD",
    )
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        db_table = "notifications"

    def __str__(self):
        return f"{self.notification_type} for {self.product.name}"

    def mark_as_read(self):
        self.status = "READ"
        self.save()

    def archive(self):
        self.status = "ARCHIVED"
        self.save()
