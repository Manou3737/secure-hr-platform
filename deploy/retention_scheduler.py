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
    """Return the next scheduled 02:00 local time."""
    local_now = now.astimezone(TIMEZONE)

    for offset in range(3):
        day = local_now.date() + timedelta(days=offset)
        candidate = datetime.combine(
            day,
            datetime_time(hour=2, minute=0),
            tzinfo=TIMEZONE,
        )

        normalized = candidate.astimezone(UTC).astimezone(TIMEZONE)

        # If 02:00 does not exist during the spring clock change,
        # use the first valid local time after the jump.
        if normalized.date() != day or normalized.hour != 2:
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
        logger.info("Retention processing completed successfully.")
    else:
        logger.error(
            "Retention processing failed with exit code %s.",
            result.returncode,
        )


def main():
    logger.info(
        "Scheduler started: daily at 02:00 %s.",
        TIMEZONE.key,
    )

    while True:
        now = datetime.now(TIMEZONE)
        scheduled = next_run_after(now)

        logger.info("Next run scheduled for %s.", scheduled.isoformat())

        while True:
            remaining = (scheduled - datetime.now(TIMEZONE)).total_seconds()
            if remaining <= 0:
                break
            time.sleep(min(CHECK_INTERVAL_SECONDS, remaining))

        run_retention_command()


if __name__ == "__main__":
    main()
