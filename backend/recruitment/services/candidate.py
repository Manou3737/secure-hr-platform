
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from accounts.models import AuditLog, User
from employees.models import EmployeeProfile
from recruitment.models import Candidate


class CandidateService:
    """Manage candidate profiles with role-based access control."""

    ADMIN_ROLES = {
        User.Role.SUPER_ADMIN,
        User.Role.HR_ADMIN,
    }

    MANAGEMENT_ROLES = ADMIN_ROLES | {
        User.Role.HR_MANAGER,
    }

    EDITABLE_FIELDS = {
        "first_name",
        "last_name",
        "email",
        "phone",
        "linkedin_url",
        "portfolio_url",
    }
    CREATE_FIELDS = EDITABLE_FIELDS | {"department"}
    AUDIT_ACTIONS = {
        "create": "CANDIDATE_CREATED",
        "update": "CANDIDATE_UPDATED",
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

        if actor.role not in CandidateService.MANAGEMENT_ROLES:
            raise PermissionDenied(
                "You are not allowed to manage candidates."
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
    def _check_candidate_access(actor, candidate):
        """Restrict HR Managers to candidates in their department."""

        if actor.role == User.Role.HR_MANAGER:
            department = CandidateService._get_manager_department(
                actor
            )

            if candidate.department_id != department.id:
                raise PermissionDenied(
                    "You can only access candidates "
                    "from your own department."
                )

    @staticmethod
    def _record_audit(actor, action, candidate):
        """Record a candidate action without exposing personal data."""

        AuditLog.objects.create(
            user=actor,
            action=action,
            details=f"{action}: candidate {candidate.pk}.",
        )

    @staticmethod
    @transaction.atomic
    def create_candidate(*, actor, **validated_data):
        """Create a candidate profile. No user account is created."""

        CandidateService._validate_actor(actor)

        if actor.role not in CandidateService.ADMIN_ROLES:
            raise PermissionDenied(
                "Only SUPER_ADMIN and HR_ADMIN can create "
                "standalone candidate profiles."
            )

        invalid_fields = (
            set(validated_data) - CandidateService.CREATE_FIELDS
        )

        if invalid_fields:
            raise ValidationError({
                "fields": (
                    "These fields cannot be provided: "
                    + ", ".join(sorted(invalid_fields))
                )
            })

        if "department" not in validated_data:
            raise ValidationError({
                "department": "A department is required."
            })

        candidate = Candidate(**validated_data)
        candidate.full_clean()
        candidate.save()

        CandidateService._record_audit(
            actor,
            CandidateService.AUDIT_ACTIONS["create"],
            candidate,
        )

        return candidate

    @staticmethod
    def list_candidates(*, actor):
        """Return candidates visible to the authenticated actor."""

        CandidateService._validate_actor(actor)

        queryset = Candidate.objects.all()

        if actor.role == User.Role.HR_MANAGER:
            department = CandidateService._get_manager_department(
                actor
            )

            queryset = queryset.filter(
                department=department
            )
        return queryset.order_by("last_name", "first_name")

    @staticmethod
    def get_candidate(*, candidate_id, actor):
        """Retrieve a candidate after checking departmental access."""

        CandidateService._validate_actor(actor)

        try:
            candidate = Candidate.objects.get(pk=candidate_id)
        except Candidate.DoesNotExist as exc:
            raise ValidationError(
                "Candidate does not exist."
            ) from exc

        CandidateService._check_candidate_access(actor, candidate)

        return candidate

    @staticmethod
    @transaction.atomic
    def update_candidate(
        *,
        candidate_id,
        actor,
        **validated_data,
    ):
        """Update an existing candidate profile."""

        CandidateService._validate_actor(actor)

        invalid_fields = (
            set(validated_data) - CandidateService.EDITABLE_FIELDS
        )

        if invalid_fields:
            raise ValidationError({
                "fields": (
                    "These fields cannot be modified: "
                    + ", ".join(sorted(invalid_fields))
                )
            })

        if not validated_data:
            raise ValidationError(
                "At least one field must be provided."
            )

        try:
            candidate = Candidate.objects.select_for_update().get(
                pk=candidate_id
            )
        except Candidate.DoesNotExist as exc:
            raise ValidationError(
                "Candidate does not exist."
            ) from exc

        CandidateService._check_candidate_access(actor, candidate)

        for field, value in validated_data.items():
            setattr(candidate, field, value)

        candidate.full_clean()
        candidate.save(
            update_fields=[
                *validated_data.keys(),
                "updated_at",
            ]
        )

        CandidateService._record_audit(
            actor,
            CandidateService.AUDIT_ACTIONS["update"],
            candidate,
        )

        return candidate
