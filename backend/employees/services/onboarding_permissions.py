from django.db.models import Q
from employees.models import (
    OnboardingJourney,
    OnboardingTask,
)


class OnboardingPermissionService:
    """Centralize authorization rules for onboarding operations."""

    TEMPLATE_MANAGEMENT_ROLES = {
        "SUPER_ADMIN",
        "HR_ADMIN",
    }

    OPERATIONAL_ROLES = {
        "SUPER_ADMIN",
        "HR_ADMIN",
        "HR_MANAGER",
    }

    @staticmethod
    def _is_active_authenticated_user(user):
        """Return whether the user is authenticated and active."""
        return bool(
            user
            and getattr(user, "is_authenticated", False)
            and getattr(user, "is_active", False)
            and getattr(user, "pk", None)
        )

    @classmethod
    def can_view_journey(cls, user, journey):
        """Check whether a user may view an onboarding journey."""
        if not cls._is_active_authenticated_user(user) or journey is None:
            return False

        if user.role in {"SUPER_ADMIN", "HR_ADMIN"}:
            return True

        if user.role == "HR_MANAGER":
            manager_profile = getattr(user, "employee_profile", None)
            manager_department_id = getattr(
                manager_profile, "department_id", None
            )
            return bool(
                manager_department_id
                and OnboardingJourney.objects.filter(
                    pk=journey.pk,
                    employee__department_id=manager_department_id,
                ).exists()
            )

        if user.role != "EMPLOYEE":
            return False

        return OnboardingJourney.objects.filter(
            pk=journey.pk,
            employee__user_id=user.pk,
        ).exists()

    @classmethod
    def can_view_task(cls, user, task):
        """Check whether a user may view an onboarding task."""
        if not cls._is_active_authenticated_user(user) or task is None:
            return False

        if user.role in {"SUPER_ADMIN", "HR_ADMIN"}:
            return True

        if user.role == "HR_MANAGER":
            manager_profile = getattr(user, "employee_profile", None)
            manager_department_id = getattr(
                manager_profile, "department_id", None
            )
            return bool(
                manager_department_id
                and OnboardingTask.objects.filter(
                    pk=task.pk,
                    journey__employee__department_id=manager_department_id,
                ).exists()
            )

        if user.role != "EMPLOYEE":
            return False

        return OnboardingTask.objects.filter(
            pk=task.pk,
        ).filter(
            Q(journey__employee__user_id=user.pk)
            | Q(assigned_to_id=user.pk)
        ).exists()

    @classmethod
    def can_manage_templates(cls, user):
        """Check whether a user may manage onboarding templates."""
        return bool(
            cls._is_active_authenticated_user(user)
            and user.role in cls.TEMPLATE_MANAGEMENT_ROLES
        )

    @classmethod
    def can_assign_tasks(cls, user):
        """Check whether a user may assign onboarding tasks."""
        return bool(
            cls._is_active_authenticated_user(user)
            and user.role in cls.OPERATIONAL_ROLES
        )

    @classmethod
    def can_transition_tasks(cls, user):
        """Check whether a user may transition onboarding task statuses."""
        return bool(
            cls._is_active_authenticated_user(user)
            and user.role in cls.OPERATIONAL_ROLES
        )
