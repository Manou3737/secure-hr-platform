
"""Retention and expiration handling for private HR documents."""

from datetime import date, datetime, timedelta

from django.db import transaction
from django.utils import timezone

from employees.models import DocumentRetentionPolicy, HRDocument


class DocumentExpirationService:
    """Apply active retention policies to HR documents."""

    @staticmethod
    def _get_reference_date(document, policy):
        """Return the date used to calculate the retention deadline."""
        if policy.retention_basis == (
            DocumentRetentionPolicy.RetentionBasis.UPLOAD_DATE
        ):
            value = document.uploaded_at

        elif policy.retention_basis == (
            DocumentRetentionPolicy.RetentionBasis.VERIFICATION_DATE
        ):
            value = document.verified_at

        elif policy.retention_basis == (
            DocumentRetentionPolicy.RetentionBasis.EXPIRATION_DATE
        ):
            value = document.expires_at

        else:
            return None

        if value is None:
            return None

        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, date):
            return value

        return None

    @classmethod
    def get_retention_deadline(cls, document, policy):
        """Calculate the date on which a document becomes eligible."""
        reference_date = cls._get_reference_date(document, policy)

        if reference_date is None:
            return None

        return reference_date + timedelta(days=policy.retention_days)

    @classmethod
    def is_eligible(cls, document, policy, *, today=None):
        """Check whether a document has reached its retention deadline."""
        if not policy.is_active:
            return False

        if document.document_type != policy.document_type:
            return False

        if document.status == HRDocument.Status.ARCHIVED:
            return False

        today = today or timezone.localdate()
        deadline = cls.get_retention_deadline(document, policy)

        return deadline is not None and deadline <= today

    @classmethod
    @transaction.atomic
    def process_document(
        cls,
        document,
        policy,
        *,
        today=None,
        dry_run=False,
    ):
        """
        Apply a policy to one document.

        Physical deletion is deliberately disabled.
        """
        document = HRDocument.objects.select_for_update().get(
            pk=document.pk
        )
        policy = DocumentRetentionPolicy.objects.get(pk=policy.pk)

        if not cls.is_eligible(document, policy, today=today):
            return {
                "document_id": str(document.pk),
                "action": "SKIPPED",
                "reason": "Document is not eligible under this policy.",
            }

        # Simulation must return before any real modification.
        if dry_run:
            if policy.action == DocumentRetentionPolicy.Action.ARCHIVE:
                return {
                    "document_id": str(document.pk),
                    "action": "WOULD_ARCHIVE",
                    "reason": (
                        "Retention deadline reached; dry run only."
                    ),
                }

            if policy.action == DocumentRetentionPolicy.Action.DELETE:
                return {
                    "document_id": str(document.pk),
                    "action": "SKIPPED",
                    "reason": (
                        "Physical deletion is disabled; "
                        "dry run made no changes."
                    ),
                }

            return {
                "document_id": str(document.pk),
                "action": "SKIPPED",
                "reason": "Unsupported retention action.",
            }

        if policy.action == DocumentRetentionPolicy.Action.DELETE:
            return {
                "document_id": str(document.pk),
                "action": "SKIPPED",
                "reason": (
                    "Physical deletion is not enabled; document history "
                    "and private storage must be handled safely."
                ),
            }

        if policy.action == DocumentRetentionPolicy.Action.ARCHIVE:
            document.status = HRDocument.Status.ARCHIVED
            document.save(update_fields=["status"])

            return {
                "document_id": str(document.pk),
                "action": "ARCHIVED",
                "reason": "Retention deadline reached.",
            }

        return {
            "document_id": str(document.pk),
            "action": "SKIPPED",
            "reason": "Unsupported retention action.",
        }

    @classmethod
    def process_expired_documents(
        cls,
        *,
        today=None,
        dry_run=False,
    ):
        """
        Process documents under active retention policies.

        When dry_run=True, simulate actions without modifying documents.
        Physical deletion remains disabled.
        """
        today = today or timezone.localdate()
        results = []

        policies = DocumentRetentionPolicy.objects.filter(
            is_active=True
        ).order_by("document_type", "name")

        for policy in policies.iterator():
            documents = HRDocument.objects.filter(
                document_type=policy.document_type,
            ).exclude(status=HRDocument.Status.ARCHIVED)

            for document in documents.iterator():
                result = cls.process_document(
                    document,
                    policy,
                    today=today,
                    dry_run=dry_run,
                )
                results.append(result)

        return {
            "processed": len(results),
            "archived": sum(
                item["action"] == "ARCHIVED"
                for item in results
            ),
            "would_archive": sum(
                item["action"] == "WOULD_ARCHIVE"
                for item in results
            ),
            "skipped": sum(
                item["action"] == "SKIPPED"
                for item in results
            ),
            "results": results,
        }
