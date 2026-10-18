from rest_framework import serializers

import uuid
from employees.storage import hr_document_storage
from django.db import transaction

from employees.antivirus import (
    AntivirusUnavailable,
    MalwareDetected,
    scan_uploaded_file,
)

from .models import (
    LeaveRequest,
    Department,
    EmployeeProfile,
    PayPeriod,
    Payroll,
    PayrollRecord,
    Earning,
    Deduction,
    Payment,
    BankAccount,
    PerformanceReview,
    Position,
    HRDocument,
)
import hashlib

class EmployeeProfileSerializer(serializers.ModelSerializer):
    """Serialize employee HR profile data."""

    class Meta:
        model = EmployeeProfile
        fields = (
            "id",
            "user",
            "employee_id",
            "department",
            "position",
            "phone",
            "hire_date",
            "date_of_birth",
            "address",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
        )

    def validate_user(self, user):
        """Prevent multiple employee profiles for one user."""

        if EmployeeProfile.objects.filter(
            user=user
        ).exists():
            raise serializers.ValidationError(
                "This user already has an employee profile."
            )

        return user

class LeaveRequestSerializer(serializers.ModelSerializer):
    """Serialize employee leave requests."""

    class Meta:
        model = LeaveRequest
        fields = (
            "id",
            "employee",
            "leave_type",
            "start_date",
            "end_date",
            "reason",
            "status",
            "reviewed_by",
            "reviewed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "status",
            "reviewed_by",
            "reviewed_at",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        """Validate leave request dates."""

        start_date = attrs.get(
            "start_date",
        )
        end_date = attrs.get(
            "end_date",
        )

        if (
            start_date
            and end_date
            and start_date > end_date
        ):
            raise serializers.ValidationError(
                {
                    "end_date": (
                        "End date must be greater than "
                        "or equal to start date."
                    )
                }
            )

        return attrs

class BankAccountSerializer(serializers.ModelSerializer):
    """Serialize employee bank account data securely."""

    routing_number = serializers.CharField(
        write_only=True,
    )

    account_number = serializers.CharField(
        write_only=True,
    )

    masked_routing_number = serializers.SerializerMethodField()

    masked_account_number = serializers.SerializerMethodField()

    class Meta:
        model = BankAccount
        fields = (
            "id",
            "employee",
            "account_type",
            "routing_number",
            "account_number",
            "masked_routing_number",
            "masked_account_number",
            "last_four",
            "is_primary",
            "is_verified",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "masked_routing_number",
            "masked_account_number",
            "last_four",
            "is_verified",
            "created_at",
            "updated_at",
        )

    def get_masked_routing_number(self, obj) -> str :
        """Return only the last four digits of the routing number."""

        return f"*****{obj.routing_number[-4:]}"

    def get_masked_account_number(self, obj) -> str :
        """Return only the last four digits of the account number."""

        return f"****{obj.last_four}"

class PerformanceReviewSerializer(serializers.ModelSerializer):
    """Serialize employee performance review data."""

    class Meta:
        model = PerformanceReview
        fields = (
            "id",
            "employee",
            "reviewer",
            "review_period_start",
            "review_period_end",
            "score",
            "comments",
            "status",
            "submitted_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "reviewer",
            "status",
            "submitted_at",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        """Validate performance review data."""

        start_date = attrs.get("review_period_start")
        end_date = attrs.get("review_period_end")
        score = attrs.get("score")

        if (
            start_date
            and end_date
            and start_date > end_date
        ):
            raise serializers.ValidationError(
                {
                    "review_period_end": (
                        "Review period end date must be "
                        "greater than or equal to start date."
                    )
                }
            )

        if score is not None and (score < 0 or score > 5):
            raise serializers.ValidationError(
                {
                    "score": (
                        "Performance score must be between 0 and 5."
                    )
                }
            )

        return attrs

class HRDocumentSerializer(serializers.ModelSerializer):
    """Serialize HR document metadata without exposing storage details."""
    document_file = serializers.FileField(
        write_only=True,
        required=True,
    )

    MAX_FILE_SIZE = 10 * 1024 * 1024

    ALLOWED_FILE_SIGNATURES = {
        ".pdf": b"%PDF-",
        ".png": b"\x89PNG\r\n\x1a\n",
        ".jpg": b"\xff\xd8\xff",
        ".jpeg": b"\xff\xd8\xff",
    }

    def validate_document_file(self, uploaded_file):
        """Validate the uploaded file's size, extension and signature."""

        if uploaded_file.size == 0:
            raise serializers.ValidationError(
                "The uploaded file cannot be empty."
            )

        if uploaded_file.size > self.MAX_FILE_SIZE:
            raise serializers.ValidationError(
                "The maximum allowed file size is 10 MB."
            )

        filename = uploaded_file.name or ""
        extension = (
            "." + filename.rsplit(".", 1)[-1].lower()
            if "." in filename
            else ""
        )

        expected_signature = self.ALLOWED_FILE_SIGNATURES.get(
            extension
        )

        if expected_signature is None:
            raise serializers.ValidationError(
                "Only PDF, PNG and JPEG files are allowed."
            )

        uploaded_file.seek(0)
        signature = uploaded_file.read(len(expected_signature))
        uploaded_file.seek(0)

        if not signature.startswith(expected_signature):
            raise serializers.ValidationError(
                "The file content does not match its extension."
            )

        return uploaded_file

    def create(self, validated_data):
        """Store the document and apply the antivirus scan lifecycle."""
        uploaded_file = validated_data.pop("document_file")

        original_filename = uploaded_file.name
        mime_type = uploaded_file.content_type or (
            "application/octet-stream"
        )
        size_bytes = uploaded_file.size

        sha256 = hashlib.sha256()
        uploaded_file.seek(0)
        for chunk in uploaded_file.chunks():
            sha256.update(chunk)
        checksum_sha256 = sha256.hexdigest()

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

        uploaded_file.seek(0)
        saved_key = hr_document_storage.save(
            storage_key,
            uploaded_file,
        )

        try:
            with transaction.atomic():
                document = HRDocument.objects.create(
                    **validated_data,
                    storage_key=saved_key,
                    original_filename=original_filename,
                    mime_type=mime_type,
                    size_bytes=size_bytes,
                    checksum_sha256=checksum_sha256,
                    status=HRDocument.Status.PENDING_SCAN,
                )
        except Exception:
            hr_document_storage.delete(saved_key)
            raise

        try:
            uploaded_file.seek(0)
            scan_uploaded_file(uploaded_file)
        except MalwareDetected:
            document.status = HRDocument.Status.QUARANTINED
            document.save(update_fields=["status", "updated_at"])
        except AntivirusUnavailable:
            # Keep the document pending for a future scan retry.
            pass
        else:
            document.status = HRDocument.Status.PENDING_REVIEW
            document.save(update_fields=["status", "updated_at"])

        return document

    class Meta:
        model = HRDocument
        fields = (
            "id",
            "employee",
            "title",
            "document_file",
            "document_type",
            "original_filename",
            "mime_type",
            "size_bytes",
            "checksum_sha256",
            "status",
            "uploaded_by",
            "verified_by",
            "uploaded_at",
            "updated_at",
            "verified_at",
            "rejection_reason",
            "expires_at",
            "metadata",
        )
        read_only_fields = (
            "id",
            "employee",
            "original_filename",
            "mime_type",
            "size_bytes",
            "checksum_sha256",
            "status",
            "uploaded_by",
            "verified_by",
            "uploaded_at",
            "updated_at",
            "verified_at",
            "rejection_reason",
        )
