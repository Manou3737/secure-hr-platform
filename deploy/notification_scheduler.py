"""Run queued HR notifications every 60 seconds."""
from pathlib import Path
import logging
import subprocess
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("America/New_York")
CHECK_INTERVAL_SECONDS = 60
COMMAND_TIMEOUT_SECONDS = 300
HEARTBEAT_FILE = Path("/tmp/notification-scheduler.heartbeat")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("notification_scheduler")

def update_heartbeat():
    """Update the scheduler liveness heartbeat."""
    try:
        HEARTBEAT_FILE.touch()
        return True
    except OSError:
        logger.exception("Unable to update notification scheduler heartbeat.")
        return False

def run_notification_command(*, enqueue_daily):
    """Run the Django notification processing command."""
    command = [
        sys.executable,
        "manage.py",
        "process_notifications",
        "--batch-size",
        "50",
        "--max-batches",
        "10",
    ]

    if enqueue_daily:
        command.append("--enqueue-daily")

    logger.info(
        "Starting notification processing. enqueue_daily=%s",
        enqueue_daily,
    )

    try:
        result = subprocess.run(
            command,
            cwd="/app",
            check=False,
            timeout=COMMAND_TIMEOUT_SECONDS,
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired:
        logger.error(
            "Notification processing timed out after %s seconds.",
            COMMAND_TIMEOUT_SECONDS,
        )
        return False
    except OSError:
        logger.exception("Unable to start notification processing.")
        return False

    if result.stdout.strip():
        logger.info("Notification command output:\n%s", result.stdout.strip())

    if result.stderr.strip():
        logger.warning("Notification command errors:\n%s", result.stderr.strip())

    if "another notification run is in progress" in result.stdout.lower():
        logger.warning(
            "Notification run skipped because the PostgreSQL advisory lock "
            "is held. It will be retried."
        )
        return False

    if result.returncode == 0:
        logger.info("Notification processing completed successfully.")
        return True

    logger.error(
        "Notification processing failed with exit code %s.",
        result.returncode,
    )
    return False


def main():
    logger.info(
        "Notification scheduler started. Interval: %s seconds. Timezone: %s.",
        CHECK_INTERVAL_SECONDS,
        TIMEZONE.key,
    )

    last_daily_enqueue_date = None

    while True:
        cycle_started = time.monotonic()
        today = datetime.now(TIMEZONE).date()

        enqueue_daily = last_daily_enqueue_date != today

        success = run_notification_command(
            enqueue_daily=enqueue_daily,
        )

        if success and enqueue_daily:
            last_daily_enqueue_date = today
            logger.info(
                "Daily notification enqueue completed for %s.",
                today.isoformat(),
            )

        update_heartbeat()
        elapsed = time.monotonic() - cycle_started
        sleep_seconds = max(0, CHECK_INTERVAL_SECONDS - elapsed)

        logger.info(
            "Next notification cycle in %.1f seconds.",
            sleep_seconds,
        )
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()
