
from rest_framework import serializers

from recruitment.models import (
    ApplicationStatusHistory,
    Candidate,
    JobApplication,
    JobPosting,
)
from employees.models import Department

class JobPostingSerializer(serializers.ModelSerializer):
    """Serialize job postings."""

    class Meta:
        model = JobPosting
        fields = [
            "id",
            "title",
            "department",
            "position",
            "description",
            "responsibilities",
            "qualifications",
            "employment_type",
            "location",
            "salary_min",
            "salary_max",
            "status",
            "application_deadline",
            "published_at",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "published_at",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        salary_min = attrs.get(
            "salary_min",
            getattr(self.instance, "salary_min", None),
        )
        salary_max = attrs.get(
            "salary_max",
            getattr(self.instance, "salary_max", None),
        )

        if (
            salary_min is not None
            and salary_max is not None
            and salary_max < salary_min
        ):
            raise serializers.ValidationError({
                "salary_max": (
                    "Maximum salary cannot be lower than minimum salary."
                )
            })

        department = attrs.get(
            "department",
            getattr(self.instance, "department", None),
        )
        position = attrs.get(
            "position",
            getattr(self.instance, "position", None),
        )

        if (
            department is not None
            and position is not None
            and position.department_id != department.pk
        ):
            raise serializers.ValidationError({
                "position": (
                    "The selected position must belong "
                    "to the selected department."
                )
            })

        return attrs

class CandidateSerializer(serializers.ModelSerializer):
    """Serialize candidate profiles."""

    department = serializers.PrimaryKeyRelatedField(
        read_only=True,
    )

    class Meta:
        model = Candidate
        fields = [
            "id",
            "department",
            "first_name",
            "last_name",
            "email",
            "phone",
            "linkedin_url",
            "portfolio_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "department",
            "created_at",
            "updated_at",
        ]

    def validate_email(self, value):
        return value.strip().lower()

class CandidateCreateSerializer(serializers.ModelSerializer):
    """Validate administrative candidate creation."""

    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        required=True,
    )

    class Meta:
        model = Candidate
        fields = [
            "department",
            "first_name",
            "last_name",
            "email",
            "phone",
            "linkedin_url",
            "portfolio_url",
        ]

    def validate_email(self, value):
        return value.strip().lower()

class JobApplicationSerializer(serializers.ModelSerializer):
    """Serialize job applications."""

    candidate = CandidateSerializer(read_only=True)

    candidate_data = CandidateSerializer(write_only=True)

    job_posting = serializers.PrimaryKeyRelatedField(
        queryset=JobPosting.objects.all(),
    )

    class Meta:
        model = JobApplication
        fields = [
            "id",
            "candidate",
            "candidate_data",
            "job_posting",
            "status",
            "cover_letter",
            "assigned_to",
            "privacy_consent",
            "privacy_consent_at",
            "applied_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "assigned_to",
            "privacy_consent_at",
            "applied_at",
            "updated_at",
        ]

    def validate(self, attrs):
        if not self.instance and attrs.get("privacy_consent") is not True:
            raise serializers.ValidationError({
                "privacy_consent": (
                    "Privacy consent is required to submit an application."
                )
            })

        return attrs

class ApplicationStatusHistorySerializer(serializers.ModelSerializer):
    """Expose application status history without allowing modifications."""

    class Meta:
        model = ApplicationStatusHistory
        fields = [
            "id",
            "application",
            "previous_status",
            "new_status",
            "changed_by",
            "note",
            "created_at",
        ]
        read_only_fields = fields

class PublicJobPostingSerializer(serializers.ModelSerializer):
    """Expose only the information candidates need to view open jobs."""

    class Meta:
        model = JobPosting
        fields = [
            "id",
            "title",
            "department",
            "position",
            "description",
            "responsibilities",
            "qualifications",
            "employment_type",
            "location",
            "salary_min",
            "salary_max",
            "application_deadline",
            "published_at",
        ]
        read_only_fields = fields

class JobApplicationAssignmentSerializer(serializers.Serializer):
    """Validate application assignment requests."""

    assigned_to_id = serializers.IntegerField(min_value=1)

class ApplicationStatusChangeSerializer(serializers.Serializer):
    """Validate application status change requests."""

    status = serializers.ChoiceField(
        choices=JobApplication.Status.choices,
    )
    note = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2000,
    )

class ApplicationSubmissionResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
