"""Alert use cases for products (expired, low stock)."""

from __future__ import annotations

import logging
from uuid import UUID

from django.utils import timezone

from domain.business.repositories import BusinessRepository
from domain.inventory.entities import Product
from domain.inventory.repositories import ProductRepository
from domain.inventory.services import InventoryDomainService
from domain.notifications.services import NotificationDomainService
from infrastructure.persistence.repositories import (
    BusinessMemberRepositoryImpl,
    BusinessRepositoryImpl,
    NotificationRepositoryImpl,
)

logger = logging.getLogger(__name__)


class NotifyProductExpiringUseCase:
    """
    Use case for notifying about products that will expire soon.

    This use case creates notifications for business owner and managers
    when a product is approaching its expiration date (preventive notification).
    No database update is performed, only notifications are created.
    """

    def __init__(
        self,
        notification_domain_service: NotificationDomainService,
        product: Product,
    ) -> None:
        """
        Initialize use case.

        Args:
            notification_domain_service: Service for creating notifications
            product: Product entity that is expiring soon
        """
        self.notification_domain_service = notification_domain_service
        self.product = product

    def execute(self) -> list[dict]:
        """
        Execute notification for expiring product.

        Returns:
            List of dictionaries with notification details
        """
        if not self.product.expiry_date:
            logger.warning(f"Product {self.product.id} has no expiry date, skipping notification")
            return []

        # Calculate days until expiry
        delta = self.product.expiry_date - timezone.now()
        days_until_expiry = delta.days

        if days_until_expiry < 0:
            logger.warning(
                f"Product {self.product.id} is already expired, "
                f"use NotifyProductExpiredUseCase instead"
            )
            return []

        # Create notifications
        notifications = self.notification_domain_service.notify_product_expiring(
            product_id=self.product.id,
            product_name=self.product.name,
            business_id=self.product.business_id,
            expiry_date=self.product.expiry_date,
            days_until_expiry=days_until_expiry,
        )

        # Convert to dict format for response
        return [
            {
                "product_id": str(notification.related_entity_id),
                "product_name": self.product.name,
                "notification_id": str(notification.id),
                "user_id": str(notification.user_id) if notification.user_id else None,
                "notification_type": notification.notification_type.value,
            }
            for notification in notifications
        ]


class NotifyProductExpiredUseCase:
    """
    Use case for notifying about expired products.

    This use case creates notifications for business owner and managers
    when a product has expired. The product's is_expired flag should already
    be updated in the database by InventoryDomainService.check_expired_products().
    """

    def __init__(
        self,
        notification_domain_service: NotificationDomainService,
        product: Product,
    ) -> None:
        """
        Initialize use case.

        Args:
            notification_domain_service: Service for creating notifications
            product: Product entity that has expired
        """
        self.notification_domain_service = notification_domain_service
        self.product = product

    def execute(self) -> list[dict]:
        """
        Execute notification for expired product.

        Returns:
            List of dictionaries with notification details
        """
        if not self.product.is_expired:
            logger.warning(
                f"Product {self.product.id} is not marked as expired, skipping notification"
            )
            return []

        # Create notifications
        notifications = self.notification_domain_service.notify_product_expired(
            product_id=self.product.id,
            product_name=self.product.name,
            business_id=self.product.business_id,
            expiry_date=self.product.expiry_date,
        )

        # Convert to dict format for response
        return [
            {
                "product_id": str(notification.related_entity_id),
                "product_name": self.product.name,
                "notification_id": str(notification.id),
                "user_id": str(notification.user_id) if notification.user_id else None,
                "notification_type": notification.notification_type.value,
            }
            for notification in notifications
        ]


