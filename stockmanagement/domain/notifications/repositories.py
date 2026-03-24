"""Notifications domain repositories (interfaces)."""

from abc import ABC, abstractmethod
from uuid import UUID

from domain.notifications.entities import (
    Notification,
    NotificationStatus,
    NotificationType,
)


class NotificationRepository(ABC):
    """Notification repository interface."""

    @abstractmethod
    def get_by_id(self, notification_id: UUID) -> Notification | None:
        """Get notification by ID."""
        pass

    @abstractmethod
    def get_by_user(
        self,
        user_id: UUID,
        status: NotificationStatus | None = None,
        notification_type: NotificationType | None = None,
        limit: int = 100,
    ) -> list[Notification]:
        """Get notifications for a user with optional filters."""
        pass

    @abstractmethod
    def get_unread_count(self, user_id: UUID) -> int:
        """Get count of unread notifications for a user."""
        pass

    @abstractmethod
    def create(self, notification: Notification) -> Notification:
        """Create a new notification."""
        pass

    @abstractmethod
    def update(self, notification: Notification) -> Notification:
        """Update an existing notification."""
        pass

    @abstractmethod
    def mark_all_as_read(self, user_id: UUID) -> None:
        """Mark all notifications as read for a user."""
        pass

    @abstractmethod
    def get_by_user_with_broadcast(
        self,
        user_id: UUID,
        status: NotificationStatus | None = None,
        limit: int = 100,
    ) -> list[Notification]:
        """Get notifications for a user including broadcast notifications (user=None)."""
        pass
