from rest_framework.permissions import BasePermission

from accounts.models import User


class IsActiveRecruitmentManager(BasePermission):
    """
    Allow access to active authenticated HR management users.

    HR_MANAGER departmental restrictions are enforced by the
    corresponding recruitment services and queryset filtering.
    """

    MANAGEMENT_ROLES = {
        User.Role.SUPER_ADMIN,
        User.Role.HR_ADMIN,
        User.Role.HR_MANAGER,
    }

    def has_permission(self, request, view):
        user = request.user

        return (
            user
            and user.is_authenticated
            and user.is_active
            and user.role in self.MANAGEMENT_ROLES
        )

class IsRecruitmentAdmin(BasePermission):
    """
    Allow access only to active Super Admins and HR Admins.

    This permission is intended for standalone candidate creation
    and other explicitly administrative recruitment operations.
    """

    ADMIN_ROLES = {
        User.Role.SUPER_ADMIN,
        User.Role.HR_ADMIN,
    }

    def has_permission(self, request, view):
        user = request.user

        return (
            user
            and user.is_authenticated
            and user.is_active
            and user.role in self.ADMIN_ROLES
        )
