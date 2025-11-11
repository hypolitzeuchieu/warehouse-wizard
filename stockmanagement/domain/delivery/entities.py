"""Delivery domain entities."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID


class DeliveryStatus(str, Enum):
    """Delivery status enumeration."""

    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


@dataclass
class Delivery:
    """Delivery entity."""

    id: UUID
    business_id: UUID
    order_id: UUID
    delivery_person_id: Optional[UUID]
    customer_id: UUID
    status: DeliveryStatus
    shipping_address: str
    estimated_delivery_time: Optional[datetime]
    actual_delivery_time: Optional[datetime]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    def is_completed(self) -> bool:
        """Check if delivery is completed."""
        return self.status == DeliveryStatus.DELIVERED

    def can_be_cancelled(self) -> bool:
        """Check if delivery can be cancelled."""
        return self.status in (
            DeliveryStatus.PENDING,
            DeliveryStatus.ASSIGNED,
        )

