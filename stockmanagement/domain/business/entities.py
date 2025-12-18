"""Business domain entities."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class Business:
    """Business entity."""

    id: UUID
    name: str
    unique_name: str
    owner_id: UUID
    description: str | None
    address: str | None
    phone_number: str | None
    email: str | None
    qr_code_url: str | None
    logo_url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    settings: dict | None = None

    def __post_init__(self) -> None:
        """Validate business data."""
        if not self.name:
            raise ValueError("Business name is required")
        if not self.unique_name:
            raise ValueError("Business unique name is required")


@dataclass
class BusinessMember:
    """Business member entity (employees, managers, etc.)."""

    id: UUID
    business_id: UUID
    user_id: UUID
    role: str
    is_active: bool
    joined_at: datetime
    left_at: datetime | None
    created_at: datetime
    updated_at: datetime

    def is_manager(self) -> bool:
        """Check if member is a manager."""
        return self.role == "manager"

    def is_active_member(self) -> bool:
        """Check if member is currently active."""
        return self.is_active and self.left_at is None
