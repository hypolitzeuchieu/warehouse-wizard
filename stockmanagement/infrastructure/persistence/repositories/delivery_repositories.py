"""Delivery repository implementations."""

from uuid import UUID

from domain.delivery.entities import Delivery, DeliveryStatus
from domain.delivery.repositories import DeliveryRepository
from infrastructure.persistence.models.delivery_models import (
    Delivery as DeliveryModel,
)


class DeliveryRepositoryImpl(DeliveryRepository):
    """Django implementation of DeliveryRepository."""

    def get_by_id(self, delivery_id: UUID) -> Delivery | None:
        """Get delivery by ID."""
        try:
            delivery_model = DeliveryModel.objects.select_related(
                "business", "order", "delivery_person", "customer"
            ).get(id=delivery_id)
            return self._to_entity(delivery_model)
        except DeliveryModel.DoesNotExist:
            return None

    def get_by_order(self, order_id: UUID) -> Delivery | None:
        """Get delivery for an order."""
        try:
            delivery_model = DeliveryModel.objects.select_related(
                "business", "order", "delivery_person", "customer"
            ).get(order_id=order_id)
            return self._to_entity(delivery_model)
        except DeliveryModel.DoesNotExist:
            return None

    def get_by_delivery_person(
        self, delivery_person_id: UUID, status: DeliveryStatus | None = None
    ) -> list[Delivery]:
        """Get deliveries assigned to a delivery person."""
        query = DeliveryModel.objects.filter(delivery_person_id=delivery_person_id).select_related(
            "business", "order", "customer"
        )

        if status:
            query = query.filter(status=status.value)

        deliveries = query.order_by("-created_at")
        return [self._to_entity(delivery) for delivery in deliveries]

    def get_by_business(
        self, business_id: UUID, status: DeliveryStatus | None = None
    ) -> list[Delivery]:
        """Get deliveries for a business."""
        query = DeliveryModel.objects.filter(business_id=business_id).select_related(
            "order", "delivery_person", "customer"
        )

        if status:
            query = query.filter(status=status.value)

        deliveries = query.order_by("-created_at")
        return [self._to_entity(delivery) for delivery in deliveries]

    def create(self, delivery: Delivery) -> Delivery:
        """Create a new delivery."""
        delivery_model = DeliveryModel(
            id=delivery.id,
            business_id=delivery.business_id,
            order_id=delivery.order_id,
            delivery_person_id=delivery.delivery_person_id,
            customer_id=delivery.customer_id,
            status=delivery.status.value,
            shipping_address=delivery.shipping_address,
            estimated_delivery_time=delivery.estimated_delivery_time,
            actual_delivery_time=delivery.actual_delivery_time,
            notes=delivery.notes,
        )
        delivery_model.save()
        return self._to_entity(delivery_model)

    def update(self, delivery: Delivery) -> Delivery:
        """Update an existing delivery."""
        delivery_model = DeliveryModel.objects.get(id=delivery.id)
        delivery_model.delivery_person_id = delivery.delivery_person_id
        delivery_model.status = delivery.status.value
        delivery_model.shipping_address = delivery.shipping_address
        delivery_model.estimated_delivery_time = delivery.estimated_delivery_time
        delivery_model.actual_delivery_time = delivery.actual_delivery_time
        delivery_model.notes = delivery.notes
        delivery_model.save()
        return self._to_entity(delivery_model)

    def _to_entity(self, delivery_model: DeliveryModel) -> Delivery:
        """Convert Django model to domain entity."""
        return Delivery(
            id=delivery_model.id,
            business_id=delivery_model.business_id,
            order_id=delivery_model.order_id,
            delivery_person_id=delivery_model.delivery_person_id,
            customer_id=delivery_model.customer_id,
            status=DeliveryStatus(delivery_model.status),
            shipping_address=delivery_model.shipping_address,
            estimated_delivery_time=delivery_model.estimated_delivery_time,
            actual_delivery_time=delivery_model.actual_delivery_time,
            notes=delivery_model.notes,
            created_at=delivery_model.created_at,
            updated_at=delivery_model.updated_at,
        )
