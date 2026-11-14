
"""Run document retention processing daily at 02:00 America/New_York."""

import logging
import subprocess
import sys
import time
from datetime import datetime, time as datetime_time, timedelta
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
CHECK_INTERVAL_SECONDS = 15

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("retention_scheduler")


def next_run_after(now):
    """Return the next 02:00 local occurrence strictly after now."""
    local_now = now.astimezone(TIMEZONE)
    candidate_date = local_now.date()

    for offset in range(3):
        candidate_date = local_now.date() + timedelta(days=offset)
        candidate = datetime.combine(
            candidate_date,
            datetime_time(hour=2, minute=0),
            tzinfo=TIMEZONE,
        )

        # Detect nonexistent local time during the spring DST transition.
        normalized = candidate.astimezone(UTC).astimezone(TIMEZONE)
        if normalized.date() != candidate_date or normalized.hour != 2:
            candidate = normalized.replace(second=0, microsecond=0)

        if candidate > local_now:
            return candidate

    raise RuntimeError("Unable to calculate the next scheduled run.")


def run_retention_command():
    """Run the Django retention management command."""
    logger.info("Starting document retention processing.")
    result = subprocess.run(
        [
            sys.executable,
            "manage.py",
            "process_expired_documents",
             "--scheduled",
        ],
        cwd="/app",
        check=False,
    )

    if result.returncode == 0:
        logger.info("Document retention processing completed successfully.")
    else:
        logger.error(
            "Document retention processing failed with exit code %s.",
            result.returncode,
        )


def main():
    logger.info(
        "Scheduler started. Daily schedule: 02:00 %s.",
        TIMEZONE.key,
    )

    last_run_date = None

    while True:
        now = datetime.now(TIMEZONE)
        scheduled = next_run_after(now)

        logger.info("Next run: %s", scheduled.isoformat())

        while True:
            now = datetime.now(TIMEZONE)
            remaining = (scheduled - now).total_seconds()
            if remaining <= 0:
                break
            time.sleep(min(CHECK_INTERVAL_SECONDS, remaining))

        run_date = scheduled.date()

        if last_run_date != run_date:
            run_retention_command()
            last_run_date = run_date


if __name__ == "__main__":
    main()
