from rest_framework import serializers

import uuid
from django.db import transaction

from employees.antivirus import (
    AntivirusUnavailable,
    MalwareDetected,
    scan_uploaded_file,
)
from employees.storage import (
    hr_document_storage,
    quarantine_hr_document,
)
from employees.models import OnboardingJourney, OnboardingTask
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
    DocumentVersion,
    DocumentReview,
    DocumentAccessLog,
)
from employees.validators.dashboard import (
    validate_dashboard_as_of,
    validate_dashboard_days,
    validate_dashboard_recent_limit,
)
import hashlib
import logging

logger = logging.getLogger(__name__)
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

class DepartmentSerializer(serializers.ModelSerializer):
    """Serialize department information for read-only selection."""

    class Meta:
        model = Department
        fields = (
            "id",
            "name",
            "code",
            "description",
        )

class PositionSerializer(serializers.ModelSerializer):
    """Serialize position information for read-only selection."""

    class Meta:
        model = Position
        fields = (
            "id",
            "title",
            "department",
            "description",
        )

class LeaveRequestSerializer(serializers.ModelSerializer):
    """Serialize employee leave requests."""
    employee = serializers.PrimaryKeyRelatedField(
        queryset=EmployeeProfile.objects.all(),
        required=True,
    )
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


    def validate(self, attrs):
        """Prevent changing the employee assigned to an existing bank account."""

        if self.instance is not None:
            new_employee = attrs.get("employee")

            if (
                new_employee is not None
                and new_employee != self.instance.employee
            ):
                raise serializers.ValidationError({
                    "employee": (
                        "Changing the employee assigned to a bank account "
                        "is not allowed."
                    )
                })

        return attrs

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

    def get_fields(self):
        """Restrict sensitive metadata updates by employees."""
        fields = super().get_fields()

        request = self.context.get("request")
        user = getattr(request, "user", None)

        if (
            self.instance is not None
            and getattr(user, "role", None) == "EMPLOYEE"
        ):
            fields["metadata"].read_only = True
            fields["expires_at"].read_only = True

        return fields
    def create(self, validated_data):
        """Delegate secure file storage and scanning to the service."""
        from employees.services.document_upload import (
            DocumentUploadService,
        )

        uploaded_file = validated_data.pop("document_file")

        return DocumentUploadService.create_document(
            uploaded_file=uploaded_file,
            document_data=validated_data,
        )
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

class OnboardingJourneySerializer(serializers.ModelSerializer):
    """Serialize onboarding journeys for authorized API clients."""

    class Meta:
        model = OnboardingJourney
        fields = "__all__"
        read_only_fields = (
            "id",
            "employee",
            "template",
            "status",
            "started_at",
            "completed_at",
            "created_by",
            "created_at",
            "updated_at",
        )

class OnboardingTaskSerializer(serializers.ModelSerializer):
    """Serialize onboarding tasks without allowing direct status changes."""

    class Meta:
        model = OnboardingTask
        fields = "__all__"
        read_only_fields = (
            "id",
            "employee",
            "template",
            "status",
            "started_at",
            "completed_at",
            "created_by",
            "created_at",
            "updated_at",
        )

class OnboardingTaskAssignmentSerializer(serializers.Serializer):
    """Validate the assignee identifier for a task assignment."""

    assigned_to_id = serializers.IntegerField(min_value=1)

class OnboardingTaskTransitionSerializer(serializers.Serializer):
    """Validate a requested onboarding task status transition."""

    target_status = serializers.ChoiceField(
        choices=OnboardingTask.Status.choices,
    )

class DocumentVersionSerializer(serializers.ModelSerializer):
    """Expose safe metadata for an immutable HR document version."""

    class Meta:
        model = DocumentVersion
        fields = (
            "id",
            "document",
            "version_number",
            "original_filename",
            "mime_type",
            "size_bytes",
            "checksum_sha256",
            "created_by",
            "created_at",
        )
        read_only_fields = fields

class DocumentReviewSerializer(serializers.ModelSerializer):
    """Expose immutable HR document review history."""

    class Meta:
        model = DocumentReview
        fields = (
            "id",
            "document",
            "version",
            "reviewer",
            "decision",
            "comment",
            "reviewed_at",
        )
        read_only_fields = fields

