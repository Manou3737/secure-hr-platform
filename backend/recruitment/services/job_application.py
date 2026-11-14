from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import AuditLog, User
from employees.models import EmployeeProfile
from recruitment.models import (
    ApplicationStatusHistory,
    Candidate,
    JobApplication,
    JobPosting,
)


class JobApplicationService:
    """Manage public job applications and HR application access."""

    MANAGEMENT_ROLES = {
        User.Role.SUPER_ADMIN,
        User.Role.HR_ADMIN,
        User.Role.HR_MANAGER,
    }

    CANDIDATE_FIELDS = {
        "first_name",
        "last_name",
        "email",
        "phone",
        "linkedin_url",
        "portfolio_url",
    }

    REQUIRED_CANDIDATE_FIELDS = {
        "first_name",
        "last_name",
        "email",
    }

    AUDIT_ACTIONS = {
        "submit": "JOB_APPLICATION_SUBMITTED",
        "assign": "JOB_APPLICATION_ASSIGNED",
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

        if actor.role not in JobApplicationService.MANAGEMENT_ROLES:
            raise PermissionDenied(
                "You are not allowed to manage job applications."
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
    def _check_department_access(actor, application):
        """Restrict HR Managers to applications in their department."""

        if actor.role == User.Role.HR_MANAGER:
            department = (
                JobApplicationService._get_manager_department(actor)
            )

            if application.job_posting.department_id != department.pk:
                raise PermissionDenied(
                    "You can only access applications "
                    "for your own department."
                )

    @staticmethod
    def _record_audit(actor, action, application):
        """Record an application action without exposing candidate PII."""

        AuditLog.objects.create(
            user=actor,
            action=action,
            details=(
                f"{action}: application {application.pk}; "
                f"job posting {application.job_posting_id}; "
                f"status {application.status}."
            ),
        )

    @staticmethod
    def _get_or_create_candidate(candidate_data, *, department):
        """Reuse or create a candidate profile within one department."""

        if not isinstance(candidate_data, dict):
            raise ValidationError(
                "Candidate data must be provided as a dictionary."
            )

        invalid_fields = (
            set(candidate_data)
            - JobApplicationService.CANDIDATE_FIELDS
        )

        if invalid_fields:
            raise ValidationError({
                "candidate": (
                    "Unsupported candidate fields: "
                    + ", ".join(sorted(invalid_fields))
                )
            })

        missing_fields = (
            JobApplicationService.REQUIRED_CANDIDATE_FIELDS
            - set(candidate_data)
        )

        if missing_fields:
            raise ValidationError({
                "candidate": (
                    "Required candidate fields are missing: "
                    + ", ".join(sorted(missing_fields))
                )
            })

        email = candidate_data.get("email")

        if not isinstance(email, str) or not email.strip():
            raise ValidationError({
                "email": "A valid email address is required."
            })

        normalized_email = email.strip().lower()

        candidate = Candidate.objects.filter(
            department=department,
            email__iexact=normalized_email,
        ).first()

        if candidate:
            return candidate

        candidate = Candidate(
            **candidate_data,
            department=department,
        )
        candidate.email = normalized_email
        candidate.full_clean()

        try:
            with transaction.atomic():
                candidate.save()
        except IntegrityError:
            candidate = Candidate.objects.filter(
                department=department,
                email__iexact=normalized_email,
            ).first()

            if not candidate:
                raise

        return candidate
    @staticmethod
    @transaction.atomic
    def submit_application(
        *,
        posting_id,
        candidate_data,
        cover_letter="",
        privacy_consent=False,
    ):
        """Submit a public application without requiring a user account."""

        if privacy_consent is not True:
            raise ValidationError({
                "privacy_consent": (
                    "Privacy consent is required to submit an application."
                )
            })

        if not isinstance(cover_letter, str):
            raise ValidationError({
                "cover_letter": "Cover letter must be text."
            })

        try:
            posting = JobPosting.objects.select_for_update().get(
                pk=posting_id
            )
        except JobPosting.DoesNotExist as exc:
            raise ValidationError(
                "Job posting does not exist."
            ) from exc

        if posting.status != JobPosting.Status.OPEN:
            raise ValidationError(
                "Applications are only accepted for open job postings."
            )

        if (
            posting.application_deadline
            and posting.application_deadline < timezone.localdate()
        ):
            raise ValidationError(
                "The application deadline has passed."
            )

        candidate = JobApplicationService._get_or_create_candidate(
            candidate_data,
            department=posting.department,
        )

        if JobApplication.objects.filter(
            candidate=candidate,
            job_posting=posting,
        ).exists():
            raise ValidationError(
                "This candidate has already applied for this job."
            )

        application = JobApplication(
            candidate=candidate,
            job_posting=posting,
            status=JobApplication.Status.SUBMITTED,
            cover_letter=cover_letter,
            privacy_consent=True,
            privacy_consent_at=timezone.now(),
        )

        application.full_clean()

        try:
            with transaction.atomic():
                application.save()
        except IntegrityError as exc:
            raise ValidationError(
                "This candidate has already applied for this job."
            ) from exc

        ApplicationStatusHistory.objects.create(
            application=application,
            previous_status="",
            new_status=JobApplication.Status.SUBMITTED,
            changed_by=None,
            note="Application submitted.",
        )

        JobApplicationService._record_audit(
            None,
            JobApplicationService.AUDIT_ACTIONS["submit"],
            application,
        )

        return application

    @staticmethod
    def list_applications(*, actor):
        """List applications accessible to the authenticated HR actor."""

        JobApplicationService._validate_actor(actor)

        queryset = JobApplication.objects.select_related(
            "candidate",
            "job_posting",
            "job_posting__department",
            "job_posting__position",
            "assigned_to",
        )

        if actor.role == User.Role.HR_MANAGER:
            department = (
                JobApplicationService._get_manager_department(actor)
            )
            queryset = queryset.filter(
                job_posting__department=department
            )

        return queryset.order_by("-applied_at")

    @staticmethod
    def get_application(*, application_id, actor):
        """Retrieve one application after checking access."""

        JobApplicationService._validate_actor(actor)

        try:
            application = JobApplication.objects.select_related(
                "candidate",
                "job_posting",
                "job_posting__department",
                "job_posting__position",
                "assigned_to",
            ).get(pk=application_id)
        except JobApplication.DoesNotExist as exc:
            raise ValidationError(
                "Job application does not exist."
            ) from exc

        JobApplicationService._check_department_access(
            actor,
            application,
        )

        return application

    @staticmethod
    @transaction.atomic
    def assign_application(
        *,
        application_id,
        assigned_to_id,
        actor,
    ):
        """Assign an application to an authorized active HR user."""

        JobApplicationService._validate_actor(actor)

        try:
            application = JobApplication.objects.select_for_update().get(
                pk=application_id
            )
        except JobApplication.DoesNotExist as exc:
            raise ValidationError(
                "Job application does not exist."
            ) from exc

        JobApplicationService._check_department_access(
            actor,
            application,
        )

        try:
            assignee = User.objects.get(pk=assigned_to_id)
        except User.DoesNotExist as exc:
            raise ValidationError(
                "The assigned user does not exist."
            ) from exc

        if not assignee.is_active:
            raise ValidationError(
                "The assigned user must be active."
            )

        if assignee.role not in JobApplicationService.MANAGEMENT_ROLES:
            raise ValidationError(
                "Applications can only be assigned to authorized HR users."
            )

        if assignee.role == User.Role.HR_MANAGER:
            assignee_department = (
                JobApplicationService._get_manager_department(assignee)
            )

            if (
                assignee_department.pk
                != application.job_posting.department_id
            ):
                raise ValidationError(
                    "The assigned HR Manager must belong "
                    "to the application's department."
                )

        application.assigned_to = assignee
        application.save(
            update_fields=["assigned_to", "updated_at"]
        )

        JobApplicationService._record_audit(
            actor,
            JobApplicationService.AUDIT_ACTIONS["assign"],
            application,
        )

        return application
