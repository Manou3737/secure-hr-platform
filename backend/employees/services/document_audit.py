
"""Audit logging for sensitive HR document operations."""

import logging

from accounts.siem import create_security_event
from employees.models import DocumentAccessLog

logger = logging.getLogger(__name__)


class DocumentAuditService:
    """Record document actions and optionally emit SIEM events."""

    @staticmethod
    def record(
        *,
        request,
        action,
        document=None,
        details="",
        emit_security_event=False,
        event_type=None,
    ):
        """Persist an audit entry and optionally emit a security event.

        Details must contain operational context only, never document
        contents, credentials, or confidential HR information.
        """
        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False):
            user = None

        meta = getattr(request, "META", {})
        ip_address = meta.get("REMOTE_ADDR") or None

        # Do not trust forwarded IP headers unless a trusted proxy
        # configuration explicitly validates them.
        if ip_address:
            import ipaddress

            try:
                ip_address = str(ipaddress.ip_address(ip_address))
            except ValueError:
                ip_address = None

        log_entry = DocumentAccessLog.objects.create(
            document=document,
            user=user,
            action=action,
            ip_address=ip_address,
            user_agent=meta.get("HTTP_USER_AGENT", "")[:2000],
            request_path=getattr(request, "path", "")[:500],
            details=details[:2000],
        )

        if emit_security_event:
            if not event_type:
                raise ValueError(
                    "event_type is required when emit_security_event=True."
                )

            try:
                create_security_event(
                    request=request,
                    user=user,
                    event_type=event_type,
                    details=details[:2000],
                )
            except Exception:
                # Preserve the audit entry even if SIEM integration fails.
                logger.exception(
                    "Failed to emit document security event; "
                    "audit entry ID: %s",
                    log_entry.pk,
                )

        return log_entry
