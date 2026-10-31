
from django.db.models import Count, Q
from django.utils import timezone

from accounts.models import User
from employees.models import (
    Department,
    EmployeeProfile,
    Position,
)


class WorkforceMetricsService:
    """
    Provides workforce metrics for the enterprise HR dashboard.

    Metrics are calculated from EmployeeProfile records.
    User accounts without an EmployeeProfile are excluded.
    """

    @classmethod
    def get_dashboard(cls, *, department_id=None, as_of=None):
        """
        Return workforce metrics.

        Args:
            department_id: Optional department scope.
                Access permissions must be validated by the
                calling dashboard layer.
            as_of: Reference date for hiring metrics.
        """
        as_of = as_of or timezone.localdate()

        employees = EmployeeProfile.objects.select_related(
            "user",
            "department",
            "position",
        )

        if department_id is not None:
            employees = employees.filter(
                department_id=department_id
            )

        # Headcount and account status
        headcount = employees.aggregate(
            total=Count("id"),
            active_accounts=Count(
                "id",
                filter=Q(user__is_active=True),
            ),
            inactive_accounts=Count(
                "id",
                filter=Q(user__is_active=False),
            ),
        )

        # Department distribution
        department_distribution = list(
            employees.values(
                "department_id",
                "department__name",
                "department__code",
            )
            .annotate(employee_count=Count("id"))
            .order_by("department__name")
        )

        # Count departments represented in the workforce
        department_total = len(department_distribution)

        # Position distribution
        position_distribution = list(
            employees.values(
                "position_id",
                "position__title",
                "department__name",
            )
            .annotate(employee_count=Count("id"))
            .order_by(
                "department__name",
                "position__title",
            )
        )

        # Count positions represented in the workforce
        position_total = len(position_distribution)

        # Employee distribution by account role
        role_distribution = list(
            employees.values("user__role")
            .annotate(employee_count=Count("id"))
            .order_by("user__role")
        )

        # Hiring metrics
        hires = employees.aggregate(
            this_month=Count(
                "id",
                filter=Q(
                    hire_date__year=as_of.year,
                    hire_date__month=as_of.month,
                ),
            ),
            this_year=Count(
                "id",
                filter=Q(
                    hire_date__year=as_of.year,
                ),
            ),
        )

        return {
            "headcount": headcount,
            "departments": {
                "total": department_total,
                "distribution": department_distribution,
            },
            "positions": {
                "total": position_total,
                "distribution": position_distribution,
            },
            "roles": role_distribution,
            "hires": hires,
            "as_of": as_of,
        }
