"""Delivery domain repositories (interfaces)."""

from abc import ABC, abstractmethod
from uuid import UUID

from domain.delivery.entities import Delivery, DeliveryStatus


class DeliveryRepository(ABC):
    """Delivery repository interface."""

    @abstractmethod
    def get_by_id(self, delivery_id: UUID) -> Delivery | None:
        """Get delivery by ID."""
        pass

    @abstractmethod
    def get_by_order(self, order_id: UUID) -> Delivery | None:
        """Get delivery for an order."""
        pass

    @abstractmethod
    def get_by_delivery_person(
        self, delivery_person_id: UUID, status: DeliveryStatus | None = None
    ) -> list[Delivery]:
        """Get deliveries assigned to a delivery person."""
        pass

    @abstractmethod
    def get_by_business(
        self, business_id: UUID, status: DeliveryStatus | None = None
    ) -> list[Delivery]:
        """Get deliveries for a business."""
        pass

    @abstractmethod
    def create(self, delivery: Delivery) -> Delivery:
        """Create a new delivery."""
        pass

    @abstractmethod
    def update(self, delivery: Delivery) -> Delivery:
        """Update an existing delivery."""
        pass
