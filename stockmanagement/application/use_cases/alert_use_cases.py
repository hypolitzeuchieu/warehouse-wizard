"""Alert use cases for products (expired, low stock)."""

from __future__ import annotations

import logging
from uuid import UUID

from domain.inventory.services import InventoryDomainService
from infrastructure.persistence.models.inventory_models import Product as ProductModel
from infrastructure.persistence.models.notification_models import Notification
from infrastructure.persistence.repositories import (
    BusinessRepositoryImpl,
)

logger = logging.getLogger(__name__)


class CheckExpiredProductsUseCase:
    """Use case for checking and alerting on expired products."""

    def __init__(
        self,
        inventory_domain_service: InventoryDomainService,
        business_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.inventory_domain_service = inventory_domain_service
        self.business_id = business_id

    def execute(self) -> list[dict]:
        """Execute checking expired products and create notifications."""
        expired_products = self.inventory_domain_service.check_expired_products(self.business_id)
        notifications_created = []

        for product_entity in expired_products:
            try:
                # Get Django model for notification
                product_model = ProductModel.objects.get(id=product_entity.id)

                # Check if notification already exists (within last hour)
                from datetime import timedelta

                from django.utils import timezone

                recent_notification = Notification.objects.filter(
                    product=product_model,
                    notification_type="PRODUCT_EXPIRED",
                    created_at__gte=timezone.now() - timedelta(hours=1),
                ).first()

                if not recent_notification:
                    # Create notification for business owner and managers
                    business = BusinessRepositoryImpl().get_by_id(self.business_id)
                    if business:
                        # Notify owner
                        from infrastructure.persistence.models.user_models import (
                            RetailPulseUser as User,
                        )

                        owner = User.objects.filter(id=business.owner_id).first()
                        if owner:
                            notification = Notification.objects.create(
                                product=product_model,
                                user=owner,
                                notification_type="PRODUCT_EXPIRED",
                                message=f"Product '{product_entity.name}' has expired on {product_entity.expiry_date.strftime('%Y-%m-%d') if product_entity.expiry_date else 'N/A'}.",
                                status="UNREAD",
                            )
                            notifications_created.append(
                                {
                                    "product_id": str(product_entity.id),
                                    "product_name": product_entity.name,
                                    "notification_id": str(notification.id),
                                }
                            )

                        # Notify managers
                        from infrastructure.persistence.models.business_models import (
                            BusinessMember as BusinessMemberModel,
                        )

                        managers = BusinessMemberModel.objects.filter(
                            business_id=self.business_id,
                            role="manager",
                            is_active=True,
                        ).select_related("user")

                        for manager_member in managers:
                            notification = Notification.objects.create(
                                product=product_model,
                                user=manager_member.user,
                                notification_type="PRODUCT_EXPIRED",
                                message=f"Product '{product_entity.name}' has expired on {product_entity.expiry_date.strftime('%Y-%m-%d') if product_entity.expiry_date else 'N/A'}.",
                                status="UNREAD",
                            )
                            notifications_created.append(
                                {
                                    "product_id": str(product_entity.id),
                                    "product_name": product_entity.name,
                                    "notification_id": str(notification.id),
                                    "user_id": str(manager_member.user.id),
                                }
                            )

                    logger.info(f"Created expired product notification for {product_entity.name}")

            except Exception as e:
                logger.error(
                    f"Error creating notification for expired product {product_entity.id}: {str(e)}"
                )

        return notifications_created


class CheckLowStockProductsUseCase:
    """Use case for checking and alerting on low stock products."""

    def __init__(
        self,
        inventory_domain_service: InventoryDomainService,
        business_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.inventory_domain_service = inventory_domain_service
        self.business_id = business_id

    def execute(self) -> list[dict]:
        """Execute checking low stock products and create notifications."""
        low_stock_products = self.inventory_domain_service.get_low_stock_products(self.business_id)
        notifications_created = []

        for product_entity in low_stock_products:
            try:
                # Get Django model for notification
                product_model = ProductModel.objects.get(id=product_entity.id)

                # Check if notification already exists (within last 24 hours)
                from datetime import timedelta

                from django.utils import timezone

                recent_notification = Notification.objects.filter(
                    product=product_model,
                    notification_type="STOCK_LOW",
                    created_at__gte=timezone.now() - timedelta(hours=24),
                ).first()

                if not recent_notification:
                    # Create notification for business owner and managers
                    business = BusinessRepositoryImpl().get_by_id(self.business_id)
                    if business:
                        # Notify owner
                        from infrastructure.persistence.models.user_models import (
                            RetailPulseUser as User,
                        )

                        owner = User.objects.filter(id=business.owner_id).first()
                        if owner:
                            notification = Notification.objects.create(
                                product=product_model,
                                user=owner,
                                notification_type="STOCK_LOW",
                                message=f"Product '{product_entity.name}' is low in stock. Current: {product_entity.quantity}, Minimum: {product_entity.min_quantity}.",
                                status="UNREAD",
                            )
                            notifications_created.append(
                                {
                                    "product_id": str(product_entity.id),
                                    "product_name": product_entity.name,
                                    "notification_id": str(notification.id),
                                }
                            )

                        # Notify managers
                        from infrastructure.persistence.models.business_models import (
                            BusinessMember as BusinessMemberModel,
                        )

                        managers = BusinessMemberModel.objects.filter(
                            business_id=self.business_id,
                            role="manager",
                            is_active=True,
                        ).select_related("user")

                        for manager_member in managers:
                            notification = Notification.objects.create(
                                product=product_model,
                                user=manager_member.user,
                                notification_type="STOCK_LOW",
                                message=f"Product '{product_entity.name}' is low in stock. Current: {product_entity.quantity}, Minimum: {product_entity.min_quantity}.",
                                status="UNREAD",
                            )
                            notifications_created.append(
                                {
                                    "product_id": str(product_entity.id),
                                    "product_name": product_entity.name,
                                    "notification_id": str(notification.id),
                                    "user_id": str(manager_member.user.id),
                                }
                            )

                    logger.info(f"Created low stock notification for {product_entity.name}")

            except Exception as e:
                logger.error(
                    f"Error creating notification for low stock product {product_entity.id}: {str(e)}"
                )

        return notifications_created
