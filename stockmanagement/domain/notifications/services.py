"""Notification domain services."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from django.utils import timezone

from domain.business.repositories import BusinessMemberRepository, BusinessRepository
from domain.notifications.entities import (
    Notification,
    NotificationStatus,
    NotificationType,
)
from domain.notifications.repositories import NotificationRepository

logger = logging.getLogger(__name__)


class NotificationDomainService:
    """
    Domain service for managing product expiration notifications.

    This service handles the creation of notifications for business owners and managers
    regarding product expiration. It follows clean architecture principles by using
    only repositories and domain entities, never accessing infrastructure directly.

    Responsibilities:
    - Create notifications for products expiring soon (preventive)
    - Create notifications for expired products
    - Handle notification deduplication to avoid spam
    - Notify both business owners and managers
    """

    def __init__(
        self,
        notification_repository: NotificationRepository,
        business_repository: BusinessRepository,
        business_member_repository: BusinessMemberRepository,
    ) -> None:
        """
        Initialize notification domain service.

        Args:
            notification_repository: Repository for notification persistence
            business_repository: Repository for business operations
            business_member_repository: Repository for business member operations
        """
        self.notification_repository = notification_repository
        self.business_repository = business_repository
        self.business_member_repository = business_member_repository

    def notify_product_expiring(
        self,
        product_id: UUID,
        product_name: str,
        business_id: UUID,
        expiry_date: datetime | None,
        days_until_expiry: int,
    ) -> list[Notification]:
        """
        Create notifications for business owner and managers about a product expiring soon.

        Args:
            product_id: ID of the product that is expiring
            product_name: Name of the product
            business_id: ID of the business that owns the product
            expiry_date: Date when the product will expire
            days_until_expiry: Number of days until expiration

        Returns:
            List of created notifications
        """
        notifications: list[Notification] = []

        # Get business to find owner
        business = self.business_repository.get_by_id(business_id)
        if not business:
            logger.warning(f"Business {business_id} not found for expiring product notification")
            return notifications

        # Check for recent notifications to avoid duplicates
        if self._has_recent_notification(
            product_id=product_id,
            business_id=business_id,
            notification_type=NotificationType.NEAR_EXPIRY,
            hours_threshold=24,
        ):
            logger.info(
                f"Recent notification already exists for expiring product {product_id}, skipping"
            )
            return notifications

        # Create message
        expiry_date_str = expiry_date.strftime("%Y-%m-%d") if expiry_date else "N/A"
        message = (
            f"Product '{product_name}' will expire in {days_until_expiry} days "
            f"({expiry_date_str}). Please take action."
        )
        title = f"Product '{product_name}' expiring soon"

        # Notify owner
        if business.owner_id:
            notification = self._create_notification(
                user_id=business.owner_id,
                business_id=business_id,
                notification_type=NotificationType.NEAR_EXPIRY,
                title=title,
                message=message,
                related_entity_type="product",
                related_entity_id=product_id,
            )
            notifications.append(notification)

        # Notify managers
        managers = self.business_member_repository.get_managers(business_id)
        for manager in managers:
            notification = self._create_notification(
                user_id=manager.user_id,
                business_id=business_id,
                notification_type=NotificationType.NEAR_EXPIRY,
                title=title,
                message=message,
                related_entity_type="product",
                related_entity_id=product_id,
            )
            notifications.append(notification)

        logger.info(f"Created {len(notifications)} notifications for expiring product {product_id}")
        return notifications

    def notify_product_expired(
        self,
        product_id: UUID,
        product_name: str,
        business_id: UUID,
        expiry_date: datetime | None,
    ) -> list[Notification]:
        """
        Create notifications for business owner and managers about an expired product.

        Args:
            product_id: ID of the expired product
            product_name: Name of the product
            business_id: ID of the business that owns the product
            expiry_date: Date when the product expired

        Returns:
            List of created notifications
        """
        notifications: list[Notification] = []

        # Get business to find owner
        business = self.business_repository.get_by_id(business_id)
        if not business:
            logger.warning(f"Business {business_id} not found for expired product notification")
            return notifications

        # Check for recent notifications to avoid duplicates
        if self._has_recent_notification(
            product_id=product_id,
            business_id=business_id,
            notification_type=NotificationType.EXPIRED,
            hours_threshold=24,
        ):
            logger.info(
                f"Recent notification already exists for expired product {product_id}, skipping"
            )
            return notifications

        # Create message
        expiry_date_str = expiry_date.strftime("%Y-%m-%d") if expiry_date else "N/A"
        message = f"Product '{product_name}' has expired on {expiry_date_str}."
        title = f"Product '{product_name}' expired"

        # Notify owner
        if business.owner_id:
            notification = self._create_notification(
                user_id=business.owner_id,
                business_id=business_id,
                notification_type=NotificationType.EXPIRED,
                title=title,
                message=message,
                related_entity_type="product",
                related_entity_id=product_id,
            )
            notifications.append(notification)

        # Notify managers
        managers = self.business_member_repository.get_managers(business_id)
        for manager in managers:
            notification = self._create_notification(
                user_id=manager.user_id,
                business_id=business_id,
                notification_type=NotificationType.EXPIRED,
                title=title,
                message=message,
                related_entity_type="product",
                related_entity_id=product_id,
            )
            notifications.append(notification)

        logger.info(f"Created {len(notifications)} notifications for expired product {product_id}")
        return notifications

    def notify_low_stock(
        self,
        product_id: UUID,
        product_name: str,
        business_id: UUID,
        current_quantity: int,
        min_quantity: int,
    ) -> list[Notification]:
        """
        Create notifications for business owner and managers about low stock product.

        Args:
            product_id: ID of the product with low stock
            product_name: Name of the product
            business_id: ID of the business that owns the product
            current_quantity: Current stock quantity
            min_quantity: Minimum required quantity

        Returns:
            List of created notifications
        """
        notifications: list[Notification] = []

        # Get business to find owner
        business = self.business_repository.get_by_id(business_id)
        if not business:
            logger.warning(f"Business {business_id} not found for low stock notification")
            return notifications

        # Check for recent notifications to avoid duplicates
        if self._has_recent_notification(
            product_id=product_id,
            business_id=business_id,
            notification_type=NotificationType.CRITICAL_STOCK,
            hours_threshold=24,
        ):
            logger.info(
                f"Recent notification already exists for low stock product {product_id}, skipping"
            )
            return notifications

        # Create message
        message = (
            f"⚠️ Stock critique: Le produit '{product_name}' "
            f"est en rupture de stock. Quantité actuelle: {current_quantity}, "
            f"Minimum requis: {min_quantity}. "
            f"Veuillez réapprovisionner rapidement."
        )
        title = f"Rupture de stock: {product_name}"

        # Notify owner
        if business.owner_id:
            notification = self._create_notification(
                user_id=business.owner_id,
                business_id=business_id,
                notification_type=NotificationType.CRITICAL_STOCK,
                title=title,
                message=message,
                related_entity_type="product",
                related_entity_id=product_id,
            )
            notifications.append(notification)

        # Notify managers
        managers = self.business_member_repository.get_managers(business_id)
        for manager in managers:
            notification = self._create_notification(
                user_id=manager.user_id,
                business_id=business_id,
                notification_type=NotificationType.CRITICAL_STOCK,
                title=title,
                message=message,
                related_entity_type="product",
                related_entity_id=product_id,
            )
            notifications.append(notification)

        logger.info(
            f"Created {len(notifications)} notifications for low stock product {product_id}"
        )
        return notifications

    def _create_notification(
        self,
        user_id: UUID,
        business_id: UUID,
        notification_type: NotificationType,
        title: str,
        message: str,
        related_entity_type: str | None = None,
        related_entity_id: UUID | None = None,
    ) -> Notification:
        """
        Create a notification entity and save it.

        Args:
            user_id: ID of the user to notify
            business_id: ID of the business
            notification_type: Type of notification
            title: Notification title
            message: Notification message
            related_entity_type: Type of related entity (e.g., "product")
            related_entity_id: ID of related entity

        Returns:
            Created notification entity
        """
        notification = Notification(
            id=uuid4(),
            user_id=user_id,
            business_id=business_id,
            notification_type=notification_type,
            status=NotificationStatus.UNREAD,
            title=title,
            message=message,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            created_at=timezone.now(),
            read_at=None,
        )

        saved_notification = self.notification_repository.create(notification)

        try:
            from tasks.notification_tasks import send_notification_task

            send_notification_task.delay(notification_id=saved_notification.id)

            logger.debug(
                f"Queued notification sending task for notification {saved_notification.id} "
                f"(user {user_id})"
            )
        except Exception as e:
            logger.warning(
                f"Failed to queue notification sending task for {saved_notification.id}: {str(e)}"
            )

        return saved_notification

    def _has_recent_notification(
        self,
        product_id: UUID,
        business_id: UUID,
        notification_type: NotificationType,
        hours_threshold: int = 24,
    ) -> bool:
        """
        Check if a recent notification exists for the given product and type.

        Args:
            product_id: ID of the product
            business_id: ID of the business
            notification_type: Type of notification to check
            hours_threshold: Number of hours to look back for recent notifications

        Returns:
            True if a recent notification exists, False otherwise
        """
        business = self.business_repository.get_by_id(business_id)
        if not business or not business.owner_id:
            return False
        owner_notifications = self.notification_repository.get_by_user(
            user_id=business.owner_id,
            notification_type=notification_type,
            limit=100,
        )

        threshold_time = timezone.now() - timedelta(hours=hours_threshold)
        for notification in owner_notifications:
            if (
                notification.related_entity_id == product_id
                and notification.business_id == business_id
                and notification.created_at >= threshold_time
            ):
                return True

        return False
