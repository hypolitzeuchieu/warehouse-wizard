"""Business domain repositories (interfaces)."""

from abc import ABC, abstractmethod
from uuid import UUID

from domain.business.entities import Business, BusinessMember


class BusinessRepository(ABC):
    """Business repository interface."""

    @abstractmethod
    def get_by_id(self, business_id: UUID) -> Business | None:
        """Get business by ID."""
        pass

    @abstractmethod
    def get_by_unique_name(self, unique_name: str) -> Business | None:
        """Get business by unique name."""
        pass

    @abstractmethod
    def get_by_owner(self, owner_id: UUID) -> list[Business]:
        """Get businesses owned by a user."""
        pass

    @abstractmethod
    def create(self, business: Business) -> Business:
        """Create a new business."""
        pass

    @abstractmethod
    def update(self, business: Business) -> Business:
        """Update an existing business."""
        pass

    @abstractmethod
    def delete(self, business_id: UUID) -> None:
        """Delete a business."""
        pass

    @abstractmethod
    def user_has_access(self, business_id: UUID, user_id: UUID) -> bool:
        """Check if user has access to business."""
        pass


class BusinessMemberRepository(ABC):
    """Business member repository interface."""

    @abstractmethod
    def get_by_id(self, member_id: UUID) -> BusinessMember | None:
        """Get business member by ID."""
        pass

    @abstractmethod
    def get_business_members(
        self, business_id: UUID, active_only: bool = True
    ) -> list[BusinessMember]:
        """Get all members of a business."""
        pass

    @abstractmethod
    def get_user_businesses(self, user_id: UUID) -> list[BusinessMember]:
        """Get all businesses a user is a member of."""
        pass

    @abstractmethod
    def get_managers(self, business_id: UUID) -> list[BusinessMember]:
        """Get all managers of a business."""
        pass

    @abstractmethod
    def create(self, member: BusinessMember) -> BusinessMember:
        """Add a member to a business."""
        pass

    @abstractmethod
    def update(self, member: BusinessMember) -> BusinessMember:
        """Update a business member."""
        pass

    @abstractmethod
    def remove(self, member_id: UUID) -> None:
        """Remove a member from a business."""
        pass

    @abstractmethod
    def is_manager(self, business_id: UUID, user_id: UUID) -> bool:
        """Check if user is a manager of the business."""
        pass

    @abstractmethod
    def get_by_business_and_user(self, business_id: UUID, user_id: UUID) -> BusinessMember | None:
        """Get business member by business and user."""
        pass
