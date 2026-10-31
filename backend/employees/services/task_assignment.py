from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from employees.models import (
    EmployeeProfile,
    OnboardingTask,
    WorkflowExecutionLog,
)
from employees.services.onboarding_notifications import (
    OnboardingNotificationService,
)
User = get_user_model()

ASSIGNMENT_ROLES = {
    "SUPER_ADMIN",
    "HR_ADMIN",
    "HR_MANAGER",
}


class TaskAssignmentService:
    """Business operations for assigning onboarding tasks."""

    @staticmethod
    @transaction.atomic
    def assign_task(*, task_id, assigned_to_id, actor):
        """Assign or reassign an onboarding task with authorization and audit."""

        if not actor or not actor.is_authenticated:
            raise ValidationError(
                {"actor": "An authenticated actor is required."}
            )

        if not actor.is_active or actor.role not in ASSIGNMENT_ROLES:
            raise ValidationError(
                {"actor": "You are not authorized to assign onboarding tasks."}
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

        if task.status in (
            OnboardingTask.Status.COMPLETED,
            OnboardingTask.Status.CANCELLED,
        ):
            raise ValidationError(
                {
                    "status": (
                        "Completed or cancelled tasks cannot be assigned."
                    )
                }
            )

        if assigned_to_id is None:
            raise ValidationError(
                {"assigned_to": "An assignee is required."}
            )

        try:
            assignee = (
                User.objects
                .select_for_update()
                .get(pk=assigned_to_id)
            )
        except User.DoesNotExist:
            raise ValidationError(
                {"assigned_to": "The assignee does not exist."}
            )

        if not assignee.is_active:
            raise ValidationError(
                {"assigned_to": "An inactive user cannot be assigned."}
            )

        if not EmployeeProfile.objects.filter(user=assignee).exists():
            raise ValidationError(
                {
                    "assigned_to": (
                        "Only users with an employee profile "
                        "can be assigned onboarding tasks."
                    )
                }
            )

        previous_assignee_id = task.assigned_to_id

        if previous_assignee_id == assignee.pk:
            return task

        task.assigned_to = assignee
        task.save(update_fields=["assigned_to", "updated_at"])

        event_type = (
            "TASK_REASSIGNED"
            if previous_assignee_id is not None
            else "TASK_ASSIGNED"
        )

        WorkflowExecutionLog.objects.create(
            journey=task.journey,
            task=task,
            actor=actor,
            event_type=event_type,
            outcome=WorkflowExecutionLog.Outcome.SUCCESS,
            details={
                "previous_assignee_id": (
                    str(previous_assignee_id)
                    if previous_assignee_id is not None
                    else None
                ),
                "new_assignee_id": str(assignee.pk),
            },
        )
        OnboardingNotificationService.notify_task_assigned(
            task_id=task.pk,
        )
        return task
