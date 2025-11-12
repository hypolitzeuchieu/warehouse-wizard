from __future__ import annotations

import logging

from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.notifications.serializers import (
    NotificationSerializer,
    NotifSerializer,
    UserNotificationSerializer,
    WeekSerializer,
)
from apps.notifications.service import NotificationService
from apps.stock.serializers import PaginationQuerySerializer
from apps.stock.views import CustomPagination

logger = logging.getLogger(__name__)


class NotificationsViewSet(viewsets.ViewSet):
    """
    ViewSet for handling notifications and related operations.
    """

    service = NotificationService()
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Retrieve all notifications.",
        query_serializer=PaginationQuerySerializer,
        responses={
            200: NotificationSerializer(many=True),
            500: "Internal Server Error",
        },
    )
    @action(methods=["GET"], detail=False, url_path="notifications")
    def get_notifications(self, request):
        """
        Retrieve all notifications for stock levels and other alerts.
        """
        try:
            query_serializer = PaginationQuerySerializer(data=request.query_params)
            query_serializer.is_valid(raise_exception=True)

            paginator = CustomPagination()
            paginator.page_size = query_serializer.validated_data["page_size"]

            page = paginator.paginate_queryset(
                self.service.get_all_notifications(), request, view=self
            )
            serializer = NotificationSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        except Exception as e:
            logger.error(f"Error in get_notifications: {str(e)}")
            return Response({"error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(
        query_serializer=NotifSerializer,
        operation_description="Retrieve a notification.",
        responses={
            200: NotificationSerializer(),
            500: "Internal Server Error",
        },
    )
    @action(methods=["GET"], detail=False, url_path="notification")
    def get_notification(self, request):
        """
        Retrieve a notifications for stock levels and other alerts.
        """
        serializer = NotifSerializer(data=request.query_params)
        if serializer.is_valid():
            notif_id = serializer.validated_data.get("notif_id")
            try:
                notif = self.service.get_notification(notif_id)
                serializer = NotificationSerializer(notif)
                return Response(serializer.data, status.HTTP_200_OK)
            except Exception as e:
                logger.error(f"Error in get_notifications: {str(e)}")
                return Response({"error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR)
        logger.error("Invalid data:", str(serializer.errors))
        return Response({"error": serializer.errors}, status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Retrieve notifications for the current user.",
        query_serializer=UserNotificationSerializer,
        responses={
            200: NotificationSerializer(many=True),
            500: "Internal Server Error",
        },
    )
    @action(methods=["GET"], detail=False, url_path="my-notifications")
    def get_my_notifications(self, request):
        """
        Retrieve notifications for the current user.
        """
        try:
            query_serializer = UserNotificationSerializer(data=request.query_params)
            query_serializer.is_valid(raise_exception=True)

            paginator = CustomPagination()
            paginator.page_size = query_serializer.validated_data["page_size"]

            status_filter = query_serializer.validated_data.get("status", None)

            page = paginator.paginate_queryset(
                self.service.get_user_notifications(request.user.id, status=status_filter),
                request,
                view=self,
            )
            serializer = NotificationSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        except Exception as e:
            logger.error(f"Error in get_my_notifications: {str(e)}")
            return Response({"error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(
        operation_description="Mark a notification as read.",
        request_body=NotifSerializer,
        responses={
            200: NotificationSerializer(),
            404: "Notification not found",
            500: "Internal Server Error",
        },
    )
    @action(methods=["POST"], detail=False, url_path="mark-read")
    def mark_notification_read(self, request):
        """
        Mark a specific notification as read.
        """
        serializer = NotifSerializer(data=request.data)
        if serializer.is_valid():
            notif_id = serializer.validated_data.get("notif_id")
            try:
                result = self.service.mark_as_read(notif_id)
                if isinstance(result, dict) and "error" in result:
                    if "not found" in result["error"]:
                        return Response(
                            {"error": result["error"]}, status=status.HTTP_404_NOT_FOUND
                        )
                    return Response(
                        {"error": result["error"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

                serializer = NotificationSerializer(result)
                return Response(serializer.data, status.HTTP_200_OK)
            except Exception as e:
                logger.error(f"Error in mark_notification_read: {str(e)}")
                return Response({"error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR)
        logger.error("Invalid data:", str(serializer.errors))
        return Response({"error": serializer.errors}, status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Mark all notifications as read for current user.",
        responses={
            200: "All notifications successfully marked as read",
            500: "Internal Server Error",
        },
    )
    @action(methods=["POST"], detail=False, url_path="mark-all-read")
    def mark_all_read(self, request):
        """
        Mark all unread notifications for the current user as read.
        """
        try:
            result = self.service.mark_all_as_read(request.user.id)
            if isinstance(result, dict) and "error" in result:
                return Response(
                    {"error": result["error"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            return Response({"marked_read": result}, status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in mark_all_read: {str(e)}")
            return Response({"error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(
        operation_description="Archive a notification.",
        request_body=NotifSerializer,
        responses={
            200: NotificationSerializer(),
            404: "Notification not found",
            500: "Internal Server Error",
        },
    )
    @action(methods=["POST"], detail=False, url_path="archive")
    def archive_notification(self, request):
        """
        Archive a specific notification.
        """
        serializer = NotifSerializer(data=request.data)
        if serializer.is_valid():
            notif_id = serializer.validated_data.get("notif_id")
            try:
                result = self.service.archive_notification(notif_id)
                if isinstance(result, dict) and "error" in result:
                    if "not found" in result["error"]:
                        return Response(
                            {"error": result["error"]}, status=status.HTTP_404_NOT_FOUND
                        )
                    return Response(
                        {"error": result["error"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

                serializer = NotificationSerializer(result)
                return Response(serializer.data, status.HTTP_200_OK)
            except Exception as e:
                logger.error(f"Error in archive_notification: {str(e)}")
                return Response({"error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR)
        logger.error("Invalid data:", str(serializer.errors))
        return Response({"error": serializer.errors}, status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Archive old notifications.",
        query_serializer=WeekSerializer,
        responses={
            200: "Old notifications successfully archived",
            500: "Internal Server Error",
        },
    )
    @action(methods=["POST"], detail=False, url_path="archive-old")
    def archive_old_notifications(self, request):
        """
        Archive notifications older than X weeks.
        """
        week_serializer = WeekSerializer(data=request.query_params)
        if week_serializer.is_valid():
            try:
                months = week_serializer.validated_data.get("months")
                result = self.service.bulk_archive_old_notifications(months=months)
                if isinstance(result, dict) and "error" in result:
                    return Response(
                        {"error": result["error"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

                return Response({"archived": result}, status.HTTP_200_OK)
            except Exception as e:
                logger.error(f"Error in archive_old_notifications: {str(e)}")
                return Response({"error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR)
        logger.error("Invalid data:", week_serializer.errors)
        return Response({"error": week_serializer.errors}, status.HTTP_400_BAD_REQUEST)
