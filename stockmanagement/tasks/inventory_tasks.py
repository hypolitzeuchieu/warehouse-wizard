"""Celery tasks for inventory management."""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_expired_products(self) -> dict:
    """
    Check for expired products and products expiring within 15 days.
    Send notifications to business owners and update expired status.

    Returns:
        Dictionary with task results
    """
    from application.use_cases.inventory_use_cases import NotifyExpiringProductsUseCase
    from domain.business.services import BusinessDomainService
    from infrastructure.persistence.models.inventory_models import ProductModel
    from infrastructure.persistence.repositories import (
        BusinessMemberRepositoryImpl,
        BusinessRepositoryImpl,
        ProductRepositoryImpl,
    )

    try:
        now = timezone.now()
        expiry_threshold = now + timedelta(days=15)

        # Get products expiring within 15 days
        expiring_products = ProductModel.objects.filter(
            expiry_date__lte=expiry_threshold,
            expiry_date__gt=now,
            is_expired=False,
        ).select_related("business")

        # Get expired products
        expired_products = ProductModel.objects.filter(
            expiry_date__lte=now,
            is_expired=False,
        ).select_related("business")

        expiring_count = 0
        expired_count = 0

        # Process expiring products (15 days before)
        for product_model in expiring_products:
            try:
                business_domain_service = BusinessDomainService(
                    business_repository=BusinessRepositoryImpl(),
                    business_member_repository=BusinessMemberRepositoryImpl(),
                )

                use_case = NotifyExpiringProductsUseCase(
                    product_repository=ProductRepositoryImpl(),
                    business_domain_service=business_domain_service,
                    product_id=product_model.id,
                    business_id=product_model.business_id,
                )
                use_case.execute()
                expiring_count += 1
            except Exception as e:
                logger.error(
                    f"Failed to notify for expiring product {product_model.id}: {str(e)}",
                    exc_info=True,
                )

        # Process expired products
        for product_model in expired_products:
            try:
                product_model.is_expired = True
                product_model.save(update_fields=["is_expired", "updated_at"])
                expired_count += 1

                # Send notification
                business_domain_service = BusinessDomainService(
                    business_repository=BusinessRepositoryImpl(),
                    business_member_repository=BusinessMemberRepositoryImpl(),
                )

                use_case = NotifyExpiringProductsUseCase(
                    product_repository=ProductRepositoryImpl(),
                    business_domain_service=business_domain_service,
                    product_id=product_model.id,
                    business_id=product_model.business_id,
                )
                use_case.execute()
            except Exception as e:
                logger.error(
                    f"Failed to process expired product {product_model.id}: {str(e)}",
                    exc_info=True,
                )

        result = {
            "expiring_products_notified": expiring_count,
            "expired_products_updated": expired_count,
            "timestamp": now.isoformat(),
        }

        logger.info(f"Expired products check completed: {result}")
        return result

    except Exception as exc:
        logger.error(f"Error in check_expired_products task: {exc}", exc_info=True)
        # Retry the task
        raise self.retry(exc=exc) from exc
