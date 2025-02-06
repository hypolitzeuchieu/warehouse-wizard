from __future__ import annotations

import uuid

from authentication.models import User
from django.db import models
from stock.models import Product


class Notification(models.Model):
    NOTIFICATION_TYPE_CHOICES = [
        ('CRITICAL_STOCK', 'Critical Stock'),
        ('EXPIRED', 'Expired Product'),
        ('NEAR_EXPIRY', 'Near Expiry'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        null=True,
        blank=True,
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='notifications'
    )
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPE_CHOICES,
        default='CRITICAL_STOCK',
    )
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self):
        return f"{self.notification_type} for {self.product.name}"
