"""Business DTOs."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class BusinessCreateDTO:
    """DTO for creating a business."""

    name: str
    unique_name: str
    description: str | None = None
    address: str | None = None
    phone_number: str | None = None
    email: str | None = None
    settings: dict | None = None


@dataclass
class BusinessUpdateDTO:
    """DTO for updating a business."""

    name: str | None = None
    description: str | None = None
    address: str | None = None
    phone_number: str | None = None
    email: str | None = None
    logo_url: str | None = None
    settings: dict | None = None


@dataclass
class BusinessResponseDTO:
    """DTO for business response."""

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
    settings: dict | None
    created_at: datetime
    updated_at: datetime


@dataclass
class BusinessMemberCreateDTO:
    """DTO for adding a business member."""

    user_id: UUID | None = None
    email: str | None = None
    phone_number: str | None = None
    name: str | None = None
    password: str | None = None
    role: str = ""


@dataclass
class BusinessMemberUpdateDTO:
    """DTO for updating a business member."""

    role: str | None = None
    is_active: bool | None = None


@dataclass
class BusinessMemberResponseDTO:
    """DTO for business member response."""

    id: UUID
    business_id: UUID
    user_id: UUID
    role: str
    is_active: bool
    joined_at: datetime
    created_at: datetime
    updated_at: datetime
    user: dict | None = None
    left_at: datetime | None = None
    credentials: dict | None = None
