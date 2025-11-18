"""Notification ViewSet for REST API (WebSocket removed)."""

from __future__ import annotations

from uuid import UUID

from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from infrastructure.persistence.services.notification_service import NotificationService
from shared.views.base_viewset import BaseViewSet


class NotificationViewSet(BaseViewSet):
    """ViewSet for notification management using REST API only."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="List notifications",
        operation_description="Get all notifications for the authenticated user.",
        responses={200: "List of notifications", 401: "Unauthorized"},
        tags=["Notifications"],
    )
    def list(self, request: Request) -> Response:
        """List all notifications for the authenticated user."""
        try:
            from shared.security.query_params_validator import QueryParamsValidator

            # Get and validate query parameters
            status_filter = QueryParamsValidator.validate_enum(
                request.query_params.get("status"),
                allowed_values=["UNREAD", "READ", "ARCHIVED"],
                param_name="status",
            )
            limit = QueryParamsValidator.validate_limit(
                request.query_params.get("limit"), default=100, max_limit=500
            )

            notifications = NotificationService.get_user_notifications(
                user_id=request.user.id, status=status_filter, limit=limit
            )

            # Check if error
            if isinstance(notifications, dict) and "error" in notifications:
                return self.error(
                    message=notifications["error"],
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    code="NOTIFICATION_ERROR",
                )

            # Format response
            data = [
                {
                    "id": str(notif.id),
                    "notification_type": notif.notification_type,
                    "title": notif.title,
                    "message": notif.message,
                    "related_entity_type": notif.related_entity_type,
                    "related_entity_id": (
                        str(notif.related_entity_id) if notif.related_entity_id else None
                    ),
                    "status": notif.status,
                    "read_at": notif.read_at.isoformat() if notif.read_at else None,
                    "created_at": notif.created_at.isoformat(),
                }
                for notif in notifications
            ]

            return self.success(
                message="Notifications retrieved successfully",
                data=data,
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get notification",
        operation_description="Get a specific notification by ID.",
        responses={200: "Notification details", 404: "Notification not found"},
        tags=["Notifications"],
    )
    def retrieve(self, request: Request, pk: UUID) -> Response:
        """Get notification by ID."""
        try:
            notification = NotificationService.get_notification(str(pk))

            # Check if error
            if isinstance(notification, dict) and "error" in notification:
                return self.error(
                    message=notification["error"],
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="NOTIFICATION_NOT_FOUND",
                )

            # Check if user owns this notification
            if notification.user and notification.user.id != request.user.id:
                return self.error(
                    message="You don't have access to this notification",
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="PERMISSION_DENIED",
                )

            data = {
                "id": str(notification.id),
                "notification_type": notification.notification_type,
                "title": notification.title,
                "message": notification.message,
                "related_entity_type": notification.related_entity_type,
                "related_entity_id": (
                    str(notification.related_entity_id) if notification.related_entity_id else None
                ),
                "status": notification.status,
                "read_at": notification.read_at.isoformat() if notification.read_at else None,
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
        responses={200: "Notification marked as read", 404: "Notification not found"},
        tags=["Notifications"],
    )
    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request: Request, pk: UUID) -> Response:
        """Mark a notification as read."""
        try:
            result = NotificationService.mark_as_read(str(pk))

            # Check if error
            if isinstance(result, dict) and "error" in result:
                return self.error(
                    message=result["error"],
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="NOTIFICATION_NOT_FOUND",
                )

            # Check if user owns this notification
            if result.user and result.user.id != request.user.id:
                return self.error(
                    message="You don't have access to this notification",
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="PERMISSION_DENIED",
                )

            return self.success(
                message="Notification marked as read",
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Mark all notifications as read",
        operation_description="Mark all unread notifications for the authenticated user as read.",
        responses={200: "All notifications marked as read"},
        tags=["Notifications"],
    )
    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request: Request) -> Response:
        """Mark all notifications as read."""
        try:
            count = NotificationService.mark_all_as_read(request.user.id)

            # Check if error
            if isinstance(count, dict) and "error" in count:
                return self.error(
                    message=count["error"],
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    code="NOTIFICATION_ERROR",
                )

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
        responses={200: "Notification archived", 404: "Notification not found"},
        tags=["Notifications"],
    )
    @action(detail=True, methods=["post"], url_path="archive")
    def archive_notification(self, request: Request, pk: UUID) -> Response:
        """Archive a notification."""
        try:
            notification = NotificationService.get_notification(str(pk))

            # Check if error
            if isinstance(notification, dict) and "error" in notification:
                return self.error(
                    message=notification["error"],
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="NOTIFICATION_NOT_FOUND",
                )

            # Check if user owns this notification
            if notification.user and notification.user.id != request.user.id:
                return self.error(
                    message="You don't have access to this notification",
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="PERMISSION_DENIED",
                )

            result = NotificationService.archive_notification(str(pk))

            # Check if error
            if isinstance(result, dict) and "error" in result:
                return self.error(
                    message=result["error"],
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="NOTIFICATION_NOT_FOUND",
                )

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
            notifications = NotificationService.get_user_notifications(
                user_id=request.user.id, status="UNREAD"
            )

            # Check if error
            if isinstance(notifications, dict) and "error" in notifications:
                return self.error(
                    message=notifications["error"],
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    code="NOTIFICATION_ERROR",
                )

            count = len(notifications) if hasattr(notifications, "__len__") else 0

            return self.success(
                message="Unread count retrieved successfully",
                data={"count": count},
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)
