"""Notifications domain entities."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID


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
    user_id: Optional[UUID]  # None for broadcast notifications
    business_id: Optional[UUID]
    notification_type: NotificationType
    status: NotificationStatus
    title: str
    message: str
    related_entity_type: Optional[str]  # product, order, meeting, etc.
    related_entity_id: Optional[UUID]
    created_at: datetime
    read_at: Optional[datetime] = None

    def mark_as_read(self) -> None:
        """Mark notification as read."""
        self.status = NotificationStatus.READ
        self.read_at = datetime.utcnow()

    def archive(self) -> None:
        """Archive notification."""
        self.status = NotificationStatus.ARCHIVED

