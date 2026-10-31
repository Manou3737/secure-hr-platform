"""Secure upload lifecycle for private HR documents."""

import hashlib
import logging
import uuid

from django.db import transaction

from employees.antivirus import (
    AntivirusUnavailable,
    MalwareDetected,
    scan_uploaded_file,
)
from employees.models import HRDocument
from employees.storage import (
    hr_document_storage,
    quarantine_hr_document,
)

logger = logging.getLogger(__name__)


class DocumentUploadService:
    """Manage private storage, database creation and antivirus scanning."""

    @staticmethod
    def create_document(uploaded_file, document_data):
        """Save, scan and create an HR document.

        File format, signature and size validation must be performed
        by the serializer before calling this method.
        """
        original_filename = uploaded_file.name
        mime_type = uploaded_file.content_type or (
            "application/octet-stream"
        )
        size_bytes = uploaded_file.size

        # Calculate SHA-256 using the complete uploaded file.
        sha256 = hashlib.sha256()
        uploaded_file.seek(0)

        for chunk in uploaded_file.chunks():
            sha256.update(chunk)

        checksum_sha256 = sha256.hexdigest()

        # Generate a unique private storage key.
        extension = (
            original_filename.rsplit(".", 1)[-1].lower()
            if "." in original_filename
            else ""
        )

        storage_key = (
            f"hr-documents/{uuid.uuid4().hex}.{extension}"
            if extension
            else f"hr-documents/{uuid.uuid4().hex}"
        )

        # Store the file before creating its database record.
        uploaded_file.seek(0)
        saved_key = hr_document_storage.save(
            storage_key,
            uploaded_file,
        )

        # If database creation fails, clean up the stored file.
        try:
            with transaction.atomic():
                document = HRDocument.objects.create(
                    **document_data,
                    storage_key=saved_key,
                    original_filename=original_filename,
                    mime_type=mime_type,
                    size_bytes=size_bytes,
                    checksum_sha256=checksum_sha256,
                    status=HRDocument.Status.PENDING_SCAN,
                )
        except Exception:
            try:
                hr_document_storage.delete(saved_key)
            except Exception:
                logger.critical(
                    "Failed to clean up HR document after database "
                    "creation failed. Storage key: %s",
                    saved_key,
                    exc_info=True,
                )
            raise

        # Scan the uploaded content before it can be reviewed.
        try:
            uploaded_file.seek(0)
            scan_uploaded_file(uploaded_file)

        except MalwareDetected:
            quarantine_key = quarantine_hr_document(saved_key)

            document.status = HRDocument.Status.QUARANTINED

            if quarantine_key:
                document.storage_key = quarantine_key
            else:
                # Fail closed: attempt to delete the infected file.
                try:
                    hr_document_storage.delete(saved_key)
                except Exception:
                    logger.critical(
                        "Infected HR document could not be moved "
                        "or deleted. Document ID: %s",
                        document.pk,
                        exc_info=True,
                    )

                # Never reference the original key after quarantine
                # has failed, even if deletion also failed.
                document.storage_key = (
                    "hr-document-quarantine/blocked/"
                    f"{uuid.uuid4().hex}"
                )

                logger.critical(
                    "Malicious HR document could not be moved "
                    "to quarantine. Document ID: %s",
                    document.pk,
                )

            document.save(
                update_fields=[
                    "status",
                    "storage_key",
                    "updated_at",
                ]
            )

        except AntivirusUnavailable:
            # Keep the document pending for a future scan retry.
            pass

        else:
            document.status = HRDocument.Status.PENDING_REVIEW
            document.save(
                update_fields=["status", "updated_at"]
            )

        return document
