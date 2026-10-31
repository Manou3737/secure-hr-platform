
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

    @classmethod
    def can_view_document(cls, user, document):
        """Check whether a user may view document metadata."""
        if not cls._is_active_authenticated_user(user):
            return False

        role = getattr(user, "role", None)
        confidentiality = getattr(document, "confidentiality", None)

        if role in cls.PRIVILEGED_ROLES:
            return True

        if confidentiality == "RESTRICTED":
            return False

        if role == "HR_MANAGER":
            return True

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
            return HRDocument.objects.exclude(
                confidentiality="RESTRICTED"
            )

        if role == "EMPLOYEE":
            return HRDocument.objects.filter(
                employee__user=user
            ).exclude(confidentiality="RESTRICTED")

        return HRDocument.objects.none()
