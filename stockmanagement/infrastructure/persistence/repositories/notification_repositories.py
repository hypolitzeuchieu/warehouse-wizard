"""Notification repository implementations."""

from uuid import UUID

from django.db.models import Q
from django.utils import timezone

from domain.notifications.entities import (
    Notification,
    NotificationStatus,
    NotificationType,
)
from domain.notifications.repositories import NotificationRepository
from infrastructure.persistence.models.notification_models import (
    Notification as NotificationModel,
)


class NotificationRepositoryImpl(NotificationRepository):
    """Django implementation of NotificationRepository."""

    def get_by_id(self, notification_id: UUID) -> Notification | None:
        """Get notification by ID."""
        try:
            notification_model = NotificationModel.objects.select_related("user", "business").get(
                id=notification_id
            )
            return self._to_entity(notification_model)
        except NotificationModel.DoesNotExist:
            return None

    def get_by_user(
        self,
        user_id: UUID,
        status: NotificationStatus | None = None,
        notification_type: NotificationType | None = None,
        limit: int = 100,
    ) -> list[Notification]:
        """Get notifications for a user with optional filters."""
        query = NotificationModel.objects.filter(user_id=user_id).select_related("business")

        if status:
            query = query.filter(status=status.value)

        if notification_type:
            query = query.filter(notification_type=notification_type.value)

        notifications = query.order_by("-created_at")[:limit]
        return [self._to_entity(notification) for notification in notifications]

    def get_unread_count(self, user_id: UUID) -> int:
        """Get count of unread notifications for a user."""
        return NotificationModel.objects.filter(user_id=user_id, status="UNREAD").count()

    def create(self, notification: Notification) -> Notification:
        """Create a new notification."""
        notification_model = NotificationModel(
            id=notification.id,
            user_id=notification.user_id,
            business_id=notification.business_id,
            notification_type=notification.notification_type.value,
            status=notification.status.value,
            title=notification.title,
            message=notification.message,
            related_entity_type=notification.related_entity_type,
            related_entity_id=notification.related_entity_id,
            read_at=notification.read_at,
        )
        notification_model.save()
        return self._to_entity(notification_model)

    def update(self, notification: Notification) -> Notification:
        """Update an existing notification."""
        notification_model = NotificationModel.objects.get(id=notification.id)
        notification_model.status = notification.status.value
        notification_model.read_at = notification.read_at
        notification_model.save()
        return self._to_entity(notification_model)

    def mark_all_as_read(self, user_id: UUID) -> None:
        """Mark all notifications as read for a user."""

        NotificationModel.objects.filter(
            (Q(user_id=user_id) | Q(user__isnull=True)) & Q(status="UNREAD")
        ).update(status="READ", read_at=timezone.now())

    def get_by_user_with_broadcast(
        self,
        user_id: UUID,
        status: NotificationStatus | None = None,
        limit: int = 100,
    ) -> list[Notification]:
        """Get notifications for a user including broadcast notifications (user=None)."""
        from django.db.models import Q

        query = NotificationModel.objects.filter(
            Q(user_id=user_id) | Q(user__isnull=True)
        ).select_related("business", "user")

        if status:
            query = query.filter(status=status.value)

        notifications = query.order_by("-created_at")[:limit]
        return [self._to_entity(notification) for notification in notifications]

    def _to_entity(self, notification_model: NotificationModel) -> Notification:
        """Convert Django model to domain entity."""
        return Notification(
            id=notification_model.id,
            user_id=notification_model.user_id,
            business_id=notification_model.business_id,
            notification_type=NotificationType(notification_model.notification_type),
            status=NotificationStatus(notification_model.status),
            title=notification_model.title,
            message=notification_model.message,
            related_entity_type=notification_model.related_entity_type,
            related_entity_id=notification_model.related_entity_id,
            created_at=notification_model.created_at,
            read_at=notification_model.read_at,
        )
