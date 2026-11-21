from rest_framework.permissions import BasePermission
from employees.services.onboarding_permissions import (
    OnboardingPermissionService,
)
from employees.services.document_access import DocumentAccessService
from employees.models import EmployeeProfile

class EmployeeProfilePermission(BasePermission):
    """
    Control access to employee profiles based on user roles.
    """

    def has_permission(self, request, view):
        """Control access before an employee object is accessed."""

        user = request.user

        if not (
            user
            and user.is_authenticated
        ):
            return False

        role = user.role

        if role == "SUPER_ADMIN":
            return True

        if role == "HR_ADMIN":
            return request.method != "DELETE"

        if role == "HR_MANAGER":
            return request.method in (
                "GET",
                "HEAD",
                "OPTIONS",
            )

        if role == "EMPLOYEE":
            return request.method in (
                "GET",
                "HEAD",
                "OPTIONS",
            )

        return False

    def has_object_permission(
        self,
        request,
        view,
        obj,
    ):
        """Apply role-based access to an employee profile."""

        role = request.user.role

        if role == "SUPER_ADMIN":
            return True

        if role == "HR_ADMIN":
            return request.method != "DELETE"

        if role == "HR_MANAGER":
            return request.method in (
                "GET",
                "HEAD",
                "OPTIONS",
            )

        if role == "EMPLOYEE":
            return (
                request.method in (
                    "GET",
                    "HEAD",
                    "OPTIONS",
                )
                and obj.user == request.user
            )

        return False

class DepartmentPositionReadPermission(BasePermission):
    """
    Allow read-only access to departments and positions
    for authorized HR roles.
    """


class DepartmentPositionReadPermission(BasePermission):
    """
    Allow read-only access to departments and positions
    for authorized HR roles.
    """

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if user.role not in (
            "SUPER_ADMIN",
            "HR_ADMIN",
            "HR_MANAGER",
        ):
            return False

        return True


class LeaveRequestPermission(BasePermission):
    """
    Control access to leave requests based on user roles.
    """

    def has_permission(self, request, view):
        """Control access to leave request endpoints."""

        user = request.user

        if not (
            user
            and user.is_authenticated
        ):
            return False

        role = user.role
        action = view.action

        if role == "SUPER_ADMIN":
            return True

        if role == "HR_ADMIN":
            return action in (
                "list",
                "retrieve",
                "approve",
                "reject",
            )

        if role == "HR_MANAGER":
            # A manager must have an employee profile.
            try:
                user.employee_profile
            except EmployeeProfile.DoesNotExist:
                return False

            return action in (
                "list",
                "retrieve",
                "approve",
                "reject",
            )

        if role == "EMPLOYEE":
            return action in (
                "list",
                "retrieve",
                "create",
                "partial_update",
                "cancel",
            )

        return False

    def has_object_permission(
        self,
        request,
        view,
        obj,
    ):
        """Apply object-level access to a leave request."""

        user = request.user
        role = user.role
        action = view.action

        if role == "SUPER_ADMIN":
            return True

        if role == "HR_ADMIN":
            return action in (
                "retrieve",
                "approve",
                "reject",
            )

        if role == "HR_MANAGER":
            try:
                manager_profile = user.employee_profile
            except EmployeeProfile.DoesNotExist:
                return False

            return (
                obj.employee.department_id
                == manager_profile.department_id
                and action in (
                    "retrieve",
                    "approve",
                    "reject",
                )
            )

        if role == "EMPLOYEE":
            return (
                obj.employee.user == user
                and action in (
                    "retrieve",
                    "partial_update",
                    "cancel",
                )
            )

        return False

