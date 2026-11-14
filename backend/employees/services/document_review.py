
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from employees.models import DocumentReview, DocumentVersion, HRDocument
from employees.services.document_access import DocumentAccessService

class DocumentReviewService:
    """Record HR document review decisions with authorization and audit history."""

    REVIEWER_ROLES = {"SUPER_ADMIN", "HR_ADMIN", "HR_MANAGER"}

    @staticmethod
    def _is_active_user(user):
        return bool(
            user
            and getattr(user, "is_authenticated", False)
            and getattr(user, "is_active", False)
        )

    @classmethod
    def _authorize_reviewer(cls, actor, document):
        if not cls._is_active_user(actor):
            raise PermissionDenied(
                "An active authenticated user is required."
            )

        if getattr(actor, "role", None) not in cls.REVIEWER_ROLES:
            raise PermissionDenied(
                "You are not allowed to review HR documents."
            )
        if not DocumentAccessService.can_view_document(
            actor,
            document,
        ):
            raise PermissionDenied(
                "You cannot review documents outside your department."
            )
        # A document owner or uploader cannot review their own submission.
        if actor.pk in {
            document.employee.user_id,
            document.uploaded_by_id,
        }:
            raise PermissionDenied(
                "You cannot review a document you own or uploaded."
            )

    @classmethod
    def review_document(
        cls,
        *,
        document_id,
        actor,
        decision,
        comment="",
        version_id=None,
    ):
        """Record a review decision and update the parent document when applicable."""

        valid_decisions = {
            choice
            for choice, _label in DocumentReview.Decision.choices
        }

        if decision not in valid_decisions:
            raise ValidationError("Invalid document review decision.")

        if not isinstance(comment, str):
            raise ValidationError("The review comment must be text.")

        comment = comment.strip()

        if (
            decision == DocumentReview.Decision.REJECTED
            and not comment
        ):
            raise ValidationError(
                "A rejection reason is required."
            )

        with transaction.atomic():
            try:
                document = (
                    HRDocument.objects.select_for_update()
                    .get(pk=document_id)
                )
            except HRDocument.DoesNotExist as exc:
                raise ValidationError(
                    "The requested HR document does not exist."
                ) from exc

            cls._authorize_reviewer(actor, document)

            version = None
            if version_id is not None:
                try:
                    version = DocumentVersion.objects.get(
                        pk=version_id,
                        document=document,
                    )
                except DocumentVersion.DoesNotExist as exc:
                    raise ValidationError(
                        "The version does not belong to this document "
                        "or does not exist."
                    ) from exc

                # Version reviews are audit-only: the parent document's
                # status is not changed because it has no current-version link.
                if document.status not in {
                    HRDocument.Status.PENDING_REVIEW,
                    HRDocument.Status.VERIFIED,
                }:
                    raise ValidationError(
                        "This document is not eligible for version review."
                    )

            else:
                if document.status != HRDocument.Status.PENDING_REVIEW:
                    raise ValidationError(
                        "Only documents pending review can receive "
                        "a document-level decision."
                    )

            review = DocumentReview.objects.create(
                document=document,
                version=version,
                reviewer=actor,
                decision=decision,
                comment=comment,
                reviewed_at=timezone.now(),
            )

            # Only a document-level decision updates the parent lifecycle.
            if version is None:
                if decision == DocumentReview.Decision.APPROVED:
                    document.status = HRDocument.Status.VERIFIED
                    document.verified_by = actor
                    document.verified_at = review.reviewed_at
                    document.rejection_reason = ""
                else:
                    document.status = HRDocument.Status.REJECTED
                    document.verified_by = None
                    document.verified_at = None
                    document.rejection_reason = comment

                document.save(
                    update_fields=[
                        "status",
                        "verified_by",
                        "verified_at",
                        "rejection_reason",
                        "updated_at",
                    ]
                )

            return review
