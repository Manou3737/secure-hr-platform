
from django.db.models import Count
from django.utils import timezone

from accounts.models import SecurityEvent
from employees.models import HRDocument
from employees.services.employee_compliance import (
    EmployeeComplianceService,
)


class RiskMetricsService:
    """
    Aggregates observable HR compliance, document lifecycle,
    and security risk indicators.

    No artificial risk score or severity classification is generated.
    """

    @classmethod
    def get_dashboard(cls, *, department_id=None, as_of=None):
        as_of = as_of or timezone.localdate()

        compliance = EmployeeComplianceService.get_dashboard(
            department_id=department_id,
            as_of=as_of,
        )

        documents = HRDocument.objects.all()

        if department_id is not None:
            documents = documents.filter(
                employee__department_id=department_id
            )

        document_statuses = {
            item["status"]: item["count"]
            for item in (
                documents.values("status")
                .annotate(count=Count("id"))
                .order_by("status")
            )
        }

        security_events = SecurityEvent.objects.all()
        if department_id is not None:
            security_events = security_events.filter(
                user__employee_profile__department_id=department_id
            )
        security_detections = {
            "brute_force": security_events.filter(
                event_type="BRUTE_FORCE_DETECTED"
            ).count(),
            "suspicious_ip": security_events.filter(
                event_type="SUSPICIOUS_IP_DETECTED"
            ).count(),
            "unauthorized_access": security_events.filter(
                event_type="UNAUTHORIZED_ACCESS"
            ).count(),
            "privilege_escalation": security_events.filter(
                event_type="PRIVILEGE_ESCALATION"
            ).count(),
        }

        compliance_risks = {
            "incomplete_profiles": compliance[
                "incomplete_profile_count"
            ],
            "employees_missing_required_documents": compliance[
                "employees_missing_required_documents_count"
            ],
            "expired_documents": compliance[
                "expired_document_count"
            ],
            "documents_expiring_soon": compliance[
                "documents_expiring_soon_count"
            ],
        }

        document_lifecycle = {
            "pending_scan": document_statuses.get("PENDING_SCAN", 0),
            "pending_review": document_statuses.get("PENDING_REVIEW", 0),
            "quarantined": document_statuses.get("QUARANTINED", 0),
            "rejected": document_statuses.get("REJECTED", 0),
            "verified": document_statuses.get("VERIFIED", 0),
            "archived": document_statuses.get("ARCHIVED", 0),
        }

        return {
            "as_of": as_of,
            "compliance": compliance_risks,
            "document_lifecycle": document_lifecycle,
            "security": security_detections,
        }