class DocumentAccessLogSerializer(serializers.ModelSerializer):
    """Expose audit logs as read-only records."""

    user_email = serializers.CharField(
        source="user.email",
        read_only=True,
        default=None,
    )
    document_title = serializers.CharField(
        source="document.title",
        read_only=True,
        default=None,
    )

    class Meta:
        model = DocumentAccessLog
        fields = (
            "id",
            "document",
            "document_title",
            "user",
            "user_email",
            "action",
            "ip_address",
            "user_agent",
            "request_path",
            "details",
            "created_at",
        )
        read_only_fields = fields

class DashboardFilterSerializer(serializers.Serializer):
    """Validate filters accepted by the HR dashboard API."""

    department_id = serializers.IntegerField(
        required=False,
        min_value=1,
    )

    as_of = serializers.DateField(
        required=False,
        allow_null=False,
        validators=[validate_dashboard_as_of],
    )

    days = serializers.IntegerField(
        required=False,
        default=7,
        validators=[validate_dashboard_days],
    )

    recent_limit = serializers.IntegerField(
        required=False,
        default=10,
        validators=[validate_dashboard_recent_limit],
    )

    def validate_department_id(self, value):
        """Ensure the requested department exists."""
        if not Department.objects.filter(pk=value).exists():
            raise serializers.ValidationError(
                "The specified department does not exist."
            )

        return value

class WorkforceHeadcountSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    active_accounts = serializers.IntegerField()
    inactive_accounts = serializers.IntegerField()

class WorkforceDepartmentDistributionSerializer(serializers.Serializer):
    department_id = serializers.IntegerField()
    department__name = serializers.CharField()
    department__code = serializers.CharField()
    employee_count = serializers.IntegerField()

class WorkforcePositionDistributionSerializer(serializers.Serializer):
    position_id = serializers.IntegerField()
    position__title = serializers.CharField()
    department__name = serializers.CharField()
    employee_count = serializers.IntegerField()

class WorkforceDepartmentMetricsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    distribution = WorkforceDepartmentDistributionSerializer(many=True)

class WorkforcePositionMetricsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    distribution = WorkforcePositionDistributionSerializer(many=True)

class WorkforceRoleDistributionSerializer(serializers.Serializer):
    user__role = serializers.CharField()
    employee_count = serializers.IntegerField()

class WorkforceHiresSerializer(serializers.Serializer):
    this_month = serializers.IntegerField()
    this_year = serializers.IntegerField()

class WorkforceMetricsSerializer(serializers.Serializer):
    headcount = WorkforceHeadcountSerializer()
    departments = WorkforceDepartmentMetricsSerializer()
    positions = WorkforcePositionMetricsSerializer()
    roles = WorkforceRoleDistributionSerializer(many=True)
    hires = WorkforceHiresSerializer()
    as_of = serializers.DateField()


class ComplianceIncompleteProfileSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    employee_id = serializers.CharField()
    user__name = serializers.CharField()
    department__name = serializers.CharField()
    position__title = serializers.CharField()

class ComplianceMissingDocumentsSerializer(serializers.Serializer):
    employee_id = serializers.CharField()
    employee_name = serializers.CharField()
    missing_document_types = serializers.ListField(
        child=serializers.CharField()
    )

class ComplianceDocumentDetailSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    employee_id = serializers.CharField()
    employee__user__name = serializers.CharField()
    document_type = serializers.CharField()
    expires_at = serializers.DateField(allow_null=True)

class ComplianceProfilesSerializer(serializers.Serializer):
    complete = serializers.IntegerField()
    incomplete = serializers.IntegerField()
    completion_rate = serializers.FloatField()
    incomplete_details = ComplianceIncompleteProfileSerializer(many=True)

class ComplianceDocumentsSerializer(serializers.Serializer):
    compliant_employees = serializers.IntegerField()
    employees_missing_required_documents = serializers.IntegerField()
    compliance_rate = serializers.FloatField()
    missing_documents_details = (
        ComplianceMissingDocumentsSerializer(many=True)
    )
    expired_count = serializers.IntegerField()
    expired_details = ComplianceDocumentDetailSerializer(many=True)
    expiring_soon_count = serializers.IntegerField()
    expiring_soon_details = ComplianceDocumentDetailSerializer(many=True)

class ComplianceMetricsSerializer(serializers.Serializer):
    as_of = serializers.DateField()
    headcount = serializers.IntegerField()
    profiles = ComplianceProfilesSerializer()
    documents = ComplianceDocumentsSerializer()

class OnboardingJourneyMetricsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    pending = serializers.IntegerField()
    in_progress = serializers.IntegerField()
    suspended = serializers.IntegerField()
    completed = serializers.IntegerField()
    cancelled = serializers.IntegerField()

class OnboardingTaskMetricsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    pending = serializers.IntegerField()
    in_progress = serializers.IntegerField()
    blocked = serializers.IntegerField()
    completed = serializers.IntegerField()
    cancelled = serializers.IntegerField()
    overdue = serializers.IntegerField()
    low_priority = serializers.IntegerField()
    medium_priority = serializers.IntegerField()
    high_priority = serializers.IntegerField()
    urgent_priority = serializers.IntegerField()

class OnboardingProgressSerializer(serializers.Serializer):
    total_eligible_tasks = serializers.IntegerField()
    completed_tasks = serializers.IntegerField()
    percentage = serializers.FloatField()

class OnboardingMetricsSerializer(serializers.Serializer):
    journeys = OnboardingJourneyMetricsSerializer()
    tasks = OnboardingTaskMetricsSerializer()
    progress = OnboardingProgressSerializer()
    as_of = serializers.DateField()

class SecurityOverviewSerializer(serializers.Serializer):
    total_events = serializers.IntegerField()
    login_success = serializers.IntegerField()
    login_failed = serializers.IntegerField()

class SecurityDetectionsSerializer(serializers.Serializer):
    brute_force = serializers.IntegerField()
    suspicious_ip = serializers.IntegerField()
    unauthorized_access = serializers.IntegerField()
    privilege_escalation = serializers.IntegerField()

class SecuritySourcesSerializer(serializers.Serializer):
    distinct_ips = serializers.IntegerField()
    distinct_users = serializers.IntegerField()

class SecurityEventDistributionSerializer(serializers.Serializer):
    event_type = serializers.CharField()
    count = serializers.IntegerField()

class SecurityDailyActivitySerializer(serializers.Serializer):
    created_at__date = serializers.DateField()
    count = serializers.IntegerField()

class SecurityRecentEventSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    event_type = serializers.CharField()
    ip_address = serializers.IPAddressField(allow_null=True)
    request_path = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()

class SecurityEventsSerializer(serializers.Serializer):
    distribution = SecurityEventDistributionSerializer(many=True)

class SecurityMetricsSerializer(serializers.Serializer):
    as_of = serializers.DateField()
    period_days = serializers.IntegerField()
    overview = SecurityOverviewSerializer()
    detections = SecurityDetectionsSerializer()
    sources = SecuritySourcesSerializer()
    events = SecurityEventsSerializer()
    daily_activity = SecurityDailyActivitySerializer(many=True)
    recent_events = SecurityRecentEventSerializer(many=True)

class AuditOverviewSerializer(serializers.Serializer):
    total_entries = serializers.IntegerField()
    general_audit_entries = serializers.IntegerField()
    document_access_entries = serializers.IntegerField()
    workflow_entries = serializers.IntegerField()

class AuditActionDistributionSerializer(serializers.Serializer):
    action = serializers.CharField()
    count = serializers.IntegerField()

class AuditEventDistributionSerializer(serializers.Serializer):
    event_type = serializers.CharField()
    count = serializers.IntegerField()

class AuditDailyActivitySerializer(serializers.Serializer):
    created_at__date = serializers.DateField()
    count = serializers.IntegerField()

class AuditDocumentAccessSerializer(serializers.Serializer):
    distribution = AuditActionDistributionSerializer(many=True)
    access_denied = serializers.IntegerField()

class AuditWorkflowsSerializer(serializers.Serializer):
    distribution = AuditEventDistributionSerializer(many=True)
    outcomes = serializers.DictField(
        child=serializers.IntegerField()
    )

class AuditRecentGeneralEventSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    action = serializers.CharField()
    user_id = serializers.IntegerField(allow_null=True)
    created_at = serializers.DateTimeField()

class AuditRecentDocumentEventSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    action = serializers.CharField()
    user_id = serializers.IntegerField(allow_null=True)
    document_id = serializers.UUIDField(allow_null=True)
    created_at = serializers.DateTimeField()

class AuditRecentWorkflowEventSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    event_type = serializers.CharField()
    outcome = serializers.CharField()
    actor_id = serializers.IntegerField(allow_null=True)
    created_at = serializers.DateTimeField()

class AuditDailyActivityGroupSerializer(serializers.Serializer):
    general_audit = AuditDailyActivitySerializer(many=True)
    document_access = AuditDailyActivitySerializer(many=True)
    workflow = AuditDailyActivitySerializer(many=True)

