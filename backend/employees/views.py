from django.core.exceptions import ValidationError
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.models import AuditLog
from accounts.siem import create_security_event

from .models import (
    Department,
    EmployeeProfile,
    LeaveRequest,
    PayPeriod,
    Payroll,
    PayrollRecord,
    Earning,
    Deduction,
    Payment,
    BankAccount,
    PerformanceReview,
    Position,
)
from .permissions import (
    EmployeeProfilePermission,
    LeaveRequestPermission,
    BankAccountPermission,
    PerformanceReviewPermission,
)
from .serializers import (
    EmployeeProfileSerializer,
    LeaveRequestSerializer,
    BankAccountSerializer,
    PerformanceReviewSerializer,
)


class EmployeeProfileViewSet(viewsets.ModelViewSet):
    """API endpoint for managing employee profiles."""

    serializer_class = EmployeeProfileSerializer
    permission_classes = (
        EmployeeProfilePermission,
    )

    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
    )

    filterset_fields = (
        "department",
        "position",
        "hire_date",
    )

    ordering_fields = (
        "employee_id",
        "hire_date",
        "created_at",
        "updated_at",
    )

    def permission_denied(
        self,
        request,
        message=None,
        code=None,
    ):
        """Record authenticated unauthorized access attempts."""

        if request.user.is_authenticated:
            create_security_event(
                request=request,
                user=request.user,
                event_type="UNAUTHORIZED_ACCESS",
                details=(
                    f"Unauthorized access attempt by "
                    f"{request.user.role} user."
                ),
            )

        super().permission_denied(
            request,
            message=message,
            code=code,
        )

    def perform_create(self, serializer):
        """Create an employee and record the security event."""

        employee = serializer.save()

        create_security_event(
            request=self.request,
            user=self.request.user,
            event_type="EMPLOYEE_CREATED",
            details=(
                f"Employee {employee.employee_id} created."
            ),
        )

    def perform_update(self, serializer):
        """Update an employee and record the security event."""

        employee = serializer.save()

        create_security_event(
            request=self.request,
            user=self.request.user,
            event_type="EMPLOYEE_UPDATED",
            details=(
                f"Employee {employee.employee_id} updated."
            ),
        )

    def perform_destroy(self, instance):
        """Delete an employee and record the security event."""

        employee_id = instance.employee_id

        create_security_event(
            request=self.request,
            user=self.request.user,
            event_type="EMPLOYEE_DELETED",
            details=(
                f"Employee {employee_id} deleted."
            ),
        )

        instance.delete()

    def get_queryset(self):
        """Restrict employee list results to the authenticated user."""

        user = self.request.user

        if (
            user.is_authenticated
            and user.role == "EMPLOYEE"
            and self.action == "list"
        ):
            return EmployeeProfile.objects.filter(
                user=user
            )

        return EmployeeProfile.objects.all()


