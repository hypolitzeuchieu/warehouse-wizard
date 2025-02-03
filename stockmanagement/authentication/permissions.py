from __future__ import annotations

from rest_framework.permissions import BasePermission


class IsManagerPermission(BasePermission):

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'manager'


class IsCashier(BasePermission):

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'cashier'


class IsStorekeeper(BasePermission):

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role == 'storekeeper'
        )
