
"""Private storage backend for sensitive HR documents."""

import os
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
import logging
import uuid
from pathlib import PurePosixPath

AWS_STORAGE_BUCKET_NAME = os.environ.get(
    "AWS_STORAGE_BUCKET_NAME", ""
).strip()


if AWS_STORAGE_BUCKET_NAME:
    from storages.backends.s3 import S3Storage

    hr_document_storage = S3Storage(
        bucket_name=AWS_STORAGE_BUCKET_NAME,
        region_name=os.environ.get(
            "AWS_S3_REGION_NAME", "us-east-1"
        ),
        endpoint_url=os.environ.get("AWS_S3_ENDPOINT_URL") or None,
        access_key=os.environ.get("AWS_ACCESS_KEY_ID") or None,
        secret_key=os.environ.get("AWS_SECRET_ACCESS_KEY") or None,
        default_acl=None,
        querystring_auth=True,
        querystring_expire=300,
        file_overwrite=False,
        object_parameters={
            "CacheControl": "no-store",
        },
    )
else:

    class PrivateHRDocumentFileSystemStorage(FileSystemStorage):
        """Local storage that does not generate public file URLs."""

        def __init__(self, *args, **kwargs):
            kwargs["base_url"] = "/_private_hr_documents_disabled_/"
            super().__init__(*args, **kwargs)

        def url(self, name):
            raise ValueError(
                "Private HR documents do not have public URLs."
            )

    hr_document_storage = PrivateHRDocumentFileSystemStorage(
        location=Path(settings.BASE_DIR) / "private_hr_documents",
    )
logger = logging.getLogger(__name__)


def quarantine_hr_document(storage_key):
    """Move a private HR document to the quarantine prefix.

    Returns the new storage key on success, or None on failure.
    """
    if not storage_key or storage_key.startswith(
        "hr-document-quarantine/"
    ):
        return storage_key

    extension = PurePosixPath(storage_key).suffix.lower()
    quarantine_key = (
        f"hr-document-quarantine/{uuid.uuid4().hex}{extension}"
    )

    try:
        with hr_document_storage.open(storage_key, "rb") as source:
            saved_key = hr_document_storage.save(
                quarantine_key,
                source,
            )

        try:
            hr_document_storage.delete(storage_key)
        except Exception:
            logger.exception(
                "Failed to remove original HR document after "
                "copying it to quarantine. Original key: %s",
                storage_key,
            )
            try:
                hr_document_storage.delete(saved_key)
            except Exception:
                logger.exception(
                    "Failed to clean up duplicate quarantined "
                    "HR document. Quarantine key: %s",
                    saved_key,
                )
            return None

        return saved_key

    except Exception:
        logger.exception(
            "Failed to move infected HR document to quarantine. "
            "Storage key: %s",
            storage_key,
        )
        return None
