from rest_framework import permissions


class IsSuperAdmin(permissions.BasePermission):
    """Allows access only to Super Admin users."""

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role == "SUPER_ADMIN"
        )


class IsHRAdmin(permissions.BasePermission):
    """Allows access to Super Admins and HR Admins."""

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role in {
                "SUPER_ADMIN",
                "HR_ADMIN",
            }
        )


class IsHRManager(permissions.BasePermission):
    """Allows access to HR management roles."""

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role in {
                "SUPER_ADMIN",
                "HR_ADMIN",
                "HR_MANAGER",
            }
        )


class IsEmployee(permissions.BasePermission):
    """Allows access to authenticated employees."""

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role == "EMPLOYEE"
        )


class IsHRAdminOrManager(permissions.BasePermission):
    """Allows HR Admins and HR Managers to access HR resources."""

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role in {
                "SUPER_ADMIN",
                "HR_ADMIN",
                "HR_MANAGER",
            }
        )


class IsStaffOrOwnDeactivation(permissions.BasePermission):
    """
    Allows HR administrators to manage any account.

    A regular employee may only deactivate their own account.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False

        if request.user.role in {
            "SUPER_ADMIN",
            "HR_ADMIN",
        }:
            return True

        return (
            obj.id == request.user.id
            and request.data.get("is_active") is False
        )


class IsAdmin(permissions.BasePermission):
    """Allows access to administrative privilege management."""

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role == "SUPER_ADMIN"
        )


class IsOwnerOrHRAdmin(permissions.BasePermission):
    """
    Allows users to access their own resources.

    HR Admins and Super Admins can access resources belonging
    to other users.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False

        if request.user.role in {
            "SUPER_ADMIN",
            "HR_ADMIN",
        }:
            return True

        return obj.id == request.user.id
