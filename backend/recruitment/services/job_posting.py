from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from django.db import transaction
from django.utils import timezone

from accounts.models import AuditLog
from accounts.models import User
from employees.models import EmployeeProfile

from recruitment.models import JobPosting

class JobPostingService:
    """Manage job postings with role-based and departmental access."""

    MANAGEMENT_ROLES = {
        User.Role.SUPER_ADMIN,
        User.Role.HR_ADMIN,
        User.Role.HR_MANAGER,
    }
    EDITABLE_FIELDS = {
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
    }
    AUDIT_ACTIONS = {
        "create": "JOB_POSTING_CREATED",
        "update": "JOB_POSTING_UPDATED",
        "publish": "JOB_POSTING_PUBLISHED",
        "close": "JOB_POSTING_CLOSED",
        "cancel": "JOB_POSTING_CANCELLED",
    }

    @staticmethod
    def _validate_actor(actor):
        """Ensure that the actor is active and authorized."""

        if (
            not actor
            or not actor.is_authenticated
            or not actor.is_active
        ):
            raise PermissionDenied(
                "An active authenticated user is required."
            )

        if actor.role not in JobPostingService.MANAGEMENT_ROLES:
            raise PermissionDenied(
                "You are not allowed to manage job postings."
            )

    @staticmethod
    def _get_manager_department(actor):
        """Return the department assigned to an HR Manager."""

        try:
            profile = EmployeeProfile.objects.select_related(
                "department"
            ).get(user=actor)
        except EmployeeProfile.DoesNotExist as exc:
            raise PermissionDenied(
                "HR Manager must have an employee profile."
            ) from exc

        return profile.department

    @staticmethod
    def _check_department_access(
        actor,
        department,
        *,
        manager_department=None,
    ):
        """Enforce departmental restrictions for HR Managers."""

        if actor.role == User.Role.HR_MANAGER:
            if manager_department is None:
                manager_department = (
                    JobPostingService._get_manager_department(actor)
                )

            if department.pk != manager_department.pk:
                raise PermissionDenied(
                    "You can only manage postings "
                    "for your own department."
                )

    @staticmethod
    def _validate_department_position(department, position):
        """Ensure that the position belongs to the department."""

        if position.department_id != department.pk:
            raise ValidationError({
                "position": (
                    "The selected position does not belong "
                    "to the selected department."
                )
            })

    @staticmethod
    def _record_audit(actor, action, posting):
        """Record a recruitment action in the audit log."""

        AuditLog.objects.create(
            user=actor,
            action=action,
            details=(
                f"{action}: job posting {posting.pk}; "
                f"department {posting.department_id}; "
                f"status {posting.status}."
            ),
        )

    @staticmethod
    @transaction.atomic
    def create_job_posting(*, actor, **validated_data):
        """Create a new draft job posting."""

        JobPostingService._validate_actor(actor)

        protected_fields = {
            "created_by",
            "status",
            "published_at",
        }

        if protected_fields.intersection(validated_data):
            raise ValidationError(
                "System-managed fields cannot be provided."
            )

        department = validated_data.get("department")
        position = validated_data.get("position")

        if not department or not position:
            raise ValidationError(
                "Department and position are required."
            )

        JobPostingService._check_department_access(
            actor,
            department,
        )

        JobPostingService._validate_department_position(
            department,
            position,
        )

        posting = JobPosting(
            **validated_data,
            created_by=actor,
            status="DRAFT",
        )

        posting.full_clean()
        posting.save()

        JobPostingService._record_audit(
            actor,
            JobPostingService.AUDIT_ACTIONS["create"],
            posting,
        )

        return posting

    @staticmethod
    @transaction.atomic
    def update_job_posting(
        *,
        posting_id,
        actor,
        **validated_data,
    ):
        """Update an existing draft or open job posting."""

        JobPostingService._validate_actor(actor)
        invalid_fields = (
            set(validated_data) - JobPostingService.EDITABLE_FIELDS
        )

        if invalid_fields:
            raise ValidationError({
                "fields": (
                    "These fields cannot be modified: "
                    + ", ".join(sorted(invalid_fields))
                )
            })


        try:
            posting = (
                JobPosting.objects
                .select_related("department", "position")
                .select_for_update(of=("self",))
                .get(pk=posting_id)
            )
        except JobPosting.DoesNotExist as exc:
            raise ValidationError(
                "Job posting does not exist."
            ) from exc

        if posting.status not in {"DRAFT", "OPEN"}:
            raise ValidationError(
                "Only draft or open postings can be updated."
            )
        manager_department = None

        if actor.role == User.Role.HR_MANAGER:
            manager_department = (
                JobPostingService._get_manager_department(actor)
            )
        JobPostingService._check_department_access(
            actor,
            posting.department,
            manager_department=manager_department,
        )

        new_department = validated_data.get(
            "department",
            posting.department,
        )

        new_position = validated_data.get(
            "position",
            posting.position,
        )

        JobPostingService._check_department_access(
            actor,
            new_department,
            manager_department=manager_department,
        )

        if posting.status == "OPEN":
            if (
                new_department.pk != posting.department_id
                or new_position.pk != posting.position_id
            ):
                raise ValidationError(
                    "Department and position cannot be changed "
                    "after publication."
                )

        JobPostingService._validate_department_position(
            new_department,
            new_position,
        )

        for field, value in validated_data.items():
            setattr(posting, field, value)

        posting.full_clean()
        posting.save()

        JobPostingService._record_audit(
            actor,
            JobPostingService.AUDIT_ACTIONS["update"],
            posting,
        )

        return posting

    @staticmethod
    @transaction.atomic
    def publish_job_posting(*, posting_id, actor):
        """Publish a draft job posting."""

        JobPostingService._validate_actor(actor)

        try:
            posting = (
                JobPosting.objects
                .select_related("department", "position")
                .select_for_update(of=("self",))
                .get(pk=posting_id)
            )
        except JobPosting.DoesNotExist as exc:
            raise ValidationError(
                "Job posting does not exist."
            ) from exc

        JobPostingService._check_department_access(
            actor,
            posting.department,
        )

        if posting.status != "DRAFT":
            raise ValidationError(
                "Only draft postings can be published."
            )

        if (
            posting.application_deadline
            and posting.application_deadline < timezone.localdate()
        ):
            raise ValidationError({
                "application_deadline": (
                    "An expired job posting cannot be published."
                )
            })

        posting.status = "OPEN"
        posting.published_at = timezone.now()

        posting.full_clean()
        posting.save(
            update_fields=[
                "status",
                "published_at",
                "updated_at",
            ]
        )

        JobPostingService._record_audit(
            actor,
            JobPostingService.AUDIT_ACTIONS["publish"],
            posting,
        )

        return posting

    @staticmethod
    @transaction.atomic
    def close_job_posting(*, posting_id, actor):
        """Close an open job posting."""

        JobPostingService._validate_actor(actor)

        try:
            posting = (
                JobPosting.objects
                .select_related("department", "position")
                .select_for_update(of=("self",))
                .get(pk=posting_id)
            )
        except JobPosting.DoesNotExist as exc:
            raise ValidationError(
                "Job posting does not exist."
            ) from exc

        JobPostingService._check_department_access(
            actor,
            posting.department,
        )

        if posting.status != "OPEN":
            raise ValidationError(
                "Only open postings can be closed."
            )

        posting.status = "CLOSED"
        posting.full_clean()
        posting.save(update_fields=["status", "updated_at"])

        JobPostingService._record_audit(
            actor,
            JobPostingService.AUDIT_ACTIONS["close"],
            posting,
        )

        return posting

    @staticmethod
    @transaction.atomic
    def cancel_job_posting(*, posting_id, actor):
        """Cancel a draft or open job posting."""

        JobPostingService._validate_actor(actor)

        try:
            posting = (
                JobPosting.objects
                .select_related("department", "position")
                .select_for_update(of=("self",))
                .get(pk=posting_id)
            )
        except JobPosting.DoesNotExist as exc:
            raise ValidationError(
                "Job posting does not exist."
            ) from exc

        JobPostingService._check_department_access(
            actor,
            posting.department,
        )

        if posting.status not in {"DRAFT", "OPEN"}:
            raise ValidationError(
                "Only draft or open postings can be cancelled."
            )

        posting.status = "CANCELLED"
        posting.full_clean()
        posting.save(update_fields=["status", "updated_at"])

        JobPostingService._record_audit(
            actor,
            JobPostingService.AUDIT_ACTIONS["cancel"],
            posting,
        )

        return posting
