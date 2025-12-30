"""Business RBAC permissions."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from domain.business.services import BusinessDomainService
from shared.exceptions.specific import BadRequestError

if TYPE_CHECKING:
    pass


class BusinessPermission(BasePermission):
    """Base permission class for business operations."""

    def __init__(
        self,
        allowed_roles: list[str] | None = None,
        business_domain_service: BusinessDomainService | None = None,
    ) -> None:
        """
        Initialize permission with allowed roles.

        Args:
            allowed_roles: List of allowed roles
        """
        self.allowed_roles = allowed_roles or []
        self._business_domain_service = business_domain_service

    def _get_business_domain_service(self) -> BusinessDomainService:
        """
        Get business domain service instance.

        Note: For Clean Architecture, BusinessDomainService should be injected via constructor.
        """
        if self._business_domain_service is None:
            from infrastructure.persistence.repositories import (
                BusinessMemberRepositoryImpl,
                BusinessRepositoryImpl,
            )

            self._business_domain_service = BusinessDomainService(
                business_repository=BusinessRepositoryImpl(),
                business_member_repository=BusinessMemberRepositoryImpl(),
            )
        return self._business_domain_service

    def _get_business_id_from_request(self, request) -> UUID | None:
        """
        Extract business_id from request with security validation.

        Validates that business_id is consistent across all sources (URL, body, query params)
        to prevent security issues from conflicting values.
        """
        sources = {
            "url": request.parser_context.get("kwargs", {}).get("business_id"),
            "body": (
                request.data.get("business_id") if hasattr(request, "data") else None
            ),
            "query": (
                request.query_params.get("business_id")
                if hasattr(request, "query_params")
                else None
            ),
        }

        # Find all non-None values
        values = []
        for source_name, value in sources.items():
            if value is not None:
                try:
                    uuid_value = UUID(str(value)) if isinstance(value, str) else value
                    values.append((source_name, uuid_value))
                except (ValueError, TypeError):
                    continue

        if not values:
            return None

        # Security: Validate consistency - all values must be the same
        if len(values) > 1:
            unique_values = {str(v[1]) for v in values}
            if len(unique_values) > 1:
                source_names = [v[0] for v in values]
                raise BadRequestError(
                    detail=(
                        f"business_id must be consistent across all sources. "
                        f"Found conflicting values in: {', '.join(source_names)}"
                    ),
                    code="INCONSISTENT_BUSINESS_ID",
                )

        return values[0][1]

    def _get_user_role_in_business(
        self, business_id: UUID, user_id: UUID
    ) -> str | None:
        """Get user's role in a specific business."""
        service = self._get_business_domain_service()

        # Check if user is owner
        business = service.business_repository.get_by_id(business_id)
        if business and business.owner_id == user_id:
            return "owner"

        # Check if user is a member and get their role
        member = service.business_member_repository.get_by_business_and_user(
            business_id, user_id
        )
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


class IsBusinessActive(BusinessPermission):
    """
    Permission to check if business is active before allowing write operations.

    Allows GET, HEAD, OPTIONS requests (read-only) but blocks POST, PUT, PATCH, DELETE
    if business is not active (no active subscription).
    """

    def has_permission(self, request, view) -> bool:
        """Check if business is active for write operations."""
        # Always allow GET, HEAD, OPTIONS (read-only operations)
        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return True

        # For write operations (POST, PUT, PATCH, DELETE), check if business is active
        if not request.user or not request.user.is_authenticated:
            return False

        business_id = self._get_business_id_from_request(request)
        if not business_id:
            # If no business_id, allow (will be checked in use case)
            return True

        # Check if business is activated (has active subscription)
        service = self._get_business_domain_service()
        if not service.is_business_activated(business_id):
            raise PermissionDenied(
                detail=(
                    "This business is not active. "
                    "Please activate your subscription to perform this action."
                ),
                code="BUSINESS_INACTIVE",
            )

        # Business is active, check role-based permissions
        return super().has_permission(request, view)
