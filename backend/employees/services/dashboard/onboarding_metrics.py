
from django.db.models import Count, Q
from django.utils import timezone

from employees.models import OnboardingJourney, OnboardingTask


class OnboardingMetricsService:
    """
    Provides onboarding metrics for the HR dashboard.

    Task workload metrics exclude completed and cancelled journeys.
    Cancelled tasks are excluded from progress calculations.
    """

    @classmethod
    def get_dashboard(cls, *, department_id=None, as_of=None):
        as_of = as_of or timezone.localdate()

        journey_queryset = OnboardingJourney.objects.all()

        if department_id is not None:
            journey_queryset = journey_queryset.filter(
                employee__department_id=department_id
            )

        journey_metrics = journey_queryset.aggregate(
            total=Count("id"),
            pending=Count(
                "id",
                filter=Q(status=OnboardingJourney.Status.PENDING),
            ),
            in_progress=Count(
                "id",
                filter=Q(status=OnboardingJourney.Status.IN_PROGRESS),
            ),
            suspended=Count(
                "id",
                filter=Q(status=OnboardingJourney.Status.SUSPENDED),
            ),
            completed=Count(
                "id",
                filter=Q(status=OnboardingJourney.Status.COMPLETED),
            ),
            cancelled=Count(
                "id",
                filter=Q(status=OnboardingJourney.Status.CANCELLED),
            ),
        )

        active_journeys = journey_queryset.exclude(
            status__in=[
                OnboardingJourney.Status.COMPLETED,
                OnboardingJourney.Status.CANCELLED,
            ]
        )

        task_queryset = OnboardingTask.objects.filter(
            journey__in=active_journeys
        )

        task_metrics = task_queryset.aggregate(
            total=Count("id"),
            pending=Count(
                "id",
                filter=Q(status=OnboardingTask.Status.PENDING),
            ),
            in_progress=Count(
                "id",
                filter=Q(status=OnboardingTask.Status.IN_PROGRESS),
            ),
            blocked=Count(
                "id",
                filter=Q(status=OnboardingTask.Status.BLOCKED),
            ),
            completed=Count(
                "id",
                filter=Q(status=OnboardingTask.Status.COMPLETED),
            ),
            cancelled=Count(
                "id",
                filter=Q(status=OnboardingTask.Status.CANCELLED),
            ),
            overdue=Count(
                "id",
                filter=(
                    Q(due_date__lt=as_of)
                    & ~Q(status__in=[
                        OnboardingTask.Status.COMPLETED,
                        OnboardingTask.Status.CANCELLED,
                    ])
                ),
            ),
            low_priority=Count(
                "id",
                filter=Q(priority=OnboardingTask.Priority.LOW),
            ),
            medium_priority=Count(
                "id",
                filter=Q(priority=OnboardingTask.Priority.MEDIUM),
            ),
            high_priority=Count(
                "id",
                filter=Q(priority=OnboardingTask.Priority.HIGH),
            ),
            urgent_priority=Count(
                "id",
                filter=Q(priority=OnboardingTask.Priority.URGENT),
            ),
        )

        progress_total = (
            task_metrics["total"] - task_metrics["cancelled"]
        )

        progress_percentage = (
            round(
                task_metrics["completed"] / progress_total * 100,
                1,
            )
            if progress_total
            else 0.0
        )

        return {
            "journeys": journey_metrics,
            "tasks": task_metrics,
            "progress": {
                "total_eligible_tasks": progress_total,
                "completed_tasks": task_metrics["completed"],
                "percentage": progress_percentage,
            },
            "as_of": as_of,
        }
