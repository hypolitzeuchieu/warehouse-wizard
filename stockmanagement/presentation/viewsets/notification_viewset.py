"""Notification ViewSet for REST API (WebSocket removed)."""

from __future__ import annotations

from uuid import UUID

from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from application.dto.notification_list_filter_dto import NotificationListFilterDTO
from application.use_cases.notification_use_cases import (
    ArchiveNotificationUseCase,
    GetNotificationUseCase,
    GetUnreadCountUseCase,
    ListNotificationsUseCase,
    MarkAllNotificationsAsReadUseCase,
    MarkNotificationAsReadUseCase,
)
from domain.notifications.entities import NotificationStatus
from infrastructure.persistence.repositories import NotificationRepositoryImpl
from presentation.serializers.notification_serializers import (
    NotificationResponseSerializer,
)
from shared.security.query_params_validator import QueryParamsValidator
from shared.views.base_viewset import BaseViewSet


class NotificationViewSet(BaseViewSet):
    """ViewSet for notification management using REST API only."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="List notifications",
        operation_description="Get all notifications for the authenticated user.",
        responses={200: NotificationResponseSerializer(many=True), 401: "Unauthorized"},
        tags=["Notifications"],
    )
    def list(self, request: Request) -> Response:
        """List all notifications for the authenticated user."""
        try:
            filter_payload = self.parse_list_filters(
                request,
                search_fields=["title", "message"],
                order_fields=["created_at", "read_at"],
                filter_definitions={
                    "status": {
                        "type": "enum",
                        "choices": ["UNREAD", "READ", "ARCHIVED"],
                    },
                },
            )
            filter_dto = NotificationListFilterDTO.from_payload(filter_payload)

            status_filter = (
                NotificationStatus(filter_dto.status) if filter_dto.status else None
            )

            use_case = ListNotificationsUseCase(
                notification_repository=NotificationRepositoryImpl(),
                user_id=request.user.id,
                status=status_filter,
                limit=QueryParamsValidator.MAX_PAGE_SIZE,
            )
            notifications = use_case.execute()

            notifications = self.apply_filtering_to_items(
                notifications,
                filter_payload,
                name_fields=["title", "message"],
            )

            return self.paginated_response(
                request=request,
                queryset=notifications,
                serializer_class=NotificationResponseSerializer,
                message="Notifications retrieved successfully",
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get notification",
        operation_description="Get a specific notification by ID.",
        responses={200: NotificationResponseSerializer, 404: "Notification not found"},
        tags=["Notifications"],
    )
    def retrieve(self, request: Request, pk: UUID) -> Response:
        """Get notification by ID."""
        try:
            use_case = GetNotificationUseCase(
                notification_repository=NotificationRepositoryImpl(),
                notification_id=pk,
                user_id=request.user.id,
            )
            notification = use_case.execute()

            data = {
                "id": str(notification.id),
                "notification_type": notification.notification_type.value,
                "title": notification.title,
                "message": notification.message,
                "related_entity_type": notification.related_entity_type,
                "related_entity_id": (
                    str(notification.related_entity_id)
                    if notification.related_entity_id
                    else None
                ),
                "status": notification.status.value,
                "read_at": (
                    notification.read_at.isoformat() if notification.read_at else None
                ),
                "created_at": notification.created_at.isoformat(),
            }

            return self.success(
                message="Notification retrieved successfully",
                data=data,
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Mark notification as read",
        operation_description="Mark a notification as read.",
        responses={200: NotificationResponseSerializer, 404: "Notification not found"},
        tags=["Notifications"],
    )
    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request: Request, pk: UUID) -> Response:
        """Mark a notification as read."""
        try:
            use_case = MarkNotificationAsReadUseCase(
                notification_repository=NotificationRepositoryImpl(),
                notification_id=pk,
                user_id=request.user.id,
            )
            use_case.execute()

            return self.success(
                message="Notification marked as read",
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Mark all notifications as read",
        operation_description="Mark all unread notifications for the authenticated user as read.",
        responses={200: NotificationResponseSerializer, 404: "Notification not found"},
    )
    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request: Request) -> Response:
        """Mark all notifications as read."""
        try:
            use_case = MarkAllNotificationsAsReadUseCase(
                notification_repository=NotificationRepositoryImpl(),
                user_id=request.user.id,
            )
            count = use_case.execute()

            return self.success(
                message=f"{count} notification(s) marked as read",
                data={"count": count},
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Archive notification",
        operation_description="Archive a notification.",
        responses={200: NotificationResponseSerializer, 404: "Notification not found"},
        tags=["Notifications"],
    )
    @action(detail=True, methods=["post"], url_path="archive")
    def archive_notification(self, request: Request, pk: UUID) -> Response:
        """Archive a notification."""
        try:
            use_case = ArchiveNotificationUseCase(
                notification_repository=NotificationRepositoryImpl(),
                notification_id=pk,
                user_id=request.user.id,
            )
            use_case.execute()

            return self.success(
                message="Notification archived successfully",
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get unread count",
        operation_description="Get count of unread notifications for the authenticated user.",
        responses={200: "Unread count"},
        tags=["Notifications"],
    )
    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request: Request) -> Response:
        """Get count of unread notifications."""
        try:
            use_case = GetUnreadCountUseCase(
                notification_repository=NotificationRepositoryImpl(),
                user_id=request.user.id,
            )
            count = use_case.execute()

            return self.success(
                message="Unread count retrieved successfully",
                data={"count": count},
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)
