
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from employees.models import (
    OnboardingTask,
    TaskDependency,
    WorkflowExecutionLog,
)
from employees.services.onboarding_notifications import (
    OnboardingNotificationService,
)

User = get_user_model()

WORKFLOW_ROLES = {
    "SUPER_ADMIN",
    "HR_ADMIN",
    "HR_MANAGER",
}


class WorkflowEngine:
    """Manage onboarding task transitions with authorization and audit."""

    ALLOWED_TRANSITIONS = {
        OnboardingTask.Status.PENDING: {
            OnboardingTask.Status.IN_PROGRESS,
            OnboardingTask.Status.CANCELLED,
        },
        OnboardingTask.Status.IN_PROGRESS: {
            OnboardingTask.Status.COMPLETED,
            OnboardingTask.Status.CANCELLED,
        },
        OnboardingTask.Status.BLOCKED: {
            OnboardingTask.Status.PENDING,
        },
    }

    @staticmethod
    @transaction.atomic
    def transition_task(*, task_id, target_status, actor):
        """Transition a task after validating authorization and dependencies."""

        if (
            not actor
            or not getattr(actor, "is_authenticated", False)
            or not getattr(actor, "pk", None)
        ):
            raise ValidationError(
                {"actor": "An authenticated actor is required."}
            )

        if not actor.is_active or actor.role not in WORKFLOW_ROLES:
            raise ValidationError(
                {"actor": "You are not authorized to change task status."}
            )

        valid_statuses = {
            value for value, _label in OnboardingTask.Status.choices
        }
        if target_status not in valid_statuses:
            raise ValidationError(
                {"target_status": "The requested task status is invalid."}
            )

        try:
            task = (
                OnboardingTask.objects
                .select_for_update()
                .select_related("journey")
                .get(pk=task_id)
            )
        except OnboardingTask.DoesNotExist:
            raise ValidationError(
                {"task": "The onboarding task does not exist."}
            )

        if target_status == task.status:
            raise ValidationError(
                {"status": "The task already has the requested status."}
            )

        allowed = WorkflowEngine.ALLOWED_TRANSITIONS.get(
            task.status, set()
        )
        if target_status not in allowed:
            raise ValidationError(
                {
                    "status": (
                        f"Transition from {task.status} to "
                        f"{target_status} is not allowed."
                    )
                }
            )

        if target_status in {
            OnboardingTask.Status.IN_PROGRESS,
            OnboardingTask.Status.COMPLETED,
        }:
            dependencies = TaskDependency.objects.filter(
                dependent_task=task
            ).select_related("prerequisite_task")

            incomplete_dependencies = [
                str(dependency.prerequisite_task_id)
                for dependency in dependencies
                if dependency.prerequisite_task.status
                != OnboardingTask.Status.COMPLETED
            ]

            if incomplete_dependencies:
                raise ValidationError(
                    {
                        "dependencies": (
                            "All prerequisite tasks must be completed "
                            "before this task can start or complete."
                        )
                    }
                )

        now = timezone.now()
        previous_status = task.status
        task.status = target_status
        update_fields = ["status", "updated_at"]

        if target_status == OnboardingTask.Status.IN_PROGRESS:
            task.started_at = now
            update_fields.append("started_at")

        if target_status == OnboardingTask.Status.COMPLETED:
            task.completed_at = now
            update_fields.append("completed_at")

        task.save(update_fields=update_fields)

        WorkflowExecutionLog.objects.create(
            journey=task.journey,
            task=task,
            actor=actor,
            event_type="TASK_STATUS_CHANGED",
            outcome=WorkflowExecutionLog.Outcome.SUCCESS,
            details={
                "previous_status": previous_status,
                "new_status": target_status,
            },
        )
        if target_status == OnboardingTask.Status.COMPLETED:
            OnboardingNotificationService.notify_task_completed(
                task_id=task.pk,
            )
        return task
