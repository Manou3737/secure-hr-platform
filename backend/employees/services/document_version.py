
import hashlib
import logging
import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from employees.antivirus import (
    AntivirusUnavailable,
    MalwareDetected,
    scan_uploaded_file,
)
from employees.models import DocumentVersion, HRDocument
from employees.storage import hr_document_storage

logger = logging.getLogger(__name__)


class DocumentVersionService:
    """Create immutable, privately stored, malware-scanned file versions."""

    MAX_FILE_SIZE = 10 * 1024 * 1024

    ALLOWED_SIGNATURES = {
        ".pdf": (b"%PDF-",),
        ".png": (b"\x89PNG\r\n\x1a\n",),
        ".jpg": (b"\xff\xd8\xff",),
        ".jpeg": (b"\xff\xd8\xff",),
    }

    @staticmethod
    def _is_active_user(user):
        return bool(
            user
            and getattr(user, "is_authenticated", False)
            and getattr(user, "is_active", False)
        )

    @classmethod
    def _authorize(cls, user, document):
        if not cls._is_active_user(user):
            raise PermissionDenied(
                "An active authenticated user is required."
            )

        role = getattr(user, "role", None)

        if role in {"SUPER_ADMIN", "HR_ADMIN"}:
            return

        if (
            role == "EMPLOYEE"
            and document.employee.user_id == user.pk
            and document.status not in {
                HRDocument.Status.VERIFIED,
                HRDocument.Status.QUARANTINED,
                HRDocument.Status.ARCHIVED,
            }
        ):
            return

        raise PermissionDenied(
            "You are not allowed to create a version of this document."
        )

    @classmethod
    def _validate_file(cls, uploaded_file):
        if uploaded_file is None:
            raise ValidationError("A file is required.")

        size = getattr(uploaded_file, "size", 0)

        if not size:
            raise ValidationError("The uploaded file must not be empty.")

        if size > cls.MAX_FILE_SIZE:
            raise ValidationError(
                "The uploaded file exceeds the 10 MB limit."
            )

        filename = (
            getattr(uploaded_file, "name", "document")
            .replace("\\", "/")
            .split("/")[-1]
        )
        extension = (
            "." + filename.rsplit(".", 1)[-1].lower()
            if "." in filename
            else ""
        )

        signatures = cls.ALLOWED_SIGNATURES.get(extension)
        if signatures is None:
            raise ValidationError(
                "Only PDF, PNG, JPG and JPEG files are supported."
            )

        uploaded_file.seek(0)
        header = uploaded_file.read(16)
        uploaded_file.seek(0)

        if not any(header.startswith(sig) for sig in signatures):
            raise ValidationError(
                "The file content does not match its extension."
            )

        return filename, extension, size
    @classmethod
    def _authorize_archived_or_quarantined(cls, user, document):
        if not cls._is_active_user(user):
            raise PermissionDenied(
                "An active authenticated user is required."
            )

        role = getattr(user, "role", None)

        if role in {"SUPER_ADMIN", "HR_ADMIN"}:
            return

        if (
            role == "EMPLOYEE"
            and document.employee.user_id == user.pk
        ):
            return

        raise PermissionDenied(
            "You are not allowed to access this document."
        )


    @classmethod
    def create_version(cls, *, document_id, uploaded_file, actor):
        """
        Store a clean file as a version-history entry.

        This method does not approve the parent document or grant download
        access. The parent document's current file is not replaced here.
        """
        with transaction.atomic():
            document = (
                HRDocument.objects.select_for_update()
                .get(pk=document_id)
            )

            if document.status in {
                HRDocument.Status.QUARANTINED,
                HRDocument.Status.ARCHIVED,
            }:
                cls._authorize_archived_or_quarantined(
                    actor,
                    document,
                )
                raise ValidationError(
                    "Archived or quarantined documents cannot be versioned."
                )

            # Authorization must happen before file processing.
            cls._authorize(actor, document)

            # Validate the file only after authorization.
            filename, extension, size = cls._validate_file(
                uploaded_file
            )

            # Calculate the checksum after validation.
            digest = hashlib.sha256()
            uploaded_file.seek(0)

            for chunk in uploaded_file.chunks():
                digest.update(chunk)

            checksum = digest.hexdigest()
            uploaded_file.seek(0)

            # Scan the file before storing it.
            try:
                scan_uploaded_file(uploaded_file)
            except MalwareDetected as exc:
                raise ValidationError(
                    "The uploaded version was rejected by the antivirus scanner."
                ) from exc
            except AntivirusUnavailable as exc:
                raise ValidationError(
                    "The antivirus scanner is unavailable. Please try again later."
                ) from exc
            finally:
                uploaded_file.seek(0)

            latest = (
                DocumentVersion.objects.filter(document=document)
                .order_by("-version_number")
                .first()
            )

            version_number = (
                latest.version_number + 1 if latest else 1
            )

            storage_key = (
                f"hr-document-versions/{document.pk}/"
                f"{uuid.uuid4().hex}{extension}"
            )

            uploaded_file.seek(0)

            saved_key = hr_document_storage.save(
                storage_key,
                uploaded_file,
            )

            try:
                version = DocumentVersion.objects.create(
                    document=document,
                    version_number=version_number,
                    storage_key=saved_key,
                    original_filename=filename,
                    mime_type=(
                        getattr(uploaded_file, "content_type", None)
                        or "application/octet-stream"
                    ),
                    size_bytes=size,
                    checksum_sha256=checksum,
                    created_by=actor,
                )
            except Exception:
                try:
                    hr_document_storage.delete(saved_key)
                except Exception:
                    logger.critical(
                        "Failed to clean up stored document version.",
                        exc_info=True,
                    )
                raise

            return version
