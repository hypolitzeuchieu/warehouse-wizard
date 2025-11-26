"""Notifications domain entities."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from django.utils import timezone


class NotificationType(str, Enum):
    """Notification type enumeration."""

    CRITICAL_STOCK = "CRITICAL_STOCK"
    EXPIRED = "EXPIRED"
    NEAR_EXPIRY = "NEAR_EXPIRY"
    ORDER = "ORDER"
    MEETING = "MEETING"
    SYSTEM = "SYSTEM"


class NotificationStatus(str, Enum):
    """Notification status enumeration."""

    UNREAD = "UNREAD"
    READ = "READ"
    ARCHIVED = "ARCHIVED"


@dataclass
class Notification:
    """Notification entity."""

    id: UUID
    user_id: UUID | None  # None for broadcast notifications
    business_id: UUID | None
    notification_type: NotificationType
    status: NotificationStatus
    title: str
    message: str
    related_entity_type: str | None  # product, order, meeting, etc.
    related_entity_id: UUID | None
    created_at: datetime
    read_at: datetime | None = None

    def mark_as_read(self) -> None:
        """Mark notification as read."""

        self.status = NotificationStatus.READ
        self.read_at = timezone.now()

    def archive(self) -> None:
        """Archive notification."""
        self.status = NotificationStatus.ARCHIVED
