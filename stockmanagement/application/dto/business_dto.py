"""Business DTOs."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class BusinessCreateDTO:
    """DTO for creating a business."""

    name: str
    unique_name: str
    description: Optional[str] = None
    address: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    settings: Optional[dict] = None


@dataclass
class BusinessUpdateDTO:
    """DTO for updating a business."""

    name: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    logo_url: Optional[str] = None
    settings: Optional[dict] = None


@dataclass
class BusinessResponseDTO:
    """DTO for business response."""

    id: UUID
    name: str
    unique_name: str
    owner_id: UUID
    description: Optional[str]
    address: Optional[str]
    phone_number: Optional[str]
    email: Optional[str]
    qr_code_url: Optional[str]
    logo_url: Optional[str]
    is_active: bool
    settings: Optional[dict]
    created_at: datetime
    updated_at: datetime


@dataclass
class BusinessMemberCreateDTO:
    """DTO for adding a business member."""

    user_id: UUID
    role: str  # manager, cashier, stock_keeper, delivery


@dataclass
class BusinessMemberUpdateDTO:
    """DTO for updating a business member."""

    role: Optional[str] = None
    is_active: Optional[bool] = None


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
    user: Optional[dict] = None  # User details
    left_at: Optional[datetime] = None

