"""Celery tasks for inventory management."""

from __future__ import annotations

import logging

from celery import shared_task

from application.use_cases.alert_use_cases import CheckAndNotifyExpiredProductsUseCase
from domain.inventory.services import InventoryDomainService
from domain.notifications.services import NotificationDomainService
from infrastructure.persistence.repositories import (
    BusinessMemberRepositoryImpl,
    BusinessRepositoryImpl,
    NotificationRepositoryImpl,
    ProductRepositoryImpl,
    StockMovementRepositoryImpl,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_expired_products(self) -> dict:
    """
    Check for expired products and products expiring within 15 days.

    This task:
    1. Notifies about products expiring soon (preventive notification)
    2. Updates expired products in DB and notifies about them

    Returns:
        Dictionary with task results including statistics
    """
    try:
        # Initialize services and repositories
        inventory_domain_service = InventoryDomainService(
            product_repository=ProductRepositoryImpl(),
            stock_movement_repository=StockMovementRepositoryImpl(),
        )

        notification_domain_service = NotificationDomainService(
            notification_repository=NotificationRepositoryImpl(),
            business_repository=BusinessRepositoryImpl(),
            business_member_repository=BusinessMemberRepositoryImpl(),
        )

        # Execute the use case
        use_case = CheckAndNotifyExpiredProductsUseCase(
            inventory_domain_service=inventory_domain_service,
            notification_domain_service=notification_domain_service,
            business_repository=BusinessRepositoryImpl(),
            product_repository=ProductRepositoryImpl(),
            days_ahead=15,
        )

        result = use_case.execute()
        logger.info(f"Expired products check task completed successfully: {result}")
        return result

    except Exception as exc:
        logger.error(
            f"Error in check_expired_products task: {exc}",
            exc_info=True,
        )
        raise self.retry(exc=exc) from exc
