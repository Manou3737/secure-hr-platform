import json
import logging
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from unittest.mock import patch
from .models import SecurityEvent

logger = logging.getLogger(__name__)
def get_client_ip(request):
    """Return the direct client IP address.

    Forwarded headers are not trusted unless a trusted-proxy
    configuration is explicitly implemented.
    """
    return request.META.get("REMOTE_ADDR")


def _write_siem_log(event):
    """Write a security event to the local SIEM JSONL log."""

    log_directory = Path(settings.BASE_DIR) / "logs"
    log_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    log_file = log_directory / "security-events.jsonl"

    payload = {
        "@timestamp": timezone.now().isoformat(),
        "event.action": event.event_type,
        "source.ip": event.ip_address,
        "url.path": event.request_path,
        "user_agent.original": event.user_agent,
        "user.id": event.user_id,
        "message": event.details,
    }

    with log_file.open(
        "a",
        encoding="utf-8",
    ) as file:
        file.write(
            json.dumps(payload)
            + "\n"
        )


def create_security_event(
    request,
    event_type,
    details=None,
    user=None,
):
    """Create a security event in the database and SIEM log."""

    event = SecurityEvent.objects.create(
        user=user,
        event_type=event_type,
        ip_address=get_client_ip(request),
        user_agent=request.META.get(
            "HTTP_USER_AGENT",
            "",
        ),
        request_path=request.path,
        details=details or "",
    )
    try:
        _write_siem_log(event)
    except OSError:
        logger.exception(
            "Failed to write security event to the SIEM file. "
            "Event ID: %s, event type: %s",
            event.pk,
            event.event_type,
        )

    return event
