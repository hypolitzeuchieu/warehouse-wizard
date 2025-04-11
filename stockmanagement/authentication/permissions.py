from __future__ import annotations

from rest_framework.permissions import BasePermission


ROLE_HIERARCHY = {
    'manager': ['manager', 'cashier', 'storekeeper'],
    'cashier': ['cashier'],
    'storekeeper': ['storekeeper'],
}


def has_role(user, *roles):
    if not user.is_authenticated:
        return False
    allowed_roles = ROLE_HIERARCHY.get(user.role, [])
    return any(role in allowed_roles for role in roles)


class IsManagerPermission(BasePermission):
    def has_permission(self, request, view):
        return has_role(request.user, 'manager')


class IsCashier(BasePermission):
    def has_permission(self, request, view):
        return has_role(request.user, 'cashier')


class IsStorekeeper(BasePermission):
    def has_permission(self, request, view):
        return has_role(request.user, 'storekeeper')
