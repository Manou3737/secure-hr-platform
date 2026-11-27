
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from employees.models import EmployeeProfile, HRDocument


class EmployeeComplianceService:
    """Aggregate employee-record and HR-document compliance indicators."""

    REQUIRED_DOCUMENT_TYPES = {
        "IDENTITY_DOCUMENT",
        "EMPLOYMENT_CONTRACT",
        "TAX_FORM",
    }

    EXPIRING_WITHIN_DAYS = 30
    SUPPORTED_PERIODS = (7, 30, 60, 90)

    @classmethod
    def get_dashboard(
        cls,
        *,
        department_id=None,
        site_id=None,
        as_of=None,
        expiring_within_days=30,
        uploaded_within_days=None,
    ):
        """
        Return compliance counts and affected employee/document records.

        Only active employees are included. A required document is considered
        present when a verified, non-expired document of that type exists.
        """
        if expiring_within_days not in cls.SUPPORTED_PERIODS:
            raise ValueError("Unsupported expiration period.")

        if (
            uploaded_within_days is not None
            and uploaded_within_days not in cls.SUPPORTED_PERIODS
        ):
            raise ValueError("Unsupported upload period.")

        today = as_of or timezone.localdate()

        employees = (
            EmployeeProfile.objects
            .filter(user__is_active=True)
            .select_related("user", "department", "position")
        )

        if department_id is not None:
            employees = employees.filter(department_id=department_id)

        if site_id is not None:
            employees = employees.filter(site_id=site_id)

        employee_ids = list(employees.values_list("pk", flat=True))

        documents = HRDocument.objects.filter(
            employee_id__in=employee_ids,
        )

        verified_documents = documents.filter(
            status=HRDocument.Status.VERIFIED,
        )

        expired_documents = verified_documents.filter(
            expires_at__lt=today,
        ).select_related("employee", "employee__user")

        soon_expiring_documents = verified_documents.filter(
            expires_at__gte=today,
            expires_at__lte=today + timedelta(
                days=expiring_within_days
            ),
        ).select_related("employee", "employee__user")

        incomplete_profiles = employees.filter(
            Q(employee_id="")
            | Q(phone="")
            | Q(address="")
        ).distinct()

        missing_documents = []

        for employee in employees:
            employee_verified_types = set(
                verified_documents.filter(
                    Q(expires_at__isnull=True) | Q(expires_at__gte=today),
                    employee_id=employee.pk,
                ).values_list("document_type", flat=True)
            )

            missing_types = sorted(
                cls.REQUIRED_DOCUMENT_TYPES - employee_verified_types
            )

            if missing_types:
                missing_documents.append({
                    "employee_id": str(employee.pk),
                    "employee_name": employee.user.name,
                    "missing_document_types": missing_types,
                })

        recently_uploaded_documents = []
        if uploaded_within_days is not None:
            upload_start = (
                today - timedelta(days=uploaded_within_days - 1)
            )

            recent_uploads = documents.filter(
                uploaded_at__date__gte=upload_start,
                uploaded_at__date__lte=today,
            ).select_related(
                "employee",
                "employee__user",
            ).order_by("-uploaded_at")

            recently_uploaded_documents = list(
                recent_uploads.values(
                    "id",
                    "employee_id",
                    "employee__user__name",
                    "document_type",
                    "status",
                    "uploaded_at",
                )
            )

        return {
            "as_of": today,
            "headcount": employees.count(),
            "incomplete_profile_count": incomplete_profiles.count(),
            "incomplete_profiles": list(
                incomplete_profiles.values(
                    "id",
                    "employee_id",
                    "user__name",
                    "department__name",
                    "position__title",
                )
            ),
            "employees_missing_required_documents_count": len(
                missing_documents
            ),
            "employees_missing_required_documents": missing_documents,
            "expired_document_count": expired_documents.count(),
            "expired_documents": list(
                expired_documents.values(
                    "id",
                    "employee_id",
                    "employee__user__name",
                    "document_type",
                    "expires_at",
                )
            ),
            "documents_expiring_soon_count": soon_expiring_documents.count(),
            "documents_expiring_soon": list(
                soon_expiring_documents.values(
                    "id",
                    "employee_id",
                    "employee__user__name",
                    "document_type",
                    "expires_at",
                )
            ),
            "recently_uploaded_document_count": len(
                recently_uploaded_documents
            ),
            "recently_uploaded_documents": recently_uploaded_documents,
        }
