from rest_framework.permissions import BasePermission


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

        if role in (
            "HR_ADMIN",
            "HR_MANAGER",
        ):
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

        if role in (
            "HR_ADMIN",
            "HR_MANAGER",
        ):
            return action in (
                "retrieve",
                "approve",
                "reject",
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
            return request.method in (
                "GET",
                "HEAD",
                "OPTIONS",
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