class BankAccountPermission(BasePermission):
    """Control access to employee bank account data."""

    def has_permission(self, request, view):
        """Check permission for bank account endpoints."""

        user = request.user

        if not (user and user.is_authenticated):
            return False

        role = user.role

        if role == "SUPER_ADMIN":
            return True

        if role == "HR_ADMIN":
            return request.method in (
                "GET",
                "POST",
                "PUT",
                "PATCH",
            )

        if role == "HR_MANAGER":
            return request.method in (
                "GET",
                "HEAD",
                "OPTIONS",
            )

        if role == "EMPLOYEE":
            return request.method in (
                "GET",
                "HEAD",
                "OPTIONS",
                "POST",
                "PUT",
                "PATCH",
            )

        return False

    def has_object_permission(self, request, view, obj):
        """Check permission for a specific bank account."""

        user = request.user
        role = user.role

        if role == "SUPER_ADMIN":
            return True

        if role == "HR_ADMIN":
            return request.method in (
                "GET",
                "POST",
                "PUT",
                "PATCH",
            )

        if role == "HR_MANAGER":
            if request.method not in (
                "GET",
                "HEAD",
                "OPTIONS",
            ):
                return False

            try:
                manager_department_id = (
                    user.employee_profile.department_id
                )
            except EmployeeProfile.DoesNotExist:
                return False

            return (
                obj.employee.department_id
                == manager_department_id
            )

        if role == "EMPLOYEE":
            return (
                obj.employee.user == user
                and request.method in (
                    "GET",
                    "HEAD",
                    "OPTIONS",
                    "POST",
                    "PUT",
                    "PATCH",
                )
            )

        return False

class PerformanceReviewPermission(BasePermission):
    """Control access to employee performance reviews."""

    def has_permission(self, request, view):
        """Check permission for performance review endpoints."""

        user = request.user

        if not (user and user.is_authenticated):
            return False

        role = user.role
        action = view.action

        if role == "SUPER_ADMIN":
            return True

        if role == "HR_ADMIN":
            return action in (
                "list",
                "retrieve",
                "create",
                "update",
                "partial_update",
                "submit",
                "acknowledge",
            )

        if role == "HR_MANAGER":
            return action in (
                "list",
                "retrieve",
                "create",
                "update",
                "partial_update",
                "submit",
                "acknowledge",
            )

        if role == "EMPLOYEE":
            return action in (
                "list",
                "retrieve",
                "create",
                "partial_update",
                "submit",
                "acknowledge",
            )

        return False

    def has_object_permission(self, request, view, obj):
        """Check permission for a specific performance review."""

        user = request.user
        role = user.role
        action = view.action

        if role == "SUPER_ADMIN":
            return True

        if role in ("HR_ADMIN", "HR_MANAGER"):
            return action in (
                "retrieve",
                "update",
                "partial_update",
                "submit",
                "acknowledge",
            )

        if role == "EMPLOYEE":
            return (
                obj.employee.user == user
                and action in (
                    "retrieve",
                    "partial_update",
                    "submit",
                    "acknowledge",
                )
            )

        return False

class HRDocumentPermission(BasePermission):
    """Control access to HR documents based on roles and confidentiality."""

    def has_permission(self, request, view):
        user = request.user

        if not (
            user
            and user.is_authenticated
            and user.is_active
        ):
            return False

        role = user.role
        action = view.action

        allowed_actions = {
            "SUPER_ADMIN": {
                "list", "retrieve", "create",
                "update", "partial_update",
                "verify", "reject", "archive",
                "versions", "create_version", "reviews",
            },
            "HR_ADMIN": {
                "list", "retrieve", "create",
                "update", "partial_update",
                "verify", "reject", "archive",
                "versions", "create_version", "reviews",
            },
            "HR_MANAGER": {
                "list", "retrieve",
                "verify", "reject", "archive",
                "versions", "reviews",
            },
            "EMPLOYEE": {
                "list", "retrieve", "create",
                "update", "partial_update",
                "versions", "create_version", "reviews",
            },
        }

        return action in allowed_actions.get(role, set())

    def has_object_permission(self, request, view, obj):
        user = request.user
        role = user.role
        action = view.action

        if action in ("retrieve", "versions", "create_version","reviews", ):
            return DocumentAccessService.can_view_document(
                user, obj
            )

        if action in ("update", "partial_update"):
            return DocumentAccessService.can_manage_document(
                user, obj
            )

        if action in ("verify", "reject", "archive",):
            return (
                role in DocumentAccessService.HR_ROLES
                and DocumentAccessService.can_view_document(
                    user, obj
                )
            )

        return role == "SUPER_ADMIN"

