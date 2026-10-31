
from employees.services.employee_compliance import (
    EmployeeComplianceService,
)


class ComplianceMetricsService:
    """
    Provides aggregated compliance metrics for the HR dashboard.

    Business compliance calculations are delegated to
    EmployeeComplianceService to avoid duplicating ORM logic.
    """

    @classmethod
    def get_dashboard(cls, *, department_id=None, as_of=None):
        compliance = EmployeeComplianceService.get_dashboard(
            department_id=department_id,
            as_of=as_of,
        )

        headcount = compliance["headcount"]

        incomplete_profiles = compliance[
            "incomplete_profile_count"
        ]

        employees_missing_documents = compliance[
            "employees_missing_required_documents_count"
        ]

        complete_profiles = (
            headcount - incomplete_profiles
        )

        compliant_employees = (
            headcount - employees_missing_documents
        )

        profile_completion_rate = (
            round(complete_profiles / headcount * 100, 1)
            if headcount
            else 0.0
        )

        document_compliance_rate = (
            round(compliant_employees / headcount * 100, 1)
            if headcount
            else 0.0
        )

        return {
            "as_of": compliance["as_of"],
            "headcount": headcount,
            "profiles": {
                "complete": complete_profiles,
                "incomplete": incomplete_profiles,
                "completion_rate": profile_completion_rate,
                "incomplete_details": compliance[
                    "incomplete_profiles"
                ],
            },
            "documents": {
                "compliant_employees": compliant_employees,
                "employees_missing_required_documents": (
                    employees_missing_documents
                ),
                "compliance_rate": document_compliance_rate,
                "missing_documents_details": compliance[
                    "employees_missing_required_documents"
                ],
                "expired_count": compliance[
                    "expired_document_count"
                ],
                "expired_details": compliance[
                    "expired_documents"
                ],
                "expiring_soon_count": compliance[
                    "documents_expiring_soon_count"
                ],
                "expiring_soon_details": compliance[
                    "documents_expiring_soon"
                ],
            },
        }
