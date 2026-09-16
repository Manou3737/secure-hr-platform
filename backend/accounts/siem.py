import json
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from .models import SecurityEvent


def get_client_ip(request):
    """Return the client's IP address from the request."""

    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")

    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

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

    _write_siem_log(event)

    return event
