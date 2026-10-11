from datetime import timedelta

from django.utils import timezone

from .models import SecurityEvent
from .siem import create_security_event


def detect_brute_force(
    request,
    ip_address,
    threshold=5,
    window_minutes=5,
):
    """Detect repeated failed login attempts from one IP address."""

    window_start = timezone.now() - timedelta(
        minutes=window_minutes
    )

    failed_attempts = SecurityEvent.objects.filter(
        event_type="LOGIN_FAILED",
        ip_address=ip_address,
        created_at__gte=window_start,
    ).count()

    if failed_attempts >= threshold:
        already_detected = SecurityEvent.objects.filter(
            event_type="BRUTE_FORCE_DETECTED",
            ip_address=ip_address,
            created_at__gte=window_start,
        ).exists()

        if not already_detected:
            create_security_event(
                request=request,
                event_type="BRUTE_FORCE_DETECTED",
                details=(
                    f"{failed_attempts} failed login attempts "
                    f"within {window_minutes} minutes."
                ),
            )

        return True

    return False


def detect_suspicious_ip(
    request,
    ip_address,
    threshold=10,
    window_minutes=10,
):
    """Detect excessive security events from one IP address."""

    window_start = timezone.now() - timedelta(
        minutes=window_minutes
    )

    event_count = SecurityEvent.objects.filter(
        ip_address=ip_address,
        created_at__gte=window_start,
    ).count()

    if event_count >= threshold:
        already_detected = SecurityEvent.objects.filter(
            event_type="SUSPICIOUS_IP_DETECTED",
            ip_address=ip_address,
            created_at__gte=window_start,
        ).exists()

        if not already_detected:
            create_security_event(
                request=request,
                event_type="SUSPICIOUS_IP_DETECTED",
                details=(
                    f"{event_count} security events from this IP "
                    f"within {window_minutes} minutes."
                ),
            )

        return True

    return False
