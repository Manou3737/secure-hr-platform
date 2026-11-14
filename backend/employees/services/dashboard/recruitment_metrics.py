from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from recruitment.models import (
    ApplicationStatusHistory,
    JobApplication,
    JobPosting,
)


class RecruitmentMetricsService:
    """
    Provides aggregate recruitment metrics for the HR dashboard.

    Metrics are restricted to the requested department when
    department_id is provided.

    No candidate personal information is exposed.
    """

    @classmethod
    def get_dashboard(
        cls,
        *,
        department_id=None,
        as_of=None,
        days=7,
    ):
        as_of = as_of or timezone.localdate()

        if days < 1:
            raise ValueError(
                "days must be greater than or equal to 1."
            )

        start_date = as_of - timedelta(days=days - 1)

        job_postings = JobPosting.objects.all()
        applications = JobApplication.objects.all()

        if department_id is not None:
            job_postings = job_postings.filter(
                department_id=department_id
            )
            applications = applications.filter(
                job_posting__department_id=department_id
            )

        posting_counts = {
            item["status"]: item["count"]
            for item in (
                job_postings.values("status")
                .annotate(count=Count("id"))
                .order_by("status")
            )
        }

        application_counts = {
            item["status"]: item["count"]
            for item in (
                applications.values("status")
                .annotate(count=Count("id"))
                .order_by("status")
            )
        }

        period_applications = applications.filter(
            applied_at__date__gte=start_date,
            applied_at__date__lte=as_of,
        )

        daily_activity = list(
            period_applications.values("applied_at__date")
            .annotate(count=Count("id"))
            .order_by("applied_at__date")
        )

        hired_history = ApplicationStatusHistory.objects.filter(
            new_status=JobApplication.Status.HIRED,
            created_at__date__gte=start_date,
            created_at__date__lte=as_of,
        )

        if department_id is not None:
            hired_history = hired_history.filter(
                application__job_posting__department_id=department_id
            )

        return {
            "as_of": as_of,
            "period_days": days,
            "job_postings": {
                "total": job_postings.count(),
                "by_status": [
                    {
                        "status": status,
                        "count": posting_counts.get(status, 0),
                    }
                    for status, _ in JobPosting.Status.choices
                ],
            },
            "applications": {
                "total": applications.count(),
                "by_status": [
                    {
                        "status": status,
                        "count": application_counts.get(status, 0),
                    }
                    for status, _ in JobApplication.Status.choices
                ],
                "received_in_period": period_applications.count(),
                "hired_in_period": hired_history.count(),
            },
            "daily_activity": daily_activity,
        }
