"""Notification use cases."""

from __future__ import annotations

import logging
from uuid import UUID

from domain.notifications.entities import Notification, NotificationStatus
from domain.notifications.repositories import NotificationRepository
from shared.exceptions.specific import NotFoundError

logger = logging.getLogger(__name__)


class GetNotificationUseCase:
    """Use case for getting a notification by ID."""

    def __init__(
        self,
        notification_repository: NotificationRepository,
        notification_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.notification_repository = notification_repository
        self.notification_id = notification_id
        self.user_id = user_id

    def execute(self) -> Notification:
        """Execute getting notification."""
        notification = self.notification_repository.get_by_id(self.notification_id)
        if not notification:
            raise NotFoundError(
                detail="Notification not found",
                code="NOTIFICATION_NOT_FOUND",
            )

        # Check if user owns this notification or if it's a broadcast notification
        if notification.user_id and notification.user_id != self.user_id:
            raise NotFoundError(
                detail="Notification not found",
                code="NOTIFICATION_NOT_FOUND",
            )

        return notification


class ListNotificationsUseCase:
    """Use case for listing notifications for a user."""

    def __init__(
        self,
        notification_repository: NotificationRepository,
        user_id: UUID,
        status: NotificationStatus | None = None,
        limit: int = 100,
    ) -> None:
        """Initialize use case."""
        self.notification_repository = notification_repository
        self.user_id = user_id
        self.status = status
        self.limit = limit

    def execute(self) -> list[Notification]:
        """Execute listing notifications."""
        return self.notification_repository.get_by_user_with_broadcast(
            user_id=self.user_id,
            status=self.status,
            limit=self.limit,
        )


class MarkNotificationAsReadUseCase:
    """Use case for marking a notification as read."""

    def __init__(
        self,
        notification_repository: NotificationRepository,
        notification_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.notification_repository = notification_repository
        self.notification_id = notification_id
        self.user_id = user_id

    def execute(self) -> Notification:
        """Execute marking notification as read."""
        notification = self.notification_repository.get_by_id(self.notification_id)
        if not notification:
            raise NotFoundError(
                detail="Notification not found",
                code="NOTIFICATION_NOT_FOUND",
            )

        # Check if user owns this notification or if it's a broadcast notification
        if notification.user_id and notification.user_id != self.user_id:
            raise NotFoundError(
                detail="Notification not found",
                code="NOTIFICATION_NOT_FOUND",
            )

        # Mark as read
        notification.mark_as_read()
        return self.notification_repository.update(notification)


class MarkAllNotificationsAsReadUseCase:
    """Use case for marking all notifications as read for a user."""

    def __init__(
        self,
        notification_repository: NotificationRepository,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.notification_repository = notification_repository
        self.user_id = user_id

    def execute(self) -> int:
        """Execute marking all notifications as read."""
        # Get count before marking
        count = self.notification_repository.get_unread_count(self.user_id)
        self.notification_repository.mark_all_as_read(self.user_id)
        return count


class ArchiveNotificationUseCase:
    """Use case for archiving a notification."""

    def __init__(
        self,
        notification_repository: NotificationRepository,
        notification_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.notification_repository = notification_repository
        self.notification_id = notification_id
        self.user_id = user_id

    def execute(self) -> Notification:
        """Execute archiving notification."""
        notification = self.notification_repository.get_by_id(self.notification_id)
        if not notification:
            raise NotFoundError(
                detail="Notification not found",
                code="NOTIFICATION_NOT_FOUND",
            )

        # Check if user owns this notification or if it's a broadcast notification
        if notification.user_id and notification.user_id != self.user_id:
            raise NotFoundError(
                detail="Notification not found",
                code="NOTIFICATION_NOT_FOUND",
            )

        # Archive
        notification.archive()
        return self.notification_repository.update(notification)


class GetUnreadCountUseCase:
    """Use case for getting unread notification count for a user."""

    def __init__(
        self,
        notification_repository: NotificationRepository,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.notification_repository = notification_repository
        self.user_id = user_id

    def execute(self) -> int:
        """Execute getting unread count."""
        return self.notification_repository.get_unread_count(self.user_id)
