
import logging
from datetime import timedelta

from django.utils import timezone

from employees.models import HRDocument, NotificationJob, OnboardingTask

logger = logging.getLogger(__name__)


class OnboardingNotificationService:
    """Queue onboarding notifications without sending emails directly."""

    @staticmethod
    def _enqueue_notification(
        *,
        notification_type,
        idempotency_key,
        task,
        recipient,
    ):
        """Create an idempotent notification job."""

        if (
            not recipient
            or not recipient.is_active
            or not recipient.email
        ):
            return False

        job, created = NotificationJob.objects.get_or_create(
            idempotency_key=idempotency_key,
            defaults={
                "notification_type": notification_type,
                "payload": {
                    "task_id": str(task.pk),
                    "recipient_user_id": str(recipient.pk),
                },
            },
        )

        if not created:
            logger.info(
                "Notification job already exists. "
                "notification_type=%s task_id=%s job_id=%s",
                notification_type,
                task.pk,
                job.pk,
            )

        return True

    @classmethod
    def notify_task_assigned(cls, *, task_id):
        """Queue a notification for the assigned employee."""

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

        idempotency_key = (
            f"TASK_ASSIGNED:{task.pk}:"
            f"{recipient.pk}:{task.updated_at.isoformat()}"
        )

        return cls._enqueue_notification(
            notification_type=NotificationJob.NotificationType.TASK_ASSIGNED,
            idempotency_key=idempotency_key,
            task=task,
            recipient=recipient,
        )

    @classmethod
    def notify_task_completed(cls, *, task_id):
        """Queue a notification for the journey creator."""

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

        return cls._enqueue_notification(
            notification_type=NotificationJob.NotificationType.TASK_COMPLETED,
            idempotency_key=f"TASK_COMPLETED:{task.pk}",
            task=task,
            recipient=recipient,
        )

    @classmethod
    def enqueue_overdue_task_notifications(cls):
        """Queue notifications for currently overdue onboarding tasks."""

        today = timezone.localdate()

        tasks = (
            OnboardingTask.objects
            .select_related("assigned_to")
            .filter(
                due_date__lt=today,
                assigned_to__is_active=True,
                assigned_to__email__gt="",
            )
            .exclude(
                status__in=[
                    OnboardingTask.Status.COMPLETED,
                    OnboardingTask.Status.CANCELLED,
                ]
            )
        )

        created_count = 0

        for task in tasks.iterator():
            key = (
                f"TASK_OVERDUE:{task.pk}:"
                f"{task.due_date.isoformat()}:"
                f"{task.assigned_to_id}"
            )

            _, created = NotificationJob.objects.get_or_create(
                idempotency_key=key,
                defaults={
                    "notification_type": (
                        NotificationJob.NotificationType.TASK_OVERDUE
                    ),
                    "payload": {
                        "task_id": str(task.pk),
                        "recipient_user_id": str(task.assigned_to_id),
                    },
                },
            )

            if created:
                created_count += 1

        return created_count

    @classmethod
    def enqueue_expiring_document_notifications(cls):
        """Queue notifications for verified documents expiring soon."""

        today = timezone.localdate()
        expiration_limit = today + timedelta(days=30)

        documents = (
            HRDocument.objects
            .select_related("employee__user")
            .filter(
                status=HRDocument.Status.VERIFIED,
                expires_at__gt=today,
                expires_at__lte=expiration_limit,
                employee__user__is_active=True,
                employee__user__email__gt="",
            )
        )

        created_count = 0

        for document in documents.iterator():
            recipient = document.employee.user
            key = (
                f"DOCUMENT_EXPIRING:{document.pk}:"
                f"{document.expires_at.isoformat()}"
            )

            _, created = NotificationJob.objects.get_or_create(
                idempotency_key=key,
                defaults={
                    "notification_type": (
                        NotificationJob.NotificationType.DOCUMENT_EXPIRING
                    ),
                    "payload": {
                        "document_id": str(document.pk),
                        "recipient_user_id": str(recipient.pk),
                    },
                },
            )

            if created:
                created_count += 1

        return created_count