class HRDocumentDownloadPermission(BasePermission):
    """Allow downloads only when access rules are satisfied."""

    def has_permission(self, request, view):
        user = request.user

        if not (
            user
            and user.is_authenticated
            and user.is_active
        ):
            return False

        return user.role in (
            "SUPER_ADMIN",
            "HR_ADMIN",
            "EMPLOYEE",
        )

    def has_object_permission(self, request, view, obj):
        return DocumentAccessService.can_download_document(
            request.user,
            obj,
        )

class OnboardingJourneyPermission(BasePermission):
    """Control API access to onboarding journeys."""

    OPERATIONAL_ROLES = {
        "SUPER_ADMIN",
        "HR_ADMIN",
        "HR_MANAGER",
    }
    ALLOWED_ROLES = OPERATIONAL_ROLES | {"EMPLOYEE"}

    def has_permission(self, request, view):
        user = request.user

        if not (
            user
            and getattr(user, "is_authenticated", False)
            and getattr(user, "is_active", False)
            and getattr(user, "pk", None)
        ):
            return False

        role = getattr(user, "role", None)
        action = getattr(view, "action", None)

        if role not in self.ALLOWED_ROLES:
            return False

        if action in {"list", "retrieve"}:
            return True

        if action == "create":
            return role in self.OPERATIONAL_ROLES

        return False

    def has_object_permission(self, request, view, obj):
        if getattr(view, "action", None) != "retrieve":
            return False

        return OnboardingPermissionService.can_view_journey(
            request.user,
            obj,
        )

class OnboardingTaskPermission(BasePermission):
    """Control API access to onboarding tasks."""

    OPERATIONAL_ROLES = {
        "SUPER_ADMIN",
        "HR_ADMIN",
        "HR_MANAGER",
    }
    ALLOWED_ROLES = OPERATIONAL_ROLES | {"EMPLOYEE"}

    def has_permission(self, request, view):
        user = request.user

        if not (
            user
            and getattr(user, "is_authenticated", False)
            and getattr(user, "is_active", False)
            and getattr(user, "pk", None)
        ):
            return False

        role = getattr(user, "role", None)
        action = getattr(view, "action", None)

        if role not in self.ALLOWED_ROLES:
            return False

        if action in {"list", "retrieve"}:
            return True

        if action in {"assign", "transition"}:
            return role in self.OPERATIONAL_ROLES

        return False

    def has_object_permission(self, request, view, obj):
        action = getattr(view, "action", None)

        if action == "retrieve":
            return OnboardingPermissionService.can_view_task(
                request.user,
                obj,
            )

        if action in {"assign", "transition"}:
            return (
                request.user.role in self.OPERATIONAL_ROLES
                and OnboardingPermissionService.can_view_task(
                    request.user,
                    obj,
                )
            )

        return False

class DocumentAccessLogPermission(BasePermission):
    """Restrict document audit log access to active HR administrators and managers."""

    ALLOWED_ROLES = {
        "SUPER_ADMIN",
        "HR_ADMIN",
        "HR_MANAGER",
    }

    def has_permission(self, request, view):
        user = request.user

        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.role in self.ALLOWED_ROLES
            and request.method in ("GET", "HEAD", "OPTIONS")
        )

class DashboardPermission(BasePermission):
    """
    Restrict HR dashboard access to active HR personnel.
    """

    ALLOWED_ROLES = {
        "SUPER_ADMIN",
        "HR_ADMIN",
        "HR_MANAGER",
    }

    def has_permission(self, request, view):
        user = request.user

        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.role in self.ALLOWED_ROLES
            and request.method in ("GET", "HEAD", "OPTIONS")
        )
