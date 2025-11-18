"""Business domain services."""

from __future__ import annotations

from uuid import UUID

from domain.business.repositories import (
    BusinessMemberRepository,
    BusinessRepository,
)


class BusinessDomainService:
    """Business domain service."""

    def __init__(
        self,
        business_repository: BusinessRepository,
        business_member_repository: BusinessMemberRepository,
    ) -> None:
        """Initialize business domain service."""
        self.business_repository = business_repository
        self.business_member_repository = business_member_repository

    def can_user_delete_business(self, business_id: UUID, user_id: UUID) -> bool:
        """Check if user can delete business (only owner)."""
        business = self.business_repository.get_by_id(business_id)
        if not business:
            return False
        return business.owner_id == user_id

    def can_user_manage_managers(self, business_id: UUID, user_id: UUID) -> bool:
        """Check if user can manage managers (only owner)."""
        business = self.business_repository.get_by_id(business_id)
        if not business:
            return False
        return business.owner_id == user_id

    def can_user_manage_members(self, business_id: UUID, user_id: UUID) -> bool:
        """Check if user can manage members (owner or manager)."""
        business = self.business_repository.get_by_id(business_id)
        if not business:
            return False

        # Owner can always manage members
        if business.owner_id == user_id:
            return True

        # Check if user is a manager
        return self.business_member_repository.is_manager(business_id, user_id)

    def is_user_manager(self, business_id: UUID, user_id: UUID) -> bool:
        """Check if user is a manager of the business."""
        return self.business_member_repository.is_manager(business_id, user_id)

    def user_has_access(self, business_id: UUID, user_id: UUID) -> bool:
        """Check if user has access to business (owner or member)."""
        return self.business_repository.user_has_access(business_id, user_id)
