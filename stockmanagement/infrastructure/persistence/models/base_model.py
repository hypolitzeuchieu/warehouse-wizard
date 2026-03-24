"""Base model for RetailPulse with common fields and custom manager."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from django.db import models
from django.utils import timezone


class BaseModelManager(models.Manager):
    """Custom manager for BaseModel with useful queryset methods."""

    def get_queryset(self):
        """Return queryset with default ordering by updated_at."""
        return super().get_queryset().order_by("-updated_at")

    def active(self):
        """Return only active objects (if is_active field exists)."""
        if hasattr(self.model, "is_active"):
            return self.get_queryset().filter(is_active=True)
        return self.get_queryset()

    def recent(self, days: int = 30):
        """Return objects created in the last N days."""

        cutoff_date = timezone.now() - timedelta(days=days)
        return self.get_queryset().filter(created_at__gte=cutoff_date)


class BaseModel(models.Model):
    """Base model for all RetailPulse models.

    Provides:
    - UUID primary key
    - created_at timestamp
    - updated_at timestamp
    - Custom manager with useful methods

    Note: Models that inherit from AbstractUser should use multiple inheritance:
    class RetailPulseUser(AbstractUser, BaseModel):
        ...
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    objects = BaseModelManager()

    class Meta:
        abstract = True
        ordering = ["-updated_at"]
        get_latest_by = "updated_at"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Override save to ensure updated_at is set."""
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        """Default string representation."""
        return f"{self.__class__.__name__} {self.id}"
