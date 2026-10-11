from rest_framework.routers import DefaultRouter

from .views import (
    EmployeeProfileViewSet,
    LeaveRequestViewSet,
    BankAccountViewSet,
    PerformanceReviewViewSet,
)


router = DefaultRouter()

router.register(
    "bank-accounts",
    BankAccountViewSet,
    basename="bank-account",
)
router.register(
    "performance-reviews",
     PerformanceReviewViewSet,
     basename="performance-review"
)
router.register(
    "leave-requests",
    LeaveRequestViewSet,
    basename="leave-request",
)

router.register(
    "",
    EmployeeProfileViewSet,
    basename="employee",
)

urlpatterns = router.urls
