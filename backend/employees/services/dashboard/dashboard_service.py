from employees.services.dashboard.audit_metrics import (
    AuditMetricsService,
)
from employees.services.dashboard.compliance_metrics import (
    ComplianceMetricsService,
)
from employees.services.dashboard.onboarding_metrics import (
    OnboardingMetricsService,
)
from employees.services.dashboard.operations_metrics import (
    OperationsMetricsService,
)
from employees.services.dashboard.risk_metrics import (
    RiskMetricsService,
)
from employees.services.dashboard.security_metrics import (
    SecurityMetricsService,
)
from employees.services.dashboard.workforce_metrics import (
    WorkforceMetricsService,
)
from employees.services.dashboard.recruitment_metrics import (
    RecruitmentMetricsService,
)

class DashboardService:
    """
    Orchestrates specialized dashboard metric services.

    Authorization must be enforced by the API permission layer.
    This service does not implement access-control rules.
    """

    @classmethod
    def get_dashboard(
        cls,
        *,
        department_id=None,
        as_of=None,
        days=7,
        recent_limit=10,
    ):
        return {
            "workforce": WorkforceMetricsService.get_dashboard(
                department_id=department_id,
                as_of=as_of,
            ),
            "compliance": ComplianceMetricsService.get_dashboard(
                department_id=department_id,
                as_of=as_of,
            ),
            "onboarding": OnboardingMetricsService.get_dashboard(
                department_id=department_id,
                as_of=as_of,
            ),
            "operations": OperationsMetricsService.get_dashboard(
                department_id=department_id,
                as_of=as_of,
                days=days,
            ),
            "security": SecurityMetricsService.get_dashboard(
                department_id=department_id,
                as_of=as_of,
                days=days,
                recent_limit=recent_limit,
            ),
            "audit": AuditMetricsService.get_dashboard(
                department_id=department_id,
                as_of=as_of,
                days=days,
                recent_limit=recent_limit,
            ),
            "risk": RiskMetricsService.get_dashboard(
                department_id=department_id,
                as_of=as_of,
            ),
            "recruitment": RecruitmentMetricsService.get_dashboard(
                department_id=department_id,
                as_of=as_of,
                days=days,
            ),
        }
