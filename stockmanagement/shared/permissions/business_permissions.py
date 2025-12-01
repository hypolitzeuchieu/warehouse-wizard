"""Business RBAC permissions."""

from __future__ import annotations

from uuid import UUID

from rest_framework.permissions import BasePermission

from domain.business.services import BusinessDomainService
from infrastructure.persistence.repositories import (
    BusinessMemberRepositoryImpl,
    BusinessRepositoryImpl,
)


class BusinessPermission(BasePermission):
    """Base permission class for business operations."""

    def __init__(self, allowed_roles: list[str] | None = None) -> None:
        """Initialize permission with allowed roles."""
        self.allowed_roles = allowed_roles or []
        self._business_domain_service: BusinessDomainService | None = None

    def _get_business_domain_service(self) -> BusinessDomainService:
        """Get business domain service instance."""
        if self._business_domain_service is None:
            self._business_domain_service = BusinessDomainService(
                business_repository=BusinessRepositoryImpl(),
                business_member_repository=BusinessMemberRepositoryImpl(),
            )
        return self._business_domain_service

    def _get_business_id_from_request(self, request) -> UUID | None:
        """Extract business_id from request."""
        # Try to get from URL kwargs
        business_id = request.parser_context.get("kwargs", {}).get("business_id")
        if business_id:
            return UUID(business_id) if isinstance(business_id, str) else business_id

        # Try to get from request data
        business_id = request.data.get("business_id")
        if business_id:
            return UUID(business_id) if isinstance(business_id, str) else business_id

        # Try to get from query params
        business_id = request.query_params.get("business_id")
        if business_id:
            return UUID(business_id) if isinstance(business_id, str) else business_id

        return None

    def _get_user_role_in_business(self, business_id: UUID, user_id: UUID) -> str | None:
        """Get user's role in a specific business."""
        service = self._get_business_domain_service()

        # Check if user is owner
        business = service.business_repository.get_by_id(business_id)
        if business and business.owner_id == user_id:
            return "owner"

        # Check if user is a member and get their role
        member = service.business_member_repository.get_by_business_and_user(business_id, user_id)
        if member and member.is_active_member():
            return member.role

        return None

    def has_permission(self, request, view) -> bool:
        """Check if user has permission."""
        if not request.user or not request.user.is_authenticated:
            return False

        business_id = self._get_business_id_from_request(request)
        if not business_id:
            # If no business_id in request, allow (will be checked in use case)
            return True

        user_role = self._get_user_role_in_business(business_id, request.user.id)
        if not user_role:
            return False

        # Owner has all permissions
        if user_role == "owner":
            return True

        # Check if user's role is in allowed roles
        return user_role in self.allowed_roles

    def has_object_permission(self, request, view, obj) -> bool:
        """Check object-level permission."""
        return self.has_permission(request, view)


class IsBusinessOwner(BusinessPermission):
    """Permission to check if user is business owner."""

    def has_permission(self, request, view) -> bool:
        """Check if user is business owner."""
        if not request.user or not request.user.is_authenticated:
            return False

        business_id = self._get_business_id_from_request(request)
        if not business_id:
            return True  # Will be checked in use case

        user_role = self._get_user_role_in_business(business_id, request.user.id)
        return user_role == "owner"


class IsBusinessManagerOrOwner(BusinessPermission):
    """Permission for manager or owner."""

    def __init__(self) -> None:
        """Initialize permission."""
        super().__init__(allowed_roles=["manager", "owner"])


class CanManageInventory(BusinessPermission):
    """Permission to manage inventory (owner, manager, stock_keeper)."""

    def __init__(self) -> None:
        """Initialize permission."""
        super().__init__(allowed_roles=["owner", "manager", "stock_keeper"])


class CanManageSales(BusinessPermission):
    """Permission to manage sales (owner, manager, cashier)."""

    def __init__(self) -> None:
        """Initialize permission."""
        super().__init__(allowed_roles=["owner", "manager", "cashier"])


class CanManageFinance(BusinessPermission):
    """Permission to manage finance (owner, manager)."""

    def __init__(self) -> None:
        """Initialize permission."""
        super().__init__(allowed_roles=["owner", "manager"])


class CanManageMembers(BusinessPermission):
    """Permission to manage members (owner, manager)."""

    def __init__(self) -> None:
        """Initialize permission."""
        super().__init__(allowed_roles=["owner", "manager"])


class CanViewDashboard(BusinessPermission):
    """Permission to view dashboard (owner only)."""

    def __init__(self) -> None:
        """Initialize permission."""
        super().__init__(allowed_roles=["owner"])


class CanCreateInventory(BusinessPermission):
    """Permission to create inventory items (owner, manager, stock_keeper)."""

    def __init__(self) -> None:
        """Initialize permission."""
        super().__init__(allowed_roles=["owner", "manager", "stock_keeper"])


class CanViewProducts(BusinessPermission):
    """Permission to view products (all business members for sales purposes)."""

    def has_permission(self, request, view) -> bool:
        """Check if user has permission to view products."""
        if not request.user or not request.user.is_authenticated:
            return False

        business_id = self._get_business_id_from_request(request)
        if not business_id:
            return True

        user_role = self._get_user_role_in_business(business_id, request.user.id)
        return user_role is not None


class CanModifyProducts(BusinessPermission):
    """Permission to modify products (owner, manager, stock_keeper)."""

    def __init__(self) -> None:
        """Initialize permission."""
        super().__init__(allowed_roles=["owner", "manager", "stock_keeper"])


class CanAccessSalesReports(BusinessPermission):
    """Permission to access sales reports (owner, manager, cashier). Explicitly excludes stock_keeper."""

    def __init__(self) -> None:
        """Initialize permission."""
        super().__init__(allowed_roles=["owner", "manager", "cashier"])
