
"""Django command to process HR documents reaching their retention deadline."""

from datetime import datetime, time, timedelta
from time import monotonic
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone

from employees.models import DocumentRetentionExecution
from employees.services.document_expiration import (
    DocumentExpirationService,
)


RETENTION_LOCK_ID = 726194002
RETENTION_TIMEZONE = ZoneInfo("America/New_York")


class Command(BaseCommand):
    help = (
        "Process HR documents whose retention deadlines have been reached. "
        "Use --dry-run to simulate actions without modifying documents. "
        "Use --scheduled for daily scheduler runs."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate retention actions without modifying documents.",
        )
        parser.add_argument(
            "--scheduled",
            action="store_true",
            help="Apply daily duplicate-run protection.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        scheduled = options["scheduled"]
        started_clock = monotonic()
        lock_acquired = False

        execution = DocumentRetentionExecution.objects.create(
            status=DocumentRetentionExecution.Status.RUNNING,
        )

        try:
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT pg_try_advisory_lock(%s)",
                        [RETENTION_LOCK_ID],
                    )
                    lock_acquired = cursor.fetchone()[0]

                if not lock_acquired:
                    self.finish_skipped(
                        execution,
                        started_clock,
                        "Another document retention run is already in progress.",
                    )
                    self.stdout.write(
                        self.style.WARNING(
                            "Skipped: another retention run is in progress."
                        )
                    )
                    self.stdout.write(f"Execution ID: {execution.pk}")
                    return

            # Check only after obtaining the PostgreSQL lock, avoiding a
            # race between two scheduled processes.
            if scheduled:
                local_now = timezone.localtime(
                    timezone.now(), RETENTION_TIMEZONE
                )
                local_date = local_now.date()

                day_start = datetime.combine(
                    local_date,
                    time.min,
                    tzinfo=RETENTION_TIMEZONE,
                )
                next_day_start = datetime.combine(
                    local_date + timedelta(days=1),
                    time.min,
                    tzinfo=RETENTION_TIMEZONE,
                )

                already_succeeded = (
                    DocumentRetentionExecution.objects.filter(
                        status=DocumentRetentionExecution.Status.SUCCESS,
                        started_at__gte=day_start,
                        started_at__lt=next_day_start,
                    )
                    .exclude(pk=execution.pk)
                    .exists()
                )

                if already_succeeded:
                    self.finish_skipped(
                        execution,
                        started_clock,
                        "A successful retention run already exists for "
                        f"{local_date.isoformat()} in America/New_York.",
                    )
                    self.stdout.write(
                        self.style.WARNING(
                            "Skipped: a successful retention run already "
                            "exists for today."
                        )
                    )
                    self.stdout.write(f"Execution ID: {execution.pk}")
                    return

            summary = DocumentExpirationService.process_expired_documents(
                dry_run=dry_run,
            )

            execution.status = (
                DocumentRetentionExecution.Status.DRY_RUN
                if dry_run
                else DocumentRetentionExecution.Status.SUCCESS
            )
            execution.processed_count = summary.get("processed", 0)
            execution.archived_count = summary.get("archived", 0)
            execution.would_archive_count = summary.get("would_archive", 0)
            execution.skipped_count = summary.get("skipped", 0)
            execution.finished_at = timezone.now()
            execution.duration_ms = max(
                0, int((monotonic() - started_clock) * 1000)
            )
            execution.save(
                update_fields=[
                    "status",
                    "finished_at",
                    "duration_ms",
                    "processed_count",
                    "archived_count",
                    "would_archive_count",
                    "skipped_count",
                ]
            )

        except Exception as exc:
            execution.status = DocumentRetentionExecution.Status.FAILURE
            execution.finished_at = timezone.now()
            execution.duration_ms = max(
                0, int((monotonic() - started_clock) * 1000)
            )
            execution.error_message = (
                f"{type(exc).__name__}: {str(exc)[:500]}"
            )
            execution.save(
                update_fields=[
                    "status",
                    "finished_at",
                    "duration_ms",
                    "error_message",
                ]
            )
            raise CommandError(
                "Document retention processing failed."
            ) from exc

        finally:
            if lock_acquired:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT pg_advisory_unlock(%s)",
                        [RETENTION_LOCK_ID],
                    )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN: no documents were modified."
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Document retention processing completed."
            )
        )
        self.stdout.write(f"Processed: {summary['processed']}")
        self.stdout.write(f"Archived: {summary['archived']}")
        self.stdout.write(
            f"Would archive: {summary.get('would_archive', 0)}"
        )
        self.stdout.write(f"Skipped: {summary['skipped']}")
        self.stdout.write(f"Execution ID: {execution.pk}")

    @staticmethod
    def finish_skipped(execution, started_clock, reason):
        execution.status = DocumentRetentionExecution.Status.SKIPPED
        execution.finished_at = timezone.now()
        execution.duration_ms = max(
            0, int((monotonic() - started_clock) * 1000)
        )
        execution.error_message = reason
        execution.save(
            update_fields=[
                "status",
                "finished_at",
                "duration_ms",
                "error_message",
            ]
        )