class AuditRecentEventsSerializer(serializers.Serializer):
    general_audit = AuditRecentGeneralEventSerializer(many=True)
    document_access = AuditRecentDocumentEventSerializer(many=True)
    workflow = AuditRecentWorkflowEventSerializer(many=True)

class AuditGeneralAuditSerializer(serializers.Serializer):
    distribution = AuditActionDistributionSerializer(many=True)

class AuditMetricsSerializer(serializers.Serializer):
    as_of = serializers.DateField()
    period_days = serializers.IntegerField()
    overview = AuditOverviewSerializer()
    general_audit = AuditGeneralAuditSerializer()
    document_access = AuditDocumentAccessSerializer()
    workflows = AuditWorkflowsSerializer()
    daily_activity = AuditDailyActivityGroupSerializer()
    recent_events = AuditRecentEventsSerializer()

class RiskComplianceSerializer(serializers.Serializer):
    incomplete_profiles = serializers.IntegerField()
    employees_missing_required_documents = serializers.IntegerField()
    expired_documents = serializers.IntegerField()
    documents_expiring_soon = serializers.IntegerField()

class RiskDocumentLifecycleSerializer(serializers.Serializer):
    pending_scan = serializers.IntegerField()
    pending_review = serializers.IntegerField()
    quarantined = serializers.IntegerField()
    rejected = serializers.IntegerField()
    verified = serializers.IntegerField()
    archived = serializers.IntegerField()

class RiskSecuritySerializer(serializers.Serializer):
    brute_force = serializers.IntegerField()
    suspicious_ip = serializers.IntegerField()
    unauthorized_access = serializers.IntegerField()
    privilege_escalation = serializers.IntegerField()

class RiskMetricsSerializer(serializers.Serializer):
    as_of = serializers.DateField()
    compliance = RiskComplianceSerializer()
    document_lifecycle = RiskDocumentLifecycleSerializer()
    security = RiskSecuritySerializer()

class OperationsWorkflowMetricsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    success = serializers.IntegerField()
    failure = serializers.IntegerField()
    denied = serializers.IntegerField()

class OperationsNotificationTypeSerializer(serializers.Serializer):
    details__notification_type = serializers.CharField()
    count = serializers.IntegerField()

class OperationsEventDistributionSerializer(serializers.Serializer):
    event_type = serializers.CharField()
    count = serializers.IntegerField()

class OperationsDailyActivitySerializer(serializers.Serializer):
    created_at__date = serializers.DateField()
    count = serializers.IntegerField()

class OperationsNotificationsSerializer(serializers.Serializer):
    failed = serializers.IntegerField()
    by_type = OperationsNotificationTypeSerializer(many=True)

class OperationsEventsSerializer(serializers.Serializer):
    distribution = OperationsEventDistributionSerializer(many=True)

class OperationsMetricsSerializer(serializers.Serializer):
    as_of = serializers.DateField()
    period_days = serializers.IntegerField()
    workflows = OperationsWorkflowMetricsSerializer()
    notifications = OperationsNotificationsSerializer()
    events = OperationsEventsSerializer()
    daily_activity = OperationsDailyActivitySerializer(many=True)

class RecruitmentPostingStatusSerializer(serializers.Serializer):
    status = serializers.CharField()
    count = serializers.IntegerField()

class RecruitmentApplicationStatusSerializer(serializers.Serializer):
    status = serializers.CharField()
    count = serializers.IntegerField()

class RecruitmentDailyActivitySerializer(serializers.Serializer):
    applied_at__date = serializers.DateField()
    count = serializers.IntegerField()

class RecruitmentJobPostingsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    by_status = RecruitmentPostingStatusSerializer(many=True)

class RecruitmentApplicationsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    by_status = RecruitmentApplicationStatusSerializer(many=True)
    received_in_period = serializers.IntegerField()
    hired_in_period = serializers.IntegerField()

class RecruitmentMetricsSerializer(serializers.Serializer):
    as_of = serializers.DateField()
    period_days = serializers.IntegerField()
    job_postings = RecruitmentJobPostingsSerializer()
    applications = RecruitmentApplicationsSerializer()
    daily_activity = RecruitmentDailyActivitySerializer(many=True)

class DashboardResponseSerializer(serializers.Serializer):
    workforce = WorkforceMetricsSerializer()
    compliance = ComplianceMetricsSerializer()
    onboarding = OnboardingMetricsSerializer()
    operations = OperationsMetricsSerializer()
    security = SecurityMetricsSerializer()
    audit = AuditMetricsSerializer()
    risk = RiskMetricsSerializer()
    recruitment = RecruitmentMetricsSerializer()
