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
