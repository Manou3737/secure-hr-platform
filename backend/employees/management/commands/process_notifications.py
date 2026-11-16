"""Django command to process queued HR notifications."""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from employees.services.notification_worker import NotificationWorker
from employees.services.onboarding_notifications import (
    OnboardingNotificationService,
)


NOTIFICATION_LOCK_ID = 726194003


class Command(BaseCommand):
    help = "Process queued HR notifications."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Maximum number of notifications per batch.",
        )
        parser.add_argument(
            "--max-batches",
            type=int,
            default=10,
            help="Maximum number of batches per execution.",
        )
        parser.add_argument(
            "--enqueue-daily",
            action="store_true",
            help="Enqueue overdue task and expiring document notifications.",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        max_batches = options["max_batches"]

        if batch_size < 1:
            raise CommandError("--batch-size must be greater than zero.")

        if max_batches < 1:
            raise CommandError("--max-batches must be greater than zero.")

        lock_acquired = False

        try:
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT pg_try_advisory_lock(%s)",
                        [NOTIFICATION_LOCK_ID],
                    )
                    lock_acquired = cursor.fetchone()[0]

                if not lock_acquired:
                    self.stdout.write(
                        self.style.WARNING(
                            "Skipped: another notification run is in progress."
                        )
                    )
                    return

            overdue_created = 0
            expiring_created = 0

            if options["enqueue_daily"]:
                overdue_created = (
                    OnboardingNotificationService
                    .enqueue_overdue_task_notifications()
                )
                expiring_created = (
                    OnboardingNotificationService
                    .enqueue_expiring_document_notifications()
                )

                self.stdout.write(
                    "Daily notifications queued: "
                    f"overdue_tasks={overdue_created}, "
                    f"expiring_documents={expiring_created}"
                )

            total_processed = 0
            total_retries = 0
            total_failed = 0
            batches_processed = 0

            for _ in range(max_batches):
                summary = NotificationWorker.process_batch(
                    batch_size=batch_size,
                )

                processed = summary["processed"]
                results = summary["results"]

                total_processed += processed
                total_retries += results.count("RETRY_SCHEDULED")
                total_failed += results.count("FAILED")
                batches_processed += 1

                if processed < batch_size:
                    break

            self.stdout.write(
                self.style.SUCCESS(
                    "Notification processing completed: "
                    f"processed={total_processed}, "
                    f"retries_scheduled={total_retries}, "
                    f"failed={total_failed}, "
                    f"batches={batches_processed}"
                )
            )

        except Exception as exc:
            raise CommandError(
                "Notification processing failed."
            ) from exc

        finally:
            if lock_acquired:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT pg_advisory_unlock(%s)",
                        [NOTIFICATION_LOCK_ID],
                    )
