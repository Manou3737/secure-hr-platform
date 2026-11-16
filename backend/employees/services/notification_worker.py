import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from employees.models import (
    HRDocument,
    NotificationJob,
    OnboardingTask,
    WorkflowExecutionLog,
)

logger = logging.getLogger(__name__)


class NotificationWorker:
    """Process queued notification jobs safely."""

    @classmethod
    def process_batch(cls, *, batch_size=50):
        """Process a limited number of available jobs."""

        if batch_size < 1:
            raise ValueError("batch_size must be positive.")

        results = []

        for _ in range(batch_size):
            job = cls._claim_next_job()

            if job is None:
                break

            try:
                cls._deliver(job)
                cls._mark_success(job)
                results.append("SUCCESS")
            except Exception as exc:
                terminal = cls._handle_failure(job, exc)

                results.append(
                    "FAILED" if terminal else "RETRY_SCHEDULED"
                )

        return {
            "processed": len(results),
            "results": results,
        }

    @staticmethod
    def _claim_next_job():
        """Recover stale jobs, then claim one pending job."""

        now = timezone.now()
        stale_before = now - timedelta(minutes=10)

        with transaction.atomic():
            stale_job = (
                NotificationJob.objects
                .select_for_update(skip_locked=True)
                .filter(
                    status=NotificationJob.Status.PROCESSING,
                    updated_at__lt=stale_before,
                )
                .order_by("updated_at")
                .first()
            )

            if stale_job is not None:
                if stale_job.attempts >= stale_job.max_attempts:
                    stale_job.status = NotificationJob.Status.FAILED
                    stale_job.last_error = "Worker lease expired"

                    task_id = stale_job.payload.get("task_id")
                    task = (
                        OnboardingTask.objects
                        .select_related("journey")
                        .filter(pk=task_id)
                        .first()
                        if task_id
                        else None
                    )

                    WorkflowExecutionLog.objects.create(
                        task=task,
                        journey=task.journey if task else None,
                        actor=None,
                        event_type="NOTIFICATION_FAILED",
                        outcome=WorkflowExecutionLog.Outcome.FAILURE,
                        details={
                            "notification_type": (
                                stale_job.notification_type
                            ),
                            "reason": "WORKER_LEASE_EXPIRED",
                        },
                        correlation_id=stale_job.correlation_id,
                    )
                else:
                    stale_job.status = NotificationJob.Status.PENDING
                    stale_job.next_attempt_at = now
                    stale_job.last_error = "Worker lease expired"

                stale_job.save(update_fields=[
                    "status",
                    "next_attempt_at",
                    "last_error",
                    "updated_at",
                ])

            job = (
                NotificationJob.objects
                .select_for_update(skip_locked=True)
                .filter(
                    status=NotificationJob.Status.PENDING,
                    next_attempt_at__lte=now,
                )
                .order_by("created_at")
                .first()
            )

            if job is None:
                return None

            job.status = NotificationJob.Status.PROCESSING
            job.attempts += 1
            job.save(update_fields=[
                "status",
                "attempts",
                "updated_at",
            ])

            return job


    @classmethod
    def _deliver(cls, job):
        """Validate the current state before sending an email."""

        User = get_user_model()

        recipient_id = job.payload.get("recipient_user_id")

        if not recipient_id:
            return

        recipient = User.objects.filter(
            pk=recipient_id,
            is_active=True,
        ).first()

        if recipient is None or not recipient.email:
            return

        notification_type = job.notification_type
        today = timezone.localdate()

        subject = "Secure HR Platform notification"
        message = "You have a new notification in Secure HR Platform."

        if notification_type in (
            NotificationJob.NotificationType.TASK_ASSIGNED,
            NotificationJob.NotificationType.TASK_OVERDUE,
            NotificationJob.NotificationType.TASK_COMPLETED,
        ):
            task = (
                OnboardingTask.objects
                .select_related("journey")
                .filter(pk=job.payload.get("task_id"))
                .first()
            )

            if task is None:
                return

            if notification_type == (
                NotificationJob.NotificationType.TASK_ASSIGNED
            ):
                if task.assigned_to_id != recipient.pk:
                    return

                subject = "An onboarding task was assigned to you"
                message = (
                    "An onboarding task has been assigned to you. "
                    "Please sign in to Secure HR Platform to review it."
                )

            elif notification_type == (
                NotificationJob.NotificationType.TASK_COMPLETED
            ):
                if (
                    task.status != OnboardingTask.Status.COMPLETED
                    or task.journey.created_by_id != recipient.pk
                ):
                    return

                subject = "An onboarding task was completed"
                message = (
                    "An onboarding task has been completed. "
                    "Please sign in to Secure HR Platform to review it."
                )

            elif notification_type == (
                NotificationJob.NotificationType.TASK_OVERDUE
            ):
                if (
                    task.assigned_to_id != recipient.pk
                    or task.due_date is None
                    or task.due_date >= today
                    or task.status in (
                        OnboardingTask.Status.COMPLETED,
                        OnboardingTask.Status.CANCELLED,
                    )
                ):
                    return

                subject = "An onboarding task is overdue"
                message = (
                    "An onboarding task assigned to you is overdue. "
                    "Please sign in to Secure HR Platform to review it."
                )

        elif notification_type == (
            NotificationJob.NotificationType.DOCUMENT_EXPIRING
        ):
            document = (
                HRDocument.objects
                .select_related("employee__user")
                .filter(pk=job.payload.get("document_id"))
                .first()
            )

            if document is None:
                return

            if (
                document.employee.user_id != recipient.pk
                or document.status != HRDocument.Status.VERIFIED
                or document.expires_at is None
                or not (
                    today < document.expires_at
                    <= today + timedelta(days=30)
                )
            ):
                return

            subject = "An HR document is approaching expiration"
            message = (
                "One of your HR documents is approaching its expiration "
                "date. Please sign in to Secure HR Platform to review it."
            )

        else:
            raise ValueError("Unsupported notification type.")

        sent = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient.email],
            fail_silently=False,
        )

        if sent != 1:
            raise RuntimeError("Email backend did not confirm delivery.")

    @staticmethod
    def _mark_success(job):
        """Mark a processed job as successful."""

        NotificationJob.objects.filter(
            pk=job.pk,
            status=NotificationJob.Status.PROCESSING,
        ).update(
            status=NotificationJob.Status.SUCCESS,
            last_error="",
            updated_at=timezone.now(),
        )

    @staticmethod
    def _handle_failure(job, exc):
        """Schedule a retry or record a terminal failure."""

        now = timezone.now()

        with transaction.atomic():
            locked_job = NotificationJob.objects.select_for_update().get(
                pk=job.pk,
            )

            terminal = (
                locked_job.attempts >= locked_job.max_attempts
            )
            locked_job.last_error = type(exc).__name__

            if terminal:
                locked_job.status = NotificationJob.Status.FAILED
            else:
                delay_seconds = min(
                    60 * (2 ** (locked_job.attempts - 1)),
                    3600,
                )
                locked_job.status = NotificationJob.Status.PENDING
                locked_job.next_attempt_at = (
                    now + timedelta(seconds=delay_seconds)
                )

            locked_job.save(update_fields=[
                "status",
                "last_error",
                "next_attempt_at",
                "updated_at",
            ])

            if terminal:
                task_id = locked_job.payload.get("task_id")
                task = (
                    OnboardingTask.objects
                    .select_related("journey")
                    .filter(pk=task_id)
                    .first()
                    if task_id
                    else None
                )

                WorkflowExecutionLog.objects.create(
                    task=task,
                    journey=task.journey if task else None,
                    actor=None,
                    event_type="NOTIFICATION_FAILED",
                    outcome=WorkflowExecutionLog.Outcome.FAILURE,
                    details={
                        "notification_type": locked_job.notification_type,
                    },
                    correlation_id=locked_job.correlation_id,
                )

        logger.warning(
            "Notification processing failed. "
            "job_id=%s notification_type=%s terminal=%s error_type=%s",
            locked_job.pk,
            locked_job.notification_type,
            terminal,
            type(exc).__name__,
        )
        return terminal
