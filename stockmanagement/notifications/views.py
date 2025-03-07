from __future__ import annotations

import logging

from drf_yasg.utils import swagger_auto_schema
from notifications.serializers import NotificationSerializer
from notifications.serializers import NotifSerializer
from notifications.service import NotificationService
from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

logger = logging.getLogger(__name__)


class NotificationsViewSet(viewsets.ViewSet):
    """
    ViewSet for handling notifications and related operations.
    """

    service = NotificationService()

    @swagger_auto_schema(
        operation_description='Retrieve all notifications.',
        responses={
            200: NotificationSerializer(many=True),
            500: 'Internal Server Error',
        },
    )
    @action(methods=['GET'], detail=False, url_path='notifications')
    def get_notifications(self, request):
        """
        Retrieve all notifications for stock levels and other alerts.
        """
        try:
            notifications = self.service.get_all_notifications()
            serializer = NotificationSerializer(notifications, many=True)
            return Response(serializer.data, status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in get_notifications: {str(e)}")
            return Response(
                {'error': str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        query_serializer=NotifSerializer,
        operation_description='Retrieve a notification.',
        responses={
            200: NotificationSerializer(),
            500: 'Internal Server Error',
        },
    )
    @action(methods=['GET'], detail=False, url_path='notification')
    def get_notification(self, request):
        """
        Retrieve a notifications for stock levels and other alerts.
        """
        serializer = NotifSerializer(data=request.query_params)
        if serializer.is_valid():
            notif_id = serializer.validated_data.get('notif_id')
            try:
                notif = self.service.get_notification(notif_id)
                serializer = NotificationSerializer(notif)
                return Response(serializer.data, status.HTTP_200_OK)
            except Exception as e:
                logger.error(f"Error in get_notifications: {str(e)}")
                return Response(
                    {'error': str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        logger.error('Invalid data:', str(serializer.errors))
        return Response(serializer.errors, status.HTTP_400_BAD_REQUEST)
