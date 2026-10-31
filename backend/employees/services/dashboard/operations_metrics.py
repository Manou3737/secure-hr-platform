
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from employees.models import WorkflowExecutionLog


class OperationsMetricsService:
    """
    Provides workflow and notification metrics for the HR dashboard.

    Metrics are based on recorded WorkflowExecutionLog entries.
    """

    @classmethod
    def get_dashboard(cls, *, department_id=None, as_of=None, days=7):
        as_of = as_of or timezone.localdate()

        if days < 1:
            raise ValueError("days must be greater than or equal to 1.")

        logs = WorkflowExecutionLog.objects.all()

        if department_id is not None:
            logs = logs.filter(
                journey__employee__department_id=department_id
            )

        workflow_metrics = logs.aggregate(
            total=Count("id"),
            success=Count(
                "id",
                filter=Q(
                    outcome=WorkflowExecutionLog.Outcome.SUCCESS
                ),
            ),
            failure=Count(
                "id",
                filter=Q(
                    outcome=WorkflowExecutionLog.Outcome.FAILURE
                ),
            ),
            denied=Count(
                "id",
                filter=Q(
                    outcome=WorkflowExecutionLog.Outcome.DENIED
                ),
            ),
        )

        notification_logs = logs.filter(
            event_type="NOTIFICATION_FAILED"
        )

        notification_metrics = {
            "failed": notification_logs.count(),
            "by_type": list(
                notification_logs.values(
                    "details__notification_type"
                )
                .annotate(count=Count("id"))
                .order_by("details__notification_type")
            ),
        }

        event_distribution = list(
            logs.values("event_type")
            .annotate(count=Count("id"))
            .order_by("event_type")
        )

        start_date = as_of - timedelta(days=days - 1)

        daily_activity = list(
            logs.filter(
                created_at__date__gte=start_date,
                created_at__date__lte=as_of,
            )
            .values("created_at__date")
            .annotate(count=Count("id"))
            .order_by("created_at__date")
        )

        return {
            "as_of": as_of,
            "period_days": days,
            "workflows": workflow_metrics,
            "notifications": notification_metrics,
            "events": {
                "distribution": event_distribution,
            },
            "daily_activity": daily_activity,
        }
