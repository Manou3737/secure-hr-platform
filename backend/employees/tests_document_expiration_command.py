
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import TestCase
from employees.models import DocumentRetentionExecution
from django.utils import timezone

class ProcessExpiredDocumentsCommandTests(TestCase):
    @patch(
        "employees.management.commands.process_expired_documents."
        "DocumentExpirationService.process_expired_documents"
    )
    def test_command_displays_processing_summary(self, process_documents):
        process_documents.return_value = {
            "processed": 4,
            "archived": 2,
            "would_archive": 0,
            "skipped": 2,
            "results": [],
        }
        output = StringIO()

        call_command("process_expired_documents", stdout=output)

        self.assertIn(
            "Document retention processing completed.",
            output.getvalue(),
        )
        self.assertIn("Processed: 4", output.getvalue())
        self.assertIn("Archived: 2", output.getvalue())
        self.assertIn("Would archive: 0", output.getvalue())
        self.assertIn("Skipped: 2", output.getvalue())

        process_documents.assert_called_once_with(dry_run=False)

    @patch(
        "employees.management.commands.process_expired_documents."
        "DocumentExpirationService.process_expired_documents"
    )
    def test_command_supports_dry_run(self, process_documents):
        process_documents.return_value = {
            "processed": 1,
            "archived": 0,
            "would_archive": 1,
            "skipped": 0,
            "results": [],
        }
        output = StringIO()

        call_command(
            "process_expired_documents",
            "--dry-run",
            stdout=output,
        )

        process_documents.assert_called_once_with(dry_run=True)

        self.assertIn(
            "DRY RUN: no documents were modified.",
            output.getvalue(),
        )
        self.assertIn("Would archive: 1", output.getvalue())
        self.assertIn("Archived: 0", output.getvalue())

    @patch(
        "employees.management.commands.process_expired_documents."
        "DocumentExpirationService.process_expired_documents"
    )
    def test_command_reports_processing_errors(self, process_documents):
        process_documents.side_effect = RuntimeError("simulated failure")

        with self.assertRaisesMessage(
            CommandError,
            "Document retention processing failed",
        ):
            call_command("process_expired_documents")


    @patch(
        "employees.management.commands.process_expired_documents."
        "DocumentExpirationService.process_expired_documents"
    )
    def test_successful_run_is_persisted(self, process_documents):
        process_documents.return_value = {
            "processed": 4,
            "archived": 2,
            "would_archive": 0,
            "skipped": 2,
            "results": [],
        }

        call_command("process_expired_documents")

        execution = DocumentRetentionExecution.objects.get()

        self.assertEqual(
            execution.status,
            DocumentRetentionExecution.Status.SUCCESS,
        )
        self.assertEqual(execution.processed_count, 4)
        self.assertEqual(execution.archived_count, 2)
        self.assertEqual(execution.would_archive_count, 0)
        self.assertEqual(execution.skipped_count, 2)
        self.assertIsNotNone(execution.finished_at)
        self.assertIsNotNone(execution.duration_ms)
        self.assertEqual(execution.error_message, "")

    @patch(
        "employees.management.commands.process_expired_documents."
        "DocumentExpirationService.process_expired_documents"
    )
    def test_dry_run_is_persisted(self, process_documents):
        process_documents.return_value = {
            "processed": 1,
            "archived": 0,
            "would_archive": 1,
            "skipped": 0,
            "results": [],
        }

        call_command("process_expired_documents", "--dry-run")

        execution = DocumentRetentionExecution.objects.get()

        self.assertEqual(
            execution.status,
            DocumentRetentionExecution.Status.DRY_RUN,
        )
        self.assertEqual(execution.would_archive_count, 1)
        self.assertEqual(execution.archived_count, 0)
        self.assertIsNotNone(execution.finished_at)

    @patch(
        "employees.management.commands.process_expired_documents."
        "DocumentExpirationService.process_expired_documents"
    )
    def test_failed_run_is_persisted(self, process_documents):
        process_documents.side_effect = RuntimeError(
            "simulated failure"
        )

        with self.assertRaisesMessage(
            CommandError,
            "Document retention processing failed.",
        ):
            call_command("process_expired_documents")

        execution = DocumentRetentionExecution.objects.get()

        self.assertEqual(
            execution.status,
            DocumentRetentionExecution.Status.FAILURE,
        )
        self.assertIsNotNone(execution.finished_at)
        self.assertIsNotNone(execution.duration_ms)
        self.assertIn("simulated failure", execution.error_message)

    @patch(
        "employees.management.commands.process_expired_documents."
        "DocumentExpirationService.process_expired_documents"
    )
    def test_scheduled_run_is_skipped_after_successful_run_today(
        self,
        process_documents,
    ):
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo

        retention_timezone = ZoneInfo("America/New_York")
        now = timezone.localtime(
            timezone.now(),
            retention_timezone,
        )

        DocumentRetentionExecution.objects.create(
            started_at=now - timedelta(minutes=10),
            finished_at=now - timedelta(minutes=9),
            status=DocumentRetentionExecution.Status.SUCCESS,
        )

        output = StringIO()

        call_command(
            "process_expired_documents",
            "--scheduled",
            stdout=output,
        )

        process_documents.assert_not_called()

        execution = DocumentRetentionExecution.objects.latest(
            "started_at"
        )

        self.assertEqual(
            execution.status,
            DocumentRetentionExecution.Status.SKIPPED,
        )
        self.assertIn(
            "already",
            execution.error_message.lower(),
        )
        self.assertIsNotNone(execution.finished_at)
