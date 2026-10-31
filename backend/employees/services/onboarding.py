
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from employees.models import (
    EmployeeProfile,
    OnboardingActivityTemplate,
    OnboardingJourney,
    OnboardingPhase,
    OnboardingTask,
    OnboardingTemplate,
)


class OnboardingService:
    """Business operations for onboarding templates and journeys."""

    @staticmethod
    @transaction.atomic
    def publish_template(template_id):
        """Validate and publish a draft onboarding template."""

        try:
            template = (
                OnboardingTemplate.objects
                .select_for_update()
                .get(pk=template_id)
            )
        except OnboardingTemplate.DoesNotExist:
            raise ValidationError(
                {"template": "The onboarding template does not exist."}
            )

        if template.status != OnboardingTemplate.Status.DRAFT:
            raise ValidationError(
                {"status": "Only draft templates can be published."}
            )

        phases = list(
            OnboardingPhase.objects
            .select_for_update()
            .filter(template=template)
            .order_by("order")
        )

        if not template.name.strip():
            raise ValidationError(
                {"name": "The template name cannot be empty."}
            )

        if not phases:
            raise ValidationError(
                {"phases": "Add at least one phase before publishing."}
            )

        for phase in phases:
            if not phase.name.strip():
                raise ValidationError(
                    {"phases": f"Phase {phase.pk} must have a name."}
                )

            has_activities = OnboardingActivityTemplate.objects.filter(
                phase=phase
            ).exists()

            if not has_activities:
                raise ValidationError(
                    {
                        "phases": (
                            f"Phase '{phase.name}' must contain "
                            "at least one activity."
                        )
                    }
                )

        template.status = OnboardingTemplate.Status.PUBLISHED
        template.published_at = timezone.now()
        template.save(update_fields=["status", "published_at", "updated_at"])

        return template

    @staticmethod
    @transaction.atomic
    def create_journey(
        *,
        employee_id,
        template_id,
        created_by,
        target_completion_date=None,
    ):
        """Create an employee journey from a published template."""

        try:
            template = (
                OnboardingTemplate.objects
                .select_for_update()
                .get(pk=template_id)
            )
        except OnboardingTemplate.DoesNotExist:
            raise ValidationError(
                {"template": "The onboarding template does not exist."}
            )

        if (
            template.status != OnboardingTemplate.Status.PUBLISHED
            or template.published_at is None
        ):
            raise ValidationError(
                {"template": "Only published templates can be used."}
            )

        try:
            employee = (
                EmployeeProfile.objects
                .select_related("user")
                .get(pk=employee_id)
            )
        except EmployeeProfile.DoesNotExist:
            raise ValidationError(
                {"employee": "The employee profile does not exist."}
            )

        if not employee.user.is_active:
            raise ValidationError(
                {"employee": "An inactive employee cannot start onboarding."}
            )

        active_journey_exists = OnboardingJourney.objects.filter(
            employee=employee,
            template=template,
        ).exclude(
            status__in=[
                OnboardingJourney.Status.COMPLETED,
                OnboardingJourney.Status.CANCELLED,
            ]
        ).exists()

        if active_journey_exists:
            raise ValidationError(
                {
                    "journey": (
                        "An active onboarding journey already exists "
                        "for this employee and template."
                    )
                }
            )

        if (
            not getattr(created_by, "is_authenticated", False)
            or not getattr(created_by, "is_active", False)
            or not getattr(created_by, "pk", None)
        ):
            raise ValidationError(
                {"created_by": "An active authenticated user is required."}
            )

        activities = list(
            OnboardingActivityTemplate.objects
            .filter(phase__template=template)
            .select_related("phase")
            .order_by("phase__order", "order")
        )

        if not activities:
            raise ValidationError(
                {"template": "The published template has no activities."}
            )

        journey = OnboardingJourney.objects.create(
            employee=employee,
            template=template,
            template_version=template.version,
            created_by=created_by,
            target_completion_date=target_completion_date,
        )

        today = timezone.localdate()
        tasks = []

        for activity in activities:
            due_date = None

            if activity.default_due_days is not None:
                due_date = today + timedelta(
                    days=activity.default_due_days
                )

            tasks.append(
                OnboardingTask(
                    journey=journey,
                    activity_template=activity,
                    title=activity.name,
                    description=activity.description,
                    due_date=due_date,
                )
            )

        OnboardingTask.objects.bulk_create(tasks)

        return journey
