"""Delivery domain Django models."""

from __future__ import annotations

from django.db import models

from infrastructure.persistence.models.base_model import BaseModel
from infrastructure.persistence.models.business_models import Business
from infrastructure.persistence.models.customer_models import Customer
from infrastructure.persistence.models.sales_models import Order
from infrastructure.persistence.models.user_models import RetailPulseUser


class Delivery(BaseModel):
    """Delivery model."""

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("ASSIGNED", "Assigned"),
        ("IN_TRANSIT", "In Transit"),
        ("DELIVERED", "Delivered"),
        ("CANCELLED", "Cancelled"),
        ("FAILED", "Failed"),
    ]

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="deliveries"
    )
    order = models.OneToOneField(
        Order, on_delete=models.CASCADE, related_name="delivery"
    )
    delivery_person = models.ForeignKey(
        RetailPulseUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deliveries",
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="deliveries"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    shipping_address = models.TextField()
    estimated_delivery_time = models.DateTimeField(null=True, blank=True)
    actual_delivery_time = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "deliveries"
        verbose_name = "Delivery"
        verbose_name_plural = "Deliveries"
        indexes = [
            models.Index(fields=["business", "-updated_at"]),
            models.Index(fields=["delivery_person", "status"]),
            models.Index(fields=["status"]),
            models.Index(fields=["customer"]),
        ]

    def __str__(self) -> str:
        return f"Delivery {self.id} - {self.order.order_number}"

    def is_completed(self) -> bool:
        """Check if delivery is completed."""
        return self.status == "DELIVERED"

    def can_be_cancelled(self) -> bool:
        """Check if delivery can be cancelled."""
        return self.status in ("PENDING", "ASSIGNED")

