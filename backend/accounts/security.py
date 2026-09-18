from .models import SecurityEvent


def get_client_ip(request):
    """Return the client's IP address from the request."""

    forwarded_for = request.META.get(
        "HTTP_X_FORWARDED_FOR"
    )

    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR")


def create_security_event(
    request,
    event_type,
    details="",
):
    """Create a security event from an HTTP request."""

    return SecurityEvent.objects.create(
        user=(
            request.user
            if request.user.is_authenticated
            else None
        ),
        event_type=event_type,
        ip_address=get_client_ip(request),
        user_agent=request.META.get(
            "HTTP_USER_AGENT",
            "",
        ),
        request_path=request.path,
        details=details,
    )
