
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from deploy.notification_scheduler import (
    run_notification_command,
    update_heartbeat,
)


class NotificationSchedulerTests(unittest.TestCase):

    @patch("deploy.notification_scheduler.subprocess.run")
    def test_successful_execution_returns_true(self, mock_run):
        mock_run.return_value = SimpleNamespace(
            returncode=0,
            stdout="Notification processing completed.",
            stderr="",
        )

        result = run_notification_command(enqueue_daily=True)

        self.assertTrue(result)
        command = mock_run.call_args.args[0]
        self.assertIn("--enqueue-daily", command)

    @patch("deploy.notification_scheduler.subprocess.run")
    def test_busy_advisory_lock_returns_false(self, mock_run):
        mock_run.return_value = SimpleNamespace(
            returncode=0,
            stdout="Skipped: another notification run is in progress.",
            stderr="",
        )

        result = run_notification_command(enqueue_daily=True)

        self.assertFalse(result)

    @patch("deploy.notification_scheduler.subprocess.run")
    def test_nonzero_exit_code_returns_false(self, mock_run):
        mock_run.return_value = SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="Notification processing failed.",
        )

        result = run_notification_command(enqueue_daily=False)

        self.assertFalse(result)

    @patch("deploy.notification_scheduler.subprocess.run")
    def test_timeout_returns_false(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd="process_notifications",
            timeout=300,
        )

        result = run_notification_command(enqueue_daily=False)

        self.assertFalse(result)

    @patch("deploy.notification_scheduler.subprocess.run")
    def test_os_error_returns_false(self, mock_run):
        mock_run.side_effect = OSError("Unable to start process")

        result = run_notification_command(enqueue_daily=False)

        self.assertFalse(result)

    @patch("deploy.notification_scheduler.subprocess.run")
    def test_daily_flag_is_omitted_when_not_requested(self, mock_run):
        mock_run.return_value = SimpleNamespace(
            returncode=0,
            stdout="Notification processing completed.",
            stderr="",
        )

        result = run_notification_command(enqueue_daily=False)

        self.assertTrue(result)

        command = mock_run.call_args.args[0]

        self.assertEqual(command[command.index("--batch-size") + 1], "50")
        self.assertEqual(command[command.index("--max-batches") + 1], "10")
        self.assertNotIn("--enqueue-daily", command)

    @patch("deploy.notification_scheduler.HEARTBEAT_FILE")
    def test_update_heartbeat_returns_true_when_successful(
        self,
        mock_heartbeat_file,
    ):
        """A successful heartbeat update returns True."""

        result = update_heartbeat()

        self.assertTrue(result)
        mock_heartbeat_file.touch.assert_called_once_with()

    @patch("deploy.notification_scheduler.HEARTBEAT_FILE")
    def test_update_heartbeat_returns_false_on_os_error(
        self,
        mock_heartbeat_file,
    ):
        """A heartbeat write failure returns False."""

        mock_heartbeat_file.touch.side_effect = OSError(
            "Unable to write heartbeat",
        )

        result = update_heartbeat()

        self.assertFalse(result)
        mock_heartbeat_file.touch.assert_called_once_with()

if __name__ == "__main__":
    unittest.main()
