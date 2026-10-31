
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

from employees.models import OnboardingTask, WorkflowExecutionLog

logger = logging.getLogger(__name__)


class OnboardingNotificationService:
    """Send onboarding task notifications without exposing HR data."""

    @staticmethod
    def _send_notification(*, recipient, subject, message, task, event_type):
        """Send a minimal email and log delivery failures safely."""

        if not recipient or not recipient.is_active or not recipient.email:
            return False

        def send():
            try:
                sent_count = send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recipient.email],
                    fail_silently=False,
                )
                if sent_count != 1:
                    raise RuntimeError("Email backend did not confirm delivery.")

            except Exception:
                logger.exception(
                    "Onboarding notification failed. "
                    "event_type=%s task_id=%s recipient_id=%s",
                    event_type,
                    task.pk,
                    recipient.pk,
                )
                try:
                    WorkflowExecutionLog.objects.create(
                        journey=task.journey,
                        task=task,
                        event_type="NOTIFICATION_FAILED",
                        outcome=WorkflowExecutionLog.Outcome.FAILURE,
                        details={"notification_type": event_type},
                    )
                except Exception:
                    logger.exception(
                        "Could not record onboarding notification failure. "
                        "task_id=%s",
                        task.pk,
                    )

        transaction.on_commit(send)
        return True

    @classmethod
    def notify_task_assigned(cls, *, task_id):
        """Notify the assignee after a task assignment is committed."""

        try:
            task = (
                OnboardingTask.objects
                .select_related("assigned_to", "journey")
                .get(pk=task_id)
            )
        except OnboardingTask.DoesNotExist:
            return False

        recipient = task.assigned_to
        if recipient is None:
            return False

        return cls._send_notification(
            recipient=recipient,
            subject="An onboarding task has been assigned to you",
            message=(
                "A new onboarding task has been assigned to you. "
                "Please sign in to the secure HR platform to review it."
            ),
            task=task,
            event_type="TASK_ASSIGNED",
        )

    @classmethod
    def notify_task_completed(cls, *, task_id):
        """Notify the journey creator when a task is completed."""

        try:
            task = (
                OnboardingTask.objects
                .select_related("journey__created_by", "journey")
                .get(pk=task_id)
            )
        except OnboardingTask.DoesNotExist:
            return False

        if task.status != OnboardingTask.Status.COMPLETED:
            return False

        recipient = task.journey.created_by

        return cls._send_notification(
            recipient=recipient,
            subject="An onboarding task has been completed",
            message=(
                "An onboarding task in a journey you created has been "
                "completed. Please sign in to the secure HR platform "
                "to review the current status."
            ),
            task=task,
            event_type="TASK_COMPLETED",
        )
