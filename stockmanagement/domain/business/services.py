"""Business domain services."""

from __future__ import annotations

from uuid import UUID

from domain.business.repositories import (
    BusinessMemberRepository,
    BusinessRepository,
)
from shared.utils.uuid_utils import compare_uuids, normalize_uuid


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
        bid = normalize_uuid(business_id)
        if bid is None:
            return False
        business = self.business_repository.get_by_id(bid)
        if not business:
            return False
        return compare_uuids(business.owner_id, user_id)

    def can_user_manage_managers(self, business_id: UUID, user_id: UUID) -> bool:
        """Check if user can manage managers (only owner)."""
        bid = normalize_uuid(business_id)
        if bid is None:
            return False
        business = self.business_repository.get_by_id(bid)
        if not business:
            return False
        return compare_uuids(business.owner_id, user_id)

    def can_user_manage_members(self, business_id: UUID, user_id: UUID) -> bool:
        """Check if user can manage members (owner or manager)."""
        bid = normalize_uuid(business_id)
        uid = normalize_uuid(user_id)
        if bid is None or uid is None:
            return False
        business = self.business_repository.get_by_id(bid)
        if not business:
            return False
        if compare_uuids(business.owner_id, uid):
            return True
        return self.business_member_repository.is_manager(bid, uid)

    def is_user_manager(self, business_id: UUID, user_id: UUID) -> bool:
        """Check if user is a manager of the business."""
        bid = normalize_uuid(business_id)
        uid = normalize_uuid(user_id)
        if bid is None or uid is None:
            return False
        return self.business_member_repository.is_manager(bid, uid)

    def user_has_access(self, business_id: UUID, user_id: UUID) -> bool:
        """Check if user has access to business (owner or member)."""
        bid = normalize_uuid(business_id)
        uid = normalize_uuid(user_id)
        if bid is None or uid is None:
            return False
        return self.business_repository.user_has_access(bid, uid)

    def get_business(self, business_id: UUID):
        """Get business entity by ID."""
        return self.business_repository.get_by_id(business_id)

    def get_user_role_in_business(self, business_id: UUID, user_id: UUID) -> str | None:
        """Get user's role in a specific business."""
        bid = normalize_uuid(business_id)
        uid = normalize_uuid(user_id)
        if bid is None:
            return None
        business = self.business_repository.get_by_id(bid)
        if not business:
            return None
        if uid is not None and compare_uuids(business.owner_id, uid):
            return "owner"
        if uid is None:
            return None
        member = self.business_member_repository.get_by_business_and_user(bid, uid)
        if member and member.is_active_member():
            return member.role
        return None

    def can_create_inventory(self, business_id: UUID, user_id: UUID) -> bool:
        """Check if user can create inventory items (owner, manager, stock_keeper)."""
        role = self.get_user_role_in_business(business_id, user_id)
        if not role:
            return False
        return role in ["owner", "manager", "stock_keeper"]

    def can_modify_products(self, business_id: UUID, user_id: UUID) -> bool:
        """Check if user can modify products (owner, manager, stock_keeper)."""
        role = self.get_user_role_in_business(business_id, user_id)
        if not role:
            return False
        return role in ["owner", "manager", "stock_keeper"]

    def can_access_sales(self, business_id: UUID, user_id: UUID) -> bool:
        """Check if user can access sales/cash register (owner, manager, cashier)."""
        role = self.get_user_role_in_business(business_id, user_id)
        if not role:
            return False
        return role in ["owner", "manager", "cashier"]

    def can_generate_sales_report(self, business_id: UUID, user_id: UUID) -> bool:
        """Check if user can generate sales reports (owner, manager, cashier)."""
        role = self.get_user_role_in_business(business_id, user_id)
        if not role:
            return False
        return role in ["owner", "manager", "cashier"]

    def can_generate_inventory_report(self, business_id: UUID, user_id: UUID) -> bool:
        """Check if user can generate inventory reports (owner, manager, stock_keeper)."""
        role = self.get_user_role_in_business(business_id, user_id)
        if not role:
            return False
        return role in ["owner", "manager", "stock_keeper"]

    def can_generate_stock_report(self, business_id: UUID, user_id: UUID) -> bool:
        """Check if user can generate stock reports (owner, manager, stock_keeper)."""
        role = self.get_user_role_in_business(business_id, user_id)
        if not role:
            return False
        return role in ["owner", "manager", "stock_keeper"]

    def is_user_owner(self, business_id: UUID, user_id: UUID) -> bool:
        """Check if user is the owner of the business."""
        bid = normalize_uuid(business_id)
        if bid is None:
            return False
        business = self.business_repository.get_by_id(bid)
        if not business:
            return False
        return compare_uuids(business.owner_id, user_id)
