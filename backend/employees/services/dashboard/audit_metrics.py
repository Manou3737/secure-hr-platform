
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from accounts.models import AuditLog
from employees.models import DocumentAccessLog, WorkflowExecutionLog


class AuditMetricsService:
    """
    Consolidates audit metrics from general, document-access,
    and onboarding workflow audit logs.

    When department_id is provided, all metrics are restricted
    to records associated with that department.
    """

    @classmethod
    def get_dashboard(
        cls,
        *,
        department_id=None,
        as_of=None,
        days=7,
        recent_limit=10,
    ):
        as_of = as_of or timezone.localdate()

        if days < 1:
            raise ValueError("days must be greater than or equal to 1.")

        if recent_limit < 1:
            raise ValueError(
                "recent_limit must be greater than or equal to 1."
            )

        start_date = as_of - timedelta(days=days - 1)

        audit_logs = AuditLog.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=as_of,
        )

        document_logs = DocumentAccessLog.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=as_of,
        )

        workflow_logs = WorkflowExecutionLog.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=as_of,
        )

        # Apply department-level filtering before aggregation.
        if department_id is not None:
            audit_logs = audit_logs.filter(
                user__employee_profile__department_id=department_id
            )

            document_logs = document_logs.filter(
                document__employee__department_id=department_id
            )

            workflow_logs = workflow_logs.filter(
                journey__employee__department_id=department_id
            )

        audit_distribution = list(
            audit_logs.values("action")
            .annotate(count=Count("id"))
            .order_by("action")
        )

        document_distribution = list(
            document_logs.values("action")
            .annotate(count=Count("id"))
            .order_by("action")
        )

        workflow_distribution = list(
            workflow_logs.values("event_type")
            .annotate(count=Count("id"))
            .order_by("event_type")
        )

        workflow_outcomes = {
            item["outcome"]: item["count"]
            for item in (
                workflow_logs.values("outcome")
                .annotate(count=Count("id"))
                .order_by("outcome")
            )
        }

        daily_activity = {
            "general_audit": list(
                audit_logs.values("created_at__date")
                .annotate(count=Count("id"))
                .order_by("created_at__date")
            ),
            "document_access": list(
                document_logs.values("created_at__date")
                .annotate(count=Count("id"))
                .order_by("created_at__date")
            ),
            "workflow": list(
                workflow_logs.values("created_at__date")
                .annotate(count=Count("id"))
                .order_by("created_at__date")
            ),
        }

        recent_events = {
            "general_audit": list(
                audit_logs.order_by("-created_at").values(
                    "id",
                    "action",
                    "user_id",
                    "created_at",
                )[:recent_limit]
            ),
            "document_access": list(
                document_logs.order_by("-created_at").values(
                    "id",
                    "action",
                    "user_id",
                    "document_id",
                    "created_at",
                )[:recent_limit]
            ),
            "workflow": list(
                workflow_logs.order_by("-created_at").values(
                    "id",
                    "event_type",
                    "outcome",
                    "actor_id",
                    "created_at",
                )[:recent_limit]
            ),
        }

        general_total = audit_logs.count()
        document_total = document_logs.count()
        workflow_total = workflow_logs.count()

        return {
            "as_of": as_of,
            "period_days": days,
            "overview": {
                "total_entries": (
                    general_total + document_total + workflow_total
                ),
                "general_audit_entries": general_total,
                "document_access_entries": document_total,
                "workflow_entries": workflow_total,
            },
            "general_audit": {
                "distribution": audit_distribution,
            },
            "document_access": {
                "distribution": document_distribution,
                "access_denied": document_logs.filter(
                    action=DocumentAccessLog.Action.ACCESS_DENIED
                ).count(),
            },
            "workflows": {
                "distribution": workflow_distribution,
                "outcomes": workflow_outcomes,
            },
            "daily_activity": daily_activity,
            "recent_events": recent_events,
        }
