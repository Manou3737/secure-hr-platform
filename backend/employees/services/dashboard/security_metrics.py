
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from accounts.models import SecurityEvent


class SecurityMetricsService:
    """
    Provides SOC/SIEM metrics from recorded security events.

    When department_id is provided, only events associated
    with users belonging to that department are included.
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
            raise ValueError("recent_limit must be greater than or equal to 1.")

        events = SecurityEvent.objects.all()

        if department_id is not None:
            events = events.filter(
                user__employee_profile__department_id=department_id
            )

        start_date = as_of - timedelta(days=days - 1)

        period_events = events.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=as_of,
        )

        event_counts = period_events.aggregate(
            total=Count("id"),
        )

        login_success = period_events.filter(
            event_type="LOGIN_SUCCESS"
        ).count()

        login_failed = period_events.filter(
            event_type="LOGIN_FAILED"
        ).count()

        brute_force = period_events.filter(
            event_type="BRUTE_FORCE_DETECTED"
        ).count()

        suspicious_ip = period_events.filter(
            event_type="SUSPICIOUS_IP_DETECTED"
        ).count()

        unauthorized_access = period_events.filter(
            event_type="UNAUTHORIZED_ACCESS"
        ).count()

        privilege_escalation = period_events.filter(
            event_type="PRIVILEGE_ESCALATION"
        ).count()

        event_distribution = list(
            period_events.values("event_type")
            .annotate(count=Count("id"))
            .order_by("event_type")
        )

        daily_activity = list(
            period_events.values("created_at__date")
            .annotate(count=Count("id"))
            .order_by("created_at__date")
        )

        source_metrics = period_events.aggregate(
            distinct_ips=Count("ip_address", distinct=True),
            distinct_users=Count("user_id", distinct=True),
        )

        recent_events = list(
            period_events.order_by("-created_at")
            .values(
                "id",
                "event_type",
                "ip_address",
                "request_path",
                "created_at",
            )[:recent_limit]
        )

        return {
            "as_of": as_of,
            "period_days": days,
            "overview": {
                "total_events": event_counts["total"],
                "login_success": login_success,
                "login_failed": login_failed,
            },
            "detections": {
                "brute_force": brute_force,
                "suspicious_ip": suspicious_ip,
                "unauthorized_access": unauthorized_access,
                "privilege_escalation": privilege_escalation,
            },
            "sources": source_metrics,
            "events": {
                "distribution": event_distribution,
            },
            "daily_activity": daily_activity,
            "recent_events": recent_events,
        }