class CheckAndNotifyExpiredProductsUseCase:
    """
    Use case for checking and notifying about expired and expiring products across all businesses.

    This use case:
    1. Gets products expiring soon (within X days) and notifies about them (preventive)
    2. Gets products that are expired, updates their status in DB, and notifies

    Note: This use case processes all businesses. For processing a specific business,
    use the individual notification use cases directly.
    """

    def __init__(
        self,
        inventory_domain_service: InventoryDomainService,
        notification_domain_service: NotificationDomainService,
        business_repository: BusinessRepository,
        product_repository: ProductRepository,
        days_ahead: int = 15,
    ) -> None:
        """
        Initialize use case.

        Args:
            inventory_domain_service: Service for inventory operations
            notification_domain_service: Service for creating notifications
            business_repository: Repository for business operations
            product_repository: Repository for product operations
            days_ahead: Number of days ahead to check for expiring products (default: 15)
        """
        self.inventory_domain_service = inventory_domain_service
        self.notification_domain_service = notification_domain_service
        self.business_repository = business_repository
        self.product_repository = product_repository
        self.days_ahead = days_ahead

    def execute(self) -> dict:
        """
        Execute checking and notifying about expired and expiring products across all businesses.

        This method:
        1. Gets all businesses that have products with expiry dates
        2. For each business:
           - Gets products expiring soon (within days_ahead) and creates preventive notifications
           - Gets expired products, updates their is_expired flag in DB, and creates notifications
        3. Continues processing even if individual products fail (resilient batch processing)

        Returns:
            Dictionary containing:
            - expiring_products_notified: Count of products expiring soon that were notified
            - expired_products_updated_and_notified: Count of expired products updated and notified
            - errors_count: Number of errors encountered
            - errors: List of error messages (limited to first 10)
            - timestamp: ISO timestamp of when the check was performed
        """
        expiring_notified = 0
        expired_updated_and_notified = 0
        errors: list[str] = []
        business_ids = self._get_business_ids_with_expiring_products()

        logger.info(f"Processing {len(business_ids)} businesses for expired products check")

        # Process each business
        for business_id in business_ids:
            try:
                # Get products expiring soon (preventive notification)
                expiring_products = self.inventory_domain_service.get_products_near_expiry(
                    business_id=business_id, days_ahead=self.days_ahead
                )

                for product in expiring_products:
                    try:
                        expiring_use_case = NotifyProductExpiringUseCase(
                            notification_domain_service=self.notification_domain_service,
                            product=product,
                        )
                        notifications = expiring_use_case.execute()
                        if notifications:
                            expiring_notified += 1
                            logger.debug(
                                f"Notified about expiring product {product.id} "
                                f"({len(notifications)} notifications created)"
                            )
                    except Exception as e:
                        error_msg = f"Error notifying about expiring product {product.id}: {str(e)}"
                        logger.error(error_msg, exc_info=True)
                        errors.append(error_msg)

                # Get and update expired products (updates DB + notifies)
                expired_products = self.inventory_domain_service.check_expired_products(
                    business_id=business_id
                )

                for product in expired_products:
                    try:
                        expired_use_case = NotifyProductExpiredUseCase(
                            notification_domain_service=self.notification_domain_service,
                            product=product,
                        )
                        notifications = expired_use_case.execute()
                        if notifications:
                            expired_updated_and_notified += 1
                            logger.debug(
                                f"Updated and notified about expired product {product.id} "
                                f"({len(notifications)} notifications created)"
                            )
                    except Exception as e:
                        error_msg = f"Error notifying about expired product {product.id}: {str(e)}"
                        logger.error(error_msg, exc_info=True)
                        errors.append(error_msg)

            except Exception as e:
                error_msg = f"Error processing business {business_id}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)

        result = {
            "expiring_products_notified": expiring_notified,
            "expired_products_updated_and_notified": expired_updated_and_notified,
            "errors_count": len(errors),
            "errors": errors[:10],
            "timestamp": timezone.now().isoformat(),
        }

        logger.info(f"Expired products check completed: {result}")
        return result

    def _get_business_ids_with_expiring_products(self) -> list[UUID]:
        """
        Get all unique business IDs that have products with expiry dates.


        Returns:
            List of unique business IDs that have products with expiry dates
        """
        all_products = self.product_repository.get_all_with_expiry_dates()
        business_ids = [product.business_id for product in all_products]
        return business_ids


class CheckExpiredProductsUseCase:
    """
    Legacy use case for checking expired products (kept for backward compatibility).

    This use case is deprecated. Use CheckAndNotifyExpiredProductsUseCase instead.
    """

    def __init__(
        self,
        inventory_domain_service: InventoryDomainService,
        business_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.inventory_domain_service = inventory_domain_service
        self.business_id = business_id

    def execute(self) -> list[dict]:
        """
        Execute checking expired products and create notifications.

        Note: This is a legacy use case. Consider using CheckAndNotifyExpiredProductsUseCase.
        """

        notification_domain_service = NotificationDomainService(
            notification_repository=NotificationRepositoryImpl(),
            business_repository=BusinessRepositoryImpl(),
            business_member_repository=BusinessMemberRepositoryImpl(),
        )

        # Get expired products (this updates the DB)
        expired_products = self.inventory_domain_service.check_expired_products(self.business_id)
        notifications_created = []

        for product in expired_products:
            try:
                use_case = NotifyProductExpiredUseCase(
                    notification_domain_service=notification_domain_service,
                    product=product,
                )
                notifications = use_case.execute()
                notifications_created.extend(notifications)
            except Exception as e:
                logger.error(
                    f"Error creating notification for expired product {product.id}: {str(e)}",
                    exc_info=True,
                )

        return notifications_created


class CheckLowStockProductsUseCase:
    """Use case for checking and alerting on low stock products."""

    def __init__(
        self,
        inventory_domain_service: InventoryDomainService,
        notification_domain_service: NotificationDomainService,
        business_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.inventory_domain_service = inventory_domain_service
        self.notification_domain_service = notification_domain_service
        self.business_id = business_id

    def execute(self) -> list[dict]:
        """Execute checking low stock products and create notifications."""
        low_stock_products = self.inventory_domain_service.get_low_stock_products(self.business_id)
        notifications_created = []

        for product in low_stock_products:
            try:
                notifications = self.notification_domain_service.notify_low_stock(
                    product_id=product.id,
                    product_name=product.name,
                    business_id=self.business_id,
                    current_quantity=product.quantity,
                    min_quantity=product.min_quantity,
                )

                notifications_created.extend(
                    [
                        {
                            "product_id": str(notification.related_entity_id),
                            "product_name": product.name,
                            "notification_id": str(notification.id),
                            "user_id": str(notification.user_id) if notification.user_id else None,
                            "notification_type": notification.notification_type.value,
                        }
                        for notification in notifications
                    ]
                )

                logger.info(f"Created low stock notification for {product.name}")

            except Exception as e:
                logger.error(
                    f"Error creating notification for low stock product {product.id}: {str(e)}",
                    exc_info=True,
                )

        return notifications_created
