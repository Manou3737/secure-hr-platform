
"""Centralized access-control rules for private HR documents."""


class DocumentAccessService:
    """Evaluate access to HR document metadata and file contents."""

    PRIVILEGED_ROLES = {"SUPER_ADMIN", "HR_ADMIN"}
    HR_ROLES = {"SUPER_ADMIN", "HR_ADMIN", "HR_MANAGER"}

    @staticmethod
    def _is_active_authenticated_user(user):
        return bool(
            user
            and getattr(user, "is_authenticated", False)
            and getattr(user, "is_active", False)
        )

    @staticmethod
    def _get_manager_department_id(user):
        """Return the HR manager's department ID, or None if unavailable."""
        profile = getattr(user, "employee_profile", None)
        return getattr(profile, "department_id", None)

    @classmethod
    def can_view_document(cls, user, document):
        if not cls._is_active_authenticated_user(user):
            return False

        role = getattr(user, "role", None)
        confidentiality = getattr(document, "confidentiality", None)

        if role in cls.PRIVILEGED_ROLES:
            return True

        if confidentiality == "RESTRICTED":
            return False

        if role == "HR_MANAGER":
            manager_department_id = cls._get_manager_department_id(user)

            return bool(
                manager_department_id
                and document.employee.department_id == manager_department_id
            )

        if role == "EMPLOYEE":
            return document.employee.user_id == user.pk

        return False

    @classmethod
    def can_download_document(cls, user, document):
        """Check access to a verified document's file."""
        if not cls._is_active_authenticated_user(user):
            return False

        if document.status != document.Status.VERIFIED:
            return False

        if not cls.can_view_document(user, document):
            return False

        return getattr(user, "role", None) in (
            cls.PRIVILEGED_ROLES | {"EMPLOYEE"}
        )

    @classmethod
    def can_manage_document(cls, user, document):
        """Check whether a user may manage a document's metadata."""
        if not cls._is_active_authenticated_user(user):
            return False

        role = getattr(user, "role", None)

        if role in cls.PRIVILEGED_ROLES:
            return True

        if role == "EMPLOYEE":
            return (
                document.employee.user_id == user.pk
                and document.status not in (
                    "VERIFIED",
                    "QUARANTINED",
                    "ARCHIVED",
                )
            )

        return False

    @classmethod
    def get_accessible_documents(cls, user):
        """Return a queryset limited to documents accessible by role."""
        from employees.models import HRDocument

        if not cls._is_active_authenticated_user(user):
            return HRDocument.objects.none()

        role = getattr(user, "role", None)

        if role in cls.PRIVILEGED_ROLES:
            return HRDocument.objects.all()

        if role == "HR_MANAGER":
            department_id = cls._get_manager_department_id(user)

            if not department_id:
                return HRDocument.objects.none()

            return HRDocument.objects.filter(
                employee__department_id=department_id
            ).exclude(
                confidentiality="RESTRICTED"
            )

        if role == "EMPLOYEE":
            return HRDocument.objects.filter(
                employee__user=user
            ).exclude(confidentiality="RESTRICTED")

        return HRDocument.objects.none()