class LeaveRequestViewSet(viewsets.ModelViewSet):
    """API endpoint for managing employee leave requests."""

    serializer_class = LeaveRequestSerializer
    permission_classes = (
        LeaveRequestPermission,
    )

    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
    )

    filterset_fields = (
        "leave_type",
        "status",
        "start_date",
        "end_date",
        "employee",
    )

    ordering_fields = (
        "start_date",
        "end_date",
        "created_at",
        "updated_at",
    )

    def permission_denied(
        self,
        request,
        message=None,
        code=None,
    ):
        """Record unauthorized leave request access."""

        if request.user.is_authenticated:
            create_security_event(
                request=request,
                user=request.user,
                event_type="UNAUTHORIZED_ACCESS",
                details=(
                    f"Unauthorized leave request access "
                    f"attempt by {request.user.role} user."
                ),
            )

        super().permission_denied(
            request,
            message=message,
            code=code,
        )

    def destroy(self, request, *args, **kwargs):
        """Prevent direct deletion of leave requests."""

        return Response(
            {
                "detail": (
                    "Leave requests cannot be deleted. "
                    "Use the cancel action for pending requests."
                )
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def get_queryset(self):
        """Restrict employees to their own leave requests."""

        user = self.request.user

        queryset = LeaveRequest.objects.select_related(
            "employee",
            "employee__user",
            "reviewed_by",
        )

        if (
            user.is_authenticated
            and user.role == "EMPLOYEE"
        ):
            return queryset.filter(
                employee__user=user
            )

        return queryset

    def perform_create(self, serializer):
        """Create a leave request and record the event."""

        if self.request.user.role == "EMPLOYEE":
            employee = EmployeeProfile.objects.get(
                user=self.request.user
            )

            leave_request = serializer.save(
                employee=employee
            )
        else:
            leave_request = serializer.save()

        AuditLog.objects.create(
            user=self.request.user,
            action="LEAVE_REQUEST_CREATED",
            details=(
                f"Leave request {leave_request.id} created "
                f"for {leave_request.employee.employee_id}."
            ),
        )

        create_security_event(
            request=self.request,
            user=self.request.user,
            event_type="LEAVE_REQUEST_CREATED",
            details=(
                f"Leave request {leave_request.id} created "
                f"for {leave_request.employee.employee_id}."
            ),
        )

    @action(
        detail=True,
        methods=["post"],
    )
    def approve(self, request, pk=None):
        """Approve a pending leave request."""

        leave_request = self.get_object()

        try:
            leave_request.approve(
                reviewer=request.user
            )
        except ValidationError as exc:
            return Response(
                {
                    "detail": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        AuditLog.objects.create(
            user=request.user,
            action="LEAVE_REQUEST_APPROVED",
            details=(
                f"Leave request {leave_request.id} "
                f"approved for "
                f"{leave_request.employee.employee_id}."
            ),
        )

        create_security_event(
            request=request,
            user=request.user,
            event_type="LEAVE_REQUEST_APPROVED",
            details=(
                f"Leave request {leave_request.id} "
                f"approved for "
                f"{leave_request.employee.employee_id}."
            ),
        )

        return Response(
            self.get_serializer(
                leave_request
            ).data
        )

    @action(
        detail=True,
        methods=["post"],
    )
    def reject(self, request, pk=None):
        """Reject a pending leave request."""

        leave_request = self.get_object()

        try:
            leave_request.reject(
                reviewer=request.user
            )
        except ValidationError as exc:
            return Response(
                {
                    "detail": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        AuditLog.objects.create(
            user=request.user,
            action="LEAVE_REQUEST_REJECTED",
            details=(
                f"Leave request {leave_request.id} "
                f"rejected for "
                f"{leave_request.employee.employee_id}."
            ),
        )

        create_security_event(
            request=request,
            user=request.user,
            event_type="LEAVE_REQUEST_REJECTED",
            details=(
                f"Leave request {leave_request.id} "
                f"rejected for "
                f"{leave_request.employee.employee_id}."
            ),
        )

        return Response(
            self.get_serializer(
                leave_request
            ).data
        )

    @action(
        detail=True,
        methods=["post"],
    )
    def cancel(self, request, pk=None):
        """Cancel a pending leave request."""

        leave_request = self.get_object()

        try:
            leave_request.cancel()
        except ValidationError as exc:
            return Response(
                {
                    "detail": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        AuditLog.objects.create(
            user=request.user,
            action="LEAVE_REQUEST_CANCELLED",
            details=(
                f"Leave request {leave_request.id} "
                f"cancelled for "
                f"{leave_request.employee.employee_id}."
            ),
        )

        create_security_event(
            request=request,
            user=request.user,
            event_type="LEAVE_REQUEST_CANCELLED",
            details=(
                f"Leave request {leave_request.id} "
                f"cancelled for "
                f"{leave_request.employee.employee_id}."
            ),
        )

        return Response(
            self.get_serializer(
                leave_request
            ).data
        )

class BankAccountViewSet(viewsets.ModelViewSet):
    """Manage employee bank account information securely."""

    queryset = BankAccount.objects.select_related(
        "employee",
        "employee__user",
    ).all()

    serializer_class = BankAccountSerializer
    permission_classes = (
        BankAccountPermission,
    )
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
    )

    filterset_fields = (
        "account_type",
        "is_primary",
        "is_verified",
        "employee",
    )

    ordering_fields = (
        "created_at",
        "updated_at",
        "last_four",
    )
    def get_queryset(self):
        """Limit employees to their own bank accounts."""

        queryset = super().get_queryset()

        if self.request.user.role == "EMPLOYEE":
            queryset = queryset.filter(
                employee__user=self.request.user,
            )

        return queryset

    def create(self, request, *args, **kwargs):
        """Create a bank account with secure access control."""

        if request.user.role == "EMPLOYEE":
            if not hasattr(
                request.user,
                "employee_profile",
            ):
                create_security_event(
                    request,
                    "UNAUTHORIZED_ACCESS",
                    details=(
                        "Employee attempted to create a "
                        "bank account without an employee profile."
                    ),
                    user=request.user,
                )

                return Response(
                    {
                        "detail": (
                            "Employee profile is required."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            data = request.data.copy()
            data["employee"] = (
                request.user.employee_profile.id
            )

            serializer = self.get_serializer(
                data=data,
            )
        else:
            serializer = self.get_serializer(
                data=request.data,
            )

        serializer.is_valid(raise_exception=True)

        self.perform_create(serializer)

        headers = self.get_success_headers(
            serializer.data,
        )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def perform_create(self, serializer):
        """Create the bank account."""

        bank_account = serializer.save()

        create_security_event(
            self.request,
            "ACCOUNT_CHANGE",
            details=(
                "Bank account created for employee "
                f"{bank_account.employee.employee_id}."
            ),
            user=self.request.user,
        )

    def perform_update(self, serializer):
        """Update the bank account."""

        bank_account = serializer.save()

        create_security_event(
            self.request,
            "ACCOUNT_CHANGE",
            details=(
                "Bank account updated for employee "
                f"{bank_account.employee.employee_id}."
            ),
            user=self.request.user,
        )

    def destroy(self, request, *args, **kwargs):
        """Prevent physical deletion of bank accounts."""

        return Response(
            {
                "detail": (
                    "Bank accounts cannot be deleted. "
                    "Use account replacement or deactivation."
                )
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

class PerformanceReviewViewSet(viewsets.ModelViewSet):
    """Manage employee performance reviews securely."""

    queryset = PerformanceReview.objects.select_related(
        "employee",
        "employee__user",
        "reviewer",
    ).all()

    serializer_class = PerformanceReviewSerializer
    permission_classes = (
        PerformanceReviewPermission,
    )

    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
    )

    filterset_fields = (
        "employee",
        "reviewer",
        "status",
        "review_period_start",
        "review_period_end",
    )

    ordering_fields = (
        "review_period_start",
        "review_period_end",
        "score",
        "created_at",
        "updated_at",
    )

    def get_queryset(self):
        """Limit employees to their own performance reviews."""

        queryset = super().get_queryset()

        if self.request.user.role == "EMPLOYEE":
            queryset = queryset.filter(
                employee__user=self.request.user,
            )

        return queryset

    def create(self, request, *args, **kwargs):
        """Create a performance review securely."""

        if request.user.role == "EMPLOYEE":
            employee_id = request.data.get("employee")

            try:
                employee = EmployeeProfile.objects.get(
                    pk=employee_id,
                )
            except (EmployeeProfile.DoesNotExist, TypeError, ValueError):
                return Response(
                    {
                        "detail": (
                            "Invalid employee."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            if employee.user != request.user:
                return Response(
                    {
                        "detail": (
                            "Employees can only create "
                            "reviews for themselves."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        serializer = self.get_serializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        self.perform_create(serializer)

        headers = self.get_success_headers(
            serializer.data,
        )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def perform_create(self, serializer):
        """Create a review and record the security event."""

        review = serializer.save(
            reviewer=self.request.user,
        )

        create_security_event(
            self.request,
            "ACCOUNT_CHANGE",
            details=(
                "Performance review created for employee "
                f"{review.employee.employee_id}."
            ),
            user=self.request.user,
        )

    def perform_update(self, serializer):
        """Update a performance review."""

        review = serializer.save()

        create_security_event(
            self.request,
            "ACCOUNT_CHANGE",
            details=(
                "Performance review updated for employee "
                f"{review.employee.employee_id}."
            ),
            user=self.request.user,
        )

    def destroy(self, request, *args, **kwargs):
        """Prevent physical deletion of performance reviews."""

        return Response(
            {
                "detail": (
                    "Performance reviews cannot be deleted."
                )
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(
        detail=True,
        methods=["post"],
    )
    def submit(self, request, pk=None):
        """Submit a draft performance review."""

        review = self.get_object()

        if review.status != "DRAFT":
            return Response(
                {
                    "detail": (
                        "Only draft performance reviews "
                        "can be submitted."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        review.status = "SUBMITTED"
        review.submitted_at = timezone.now()
        review.save()

        create_security_event(
            request,
            "ACCOUNT_CHANGE",
            details=(
                "Performance review submitted for employee "
                f"{review.employee.employee_id}."
            ),
            user=request.user,
        )

        return Response(
            self.get_serializer(review).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["post"],
    )
    def acknowledge(self, request, pk=None):
        """Acknowledge a submitted performance review."""

        review = self.get_object()

        if review.status != "SUBMITTED":
            return Response(
                {
                    "detail": (
                        "Only submitted performance reviews "
                        "can be acknowledged."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        review.status = "ACKNOWLEDGED"
        review.save()

        create_security_event(
            request,
            "ACCOUNT_CHANGE",
            details=(
                "Performance review acknowledged for employee "
                f"{review.employee.employee_id}."
            ),
            user=request.user,
        )

        return Response(
            self.get_serializer(review).data,
            status=status.HTTP_200_OK,
        )
