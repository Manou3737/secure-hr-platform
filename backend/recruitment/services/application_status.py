
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from accounts.models import AuditLog, User
from employees.models import EmployeeProfile
from recruitment.models import (
    ApplicationStatusHistory,
    JobApplication,
)


class ApplicationStatusService:
    """Manage job application status transitions."""

    MANAGEMENT_ROLES = {
        User.Role.SUPER_ADMIN,
        User.Role.HR_ADMIN,
        User.Role.HR_MANAGER,
    }

    ALLOWED_TRANSITIONS = {
        JobApplication.Status.SUBMITTED: {
            JobApplication.Status.SCREENING,
            JobApplication.Status.REJECTED,
            JobApplication.Status.WITHDRAWN,
        },
        JobApplication.Status.SCREENING: {
            JobApplication.Status.INTERVIEW,
            JobApplication.Status.REJECTED,
            JobApplication.Status.WITHDRAWN,
        },
        JobApplication.Status.INTERVIEW: {
            JobApplication.Status.OFFER,
            JobApplication.Status.REJECTED,
            JobApplication.Status.WITHDRAWN,
        },
        JobApplication.Status.OFFER: {
            JobApplication.Status.HIRED,
            JobApplication.Status.REJECTED,
            JobApplication.Status.WITHDRAWN,
        },
        JobApplication.Status.HIRED: set(),
        JobApplication.Status.REJECTED: set(),
        JobApplication.Status.WITHDRAWN: set(),
    }

    AUDIT_ACTION = "JOB_APPLICATION_STATUS_CHANGED"

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

        if actor.role not in ApplicationStatusService.MANAGEMENT_ROLES:
            raise PermissionDenied(
                "You are not allowed to change application statuses."
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
        """Restrict HR Managers to their own department."""

        if actor.role == User.Role.HR_MANAGER:
            department = (
                ApplicationStatusService._get_manager_department(actor)
            )

            if application.job_posting.department_id != department.pk:
                raise PermissionDenied(
                    "You can only manage applications "
                    "for your own department."
                )

    @staticmethod
    def _validate_transition(current_status, new_status):
        """Validate the requested status transition."""

        valid_statuses = {
            value for value, label in JobApplication.Status.choices
        }

        if new_status not in valid_statuses:
            raise ValidationError({
                "status": "Invalid application status."
            })

        allowed = (
            ApplicationStatusService.ALLOWED_TRANSITIONS.get(
                current_status,
                set(),
            )
        )

        if new_status not in allowed:
            raise ValidationError({
                "status": (
                    f"Transition from {current_status} "
                    f"to {new_status} is not allowed."
                )
            })

    @staticmethod
    def _record_audit(actor, application, previous_status, new_status):
        """Record the transition without exposing candidate PII."""

        AuditLog.objects.create(
            user=actor,
            action=ApplicationStatusService.AUDIT_ACTION,
            details=(
                f"Application {application.pk}; "
                f"job posting {application.job_posting_id}; "
                f"previous status {previous_status}; "
                f"new status {new_status}."
            ),
        )

    @staticmethod
    @transaction.atomic
    def change_status(
        application_id,
        new_status,
        actor,
        note="",
    ):
        """
        Change an application's status atomically.

        The application row is locked to prevent concurrent
        status changes from overwriting each other.
        """

        ApplicationStatusService._validate_actor(actor)

        try:
            application = (
                JobApplication.objects
                .select_for_update()
                .select_related("job_posting")
                .get(pk=application_id)
            )
        except JobApplication.DoesNotExist as exc:
            raise ValidationError(
                "Job application does not exist."
            ) from exc

        ApplicationStatusService._check_department_access(
            actor,
            application,
        )

        previous_status = application.status

        ApplicationStatusService._validate_transition(
            previous_status,
            new_status,
        )

        application.status = new_status
        application.full_clean()
        application.save(update_fields=["status", "updated_at"])

        history = ApplicationStatusHistory(
            application=application,
            previous_status=previous_status,
            new_status=new_status,
            changed_by=actor,
            note=note,
        )
        history.full_clean()
        history.save()

        ApplicationStatusService._record_audit(
            actor=actor,
            application=application,
            previous_status=previous_status,
            new_status=new_status,
        )

        return application
