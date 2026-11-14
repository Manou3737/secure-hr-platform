import hashlib
import uuid
from django.http import FileResponse, Http404
from django.db.models import Q
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.filters import OrderingFilter
from rest_framework import status, viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.filters import SearchFilter
from rest_framework.views import APIView

from accounts.models import AuditLog
from accounts.siem import create_security_event
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    OpenApiResponse,
)
from employees.permissions import (
    HRDocumentDownloadPermission,
    HRDocumentPermission,
    OnboardingJourneyPermission,
    OnboardingTaskPermission,
    DashboardPermission,
)
from employees.storage import hr_document_storage
from employees.services.task_assignment import TaskAssignmentService
from employees.services.workflow_engine import WorkflowEngine
from employees.services.document_version import DocumentVersionService
from employees.services.document_review import DocumentReviewService
from employees.services.document_audit import DocumentAuditService
from employees.filters import DocumentAccessLogFilter
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
    HRDocument,
    DocumentReview,
    OnboardingJourney,
    OnboardingTask,
    DocumentAccessLog,
)
from .permissions import (
    EmployeeProfilePermission,
    LeaveRequestPermission,
    BankAccountPermission,
    PerformanceReviewPermission,
    DocumentAccessLogPermission,
)
from .serializers import (
    EmployeeProfileSerializer,
    LeaveRequestSerializer,
    BankAccountSerializer,
    PerformanceReviewSerializer,
    HRDocumentSerializer,
    DocumentVersionSerializer,
    DocumentReviewSerializer,
    DocumentAccessLogSerializer,
    OnboardingJourneySerializer,
    OnboardingTaskSerializer,
    OnboardingTaskAssignmentSerializer,
    OnboardingTaskTransitionSerializer,
    DashboardFilterSerializer,
    DashboardResponseSerializer,
)
from employees.services.document_access import DocumentAccessService
from employees.services.dashboard.dashboard_service import DashboardService

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

        queryset = EmployeeProfile.objects.all()

        if (
            user.is_authenticated
            and user.role == "EMPLOYEE"
            and self.action == "list"
        ):
            queryset = queryset.filter(user=user)

        return queryset.order_by("-created_at", "-id")

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
        """Restrict leave requests according to user role and department."""

        if getattr(self, "swagger_fake_view", False):
            return LeaveRequest.objects.none()
        user = self.request.user

        queryset = LeaveRequest.objects.select_related(
            "employee",
            "employee__user",
            "employee__department",
            "reviewed_by",
        ).order_by("-created_at", "-id")

        if user.role == "EMPLOYEE":
            return queryset.filter(
                employee__user=user
            )

        if user.role == "HR_MANAGER":
            try:
                manager_profile = user.employee_profile
            except EmployeeProfile.DoesNotExist:
                raise DRFPermissionDenied(
                    "An employee profile is required for HR managers."
                )

            return queryset.filter(
                employee__department_id=manager_profile.department_id
            )

        # HR_ADMIN and SUPER_ADMIN retain global access.
        return queryset

    def create(self, request, *args, **kwargs):
        """Reject employees without profiles before serializer validation."""

        if request.user.role == "EMPLOYEE":
            if not EmployeeProfile.objects.filter(
                user=request.user
            ).exists():
                self.permission_denied(
                    request,
                    message=(
                        "An employee profile is required to submit "
                        "a leave request."
                    ),
                )

        return super().create(
            request,
            *args,
            **kwargs,
        )


    def perform_create(self, serializer):
        """Create a leave request and record the event."""

        if self.request.user.role == "EMPLOYEE":
            try:
                employee = EmployeeProfile.objects.get(
                    user=self.request.user
                )
            except EmployeeProfile.DoesNotExist:
                raise DRFPermissionDenied(
                    "An employee profile is required to submit "
                    "a leave request."
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
    ).order_by("-created_at", "-id")

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
        """Limit bank account access by employee role and department."""

        queryset = super().get_queryset()
        user = self.request.user

        if user.role == "EMPLOYEE":
            queryset = queryset.filter(
                employee__user=user,
            )

        elif user.role == "HR_MANAGER":
            try:
                manager_department_id = (
                    user.employee_profile.department_id
                )
            except EmployeeProfile.DoesNotExist:
                raise DRFPermissionDenied(
                    "An employee profile is required."
                )

            if manager_department_id is None:
                raise DRFPermissionDenied(
                    "A department is required."
                )

            queryset = queryset.filter(
                employee__department_id=manager_department_id,
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
    ).order_by("-created_at", "-id")

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
        """Update a performance review according to its status."""

        review = self.get_object()
        user = self.request.user

        if (
            review.status in ("SUBMITTED", "ACKNOWLEDGED")
            and user.role not in ("SUPER_ADMIN", "HR_ADMIN", "HR_MANAGER")
        ):
            raise DRFValidationError(
                "Only authorized HR users can correct "
                "a submitted or acknowledged review."
            )

        review = serializer.save()

        create_security_event(
            self.request,
            "ACCOUNT_CHANGE",
            details=(
                "Performance review updated for employee "
                f"{review.employee.employee_id}."
            ),
            user=user,
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

class HRDocumentViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Expose authorized HR document metadata operations."""

    serializer_class = HRDocumentSerializer
    permission_classes = (HRDocumentPermission,)

    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
    )

    filterset_fields = (
        "document_type",
        "status",
        "employee",
    )

    ordering_fields = (
        "uploaded_at",
        "updated_at",
        "expires_at",
        "document_type",
        "status",
    )

    def get_queryset(self):
        """Return only documents accessible to the current user."""

        user = self.request.user

        queryset = DocumentAccessService.get_accessible_documents(
            user
        )

        return queryset.select_related(
            "employee",
            "employee__user",
            "uploaded_by",
            "verified_by",
        )
    def retrieve(self, request, *args, **kwargs):
        """Retrieve document metadata and record the access."""
        document = self.get_object()

        DocumentAuditService.record(
            request=request,
            action=DocumentAccessLog.Action.VIEW,
            document=document,
            details="HR document metadata viewed.",
        )

        serializer = self.get_serializer(document)
        return Response(serializer.data)
    @action(
        detail=True,
        methods=["get"],
        permission_classes=[HRDocumentDownloadPermission],
    )
    def download(self, request, pk=None):
        """Download a verified HR document as an attachment."""
        document = self.get_object()

        # Defense in depth: never open an unverified file.
        if document.status != HRDocument.Status.VERIFIED:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                "This document is not available for download."
            )

        try:
            file_handle = hr_document_storage.open(
                document.storage_key,
                "rb",
            )
        except Exception as exc:
            raise Http404(
                "The requested document is unavailable."
            ) from exc

        filename = (
            document.original_filename
            .split("/")[-1]
            .split("\\")[-1]
        )
        DocumentAuditService.record(
            request=request,
            action=DocumentAccessLog.Action.DOWNLOAD,
            document=document,
            details="Verified HR document downloaded.",
        )
        return FileResponse(
            file_handle,
            as_attachment=True,
            filename=filename,
            content_type="application/octet-stream",
        )

    @action(detail=True, methods=["get"], url_path="versions")
    def versions(self, request, pk=None):
        """List version metadata for an accessible HR document."""
        document = self.get_object()

        versions = document.versions.order_by("-version_number")

        serializer = DocumentVersionSerializer(
            versions,
            many=True,
            context=self.get_serializer_context(),
        )

        return Response(serializer.data, status=status.HTTP_200_OK)
    @action(detail=True, methods=["get"], url_path="reviews")
    def reviews(self, request, pk=None):
        """List review history for an accessible HR document."""
        document = self.get_object()

        reviews = document.reviews.select_related(
            "reviewer",
            "version",
        ).order_by("-reviewed_at")

        serializer = DocumentReviewSerializer(
            reviews,
            many=True,
            context=self.get_serializer_context(),
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )
    @action(
        detail=True,
        methods=["post"],
        url_path="create-version",
        parser_classes = [MultiPartParser, FormParser],
    )
    def create_version(self, request, pk=None):
        """Create a new private version of an accessible HR document."""
        document = self.get_object()

        uploaded_file = request.FILES.get("file")
        if uploaded_file is None:
            raise DRFValidationError({
                "file": "This field is required."
            })

        try:
            version = DocumentVersionService.create_version(
                document_id=document.pk,
                uploaded_file=uploaded_file,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise DRFValidationError({
                "file": exc.messages,
            }) from exc

        serializer = DocumentVersionSerializer(
            version,
            context=self.get_serializer_context(),
        )
        DocumentAuditService.record(
            request=request,
            action=DocumentAccessLog.Action.CREATE_VERSION,
            document=document,
            details="New HR document version created.",
        )
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )

    def perform_create(self, serializer):
        """Create a document for an authorized employee."""
        user = self.request.user

        if user.role == "EMPLOYEE":
            try:
                employee = EmployeeProfile.objects.get(user=user)
            except EmployeeProfile.DoesNotExist:
                raise DRFValidationError(
                    "No employee profile is associated with this account."
                )
        else:
            employee_id = self.request.data.get("employee")

            if not employee_id:
                raise DRFValidationError(
                    {"employee": "This field is required."}
                )

            try:
                employee = EmployeeProfile.objects.get(pk=employee_id)
            except (
                EmployeeProfile.DoesNotExist,
                ValidationError,
                ValueError,
                TypeError,
            ):
                raise DRFValidationError(
                    {"employee": "Invalid employee profile."}
                )

        document = serializer.save(
            employee=employee,
            uploaded_by=user,
        )

        create_security_event(
            self.request,
            "ACCOUNT_CHANGE",
            details=(
                f"HR document uploaded: {document.pk}."
            ),
            user=user,
        )
        DocumentAuditService.record(
            request=self.request,
            action=DocumentAccessLog.Action.CREATE,
            document=document,
            details="HR document uploaded.",
        )
    def perform_update(self, serializer):
        """Save metadata changes and record a security event."""

        document = serializer.save()

        create_security_event(
            self.request,
            "ACCOUNT_CHANGE",
            details=(
                "HR document metadata updated for document "
                f"{document.pk}."
            ),
            user=self.request.user,
        )
        DocumentAuditService.record(
            request=self.request,
            action=DocumentAccessLog.Action.UPDATE,
            document=document,
            details="HR document metadata updated.",
        )
    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        """Verify a document pending HR review and record the decision."""

        document = self.get_object()

        try:
            DocumentReviewService.review_document(
                document_id=document.pk,
                actor=request.user,
                decision=DocumentReview.Decision.APPROVED,
            )
        except DjangoPermissionDenied as exc:
            raise DRFPermissionDenied(str(exc)) from exc
        except DjangoValidationError as exc:
            detail = (
                exc.messages
                if hasattr(exc, "messages")
                else str(exc)
            )
            raise DRFValidationError({"detail": detail}) from exc

        document.refresh_from_db()

        details = (
            f"HR document {document.pk} verified "
            f"for employee {document.employee.employee_id}."
        )

        AuditLog.objects.create(
            user=request.user,
            action="HR_DOCUMENT_VERIFIED",
            details=details,
        )

        create_security_event(
            request=request,
            user=request.user,
            event_type="HR_DOCUMENT_VERIFIED",
            details=details,
        )
        DocumentAuditService.record(
            request=request,
            action=DocumentAccessLog.Action.VERIFY,
            document=document,
            details="HR document verified.",
        )
        return Response(
            self.get_serializer(document).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """Reject a document and record the review decision."""

        document = self.get_object()
        reason = request.data.get("reason")

        if not isinstance(reason, str) or not reason.strip():
            return Response(
                {"reason": "A non-empty rejection reason is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reason = reason.strip()

        try:
            DocumentReviewService.review_document(
                document_id=document.pk,
                actor=request.user,
                decision=DocumentReview.Decision.REJECTED,
                comment=reason,
            )
        except DjangoPermissionDenied as exc:
            raise DRFPermissionDenied(str(exc)) from exc
        except DjangoValidationError as exc:
            detail = (
                exc.messages
                if hasattr(exc, "messages")
                else str(exc)
            )
            raise DRFValidationError({"detail": detail}) from exc

        document.refresh_from_db()

        details = (
            f"HR document {document.pk} rejected "
            f"for employee {document.employee.employee_id}."
        )

        AuditLog.objects.create(
            user=request.user,
            action="HR_DOCUMENT_REJECTED",
            details=details,
        )

        create_security_event(
            request=request,
            user=request.user,
            event_type="HR_DOCUMENT_REJECTED",
            details=details,
        )
        DocumentAuditService.record(
            request=request,
            action=DocumentAccessLog.Action.REJECT,
            document=document,
            details="HR document rejected.",
        )
        return Response(
            self.get_serializer(document).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        """Archive a verified or rejected HR document."""
        document = self.get_object()

        if document.status not in ("VERIFIED", "REJECTED"):
            return Response(
                {
                    "detail": (
                        "Only verified or rejected documents "
                        "can be archived."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        document.status = "ARCHIVED"
        document.save(update_fields=["status", "updated_at"])

        details = (
            f"HR document {document.pk} archived "
            f"for employee {document.employee.employee_id}."
        )

        AuditLog.objects.create(
            user=request.user,
            action="HR_DOCUMENT_ARCHIVED",
            details=details,
        )

        create_security_event(
            request=request,
            user=request.user,
            event_type="HR_DOCUMENT_ARCHIVED",
            details=details,
        )
        DocumentAuditService.record(
            request=request,
            action=DocumentAccessLog.Action.ARCHIVE,
            document=document,
            details="HR document archived.",
        )
        return Response(
            self.get_serializer(document).data,
            status=status.HTTP_200_OK,
        )
@extend_schema_view(
    retrieve=extend_schema(
        parameters=[
            OpenApiParameter(
                name="id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                required=True,
            ),
        ],
    ),
)
class OnboardingJourneyViewSet(viewsets.ReadOnlyModelViewSet):
    """Expose onboarding journeys with role-based queryset filtering."""

    serializer_class = OnboardingJourneySerializer
    permission_classes = (OnboardingJourneyPermission,)

    def get_queryset(self):
        user = self.request.user

        queryset = OnboardingJourney.objects.select_related(
            "employee__user",
        )

        if user.role in {
            "SUPER_ADMIN",
            "HR_ADMIN",
            "HR_MANAGER",
        }:
            return queryset

        if user.role == "EMPLOYEE":
            return queryset.filter(employee__user_id=user.pk)

        return queryset.none()
@extend_schema_view(
    retrieve=extend_schema(
        parameters=[
            OpenApiParameter(
                name="id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                required=True,
            ),
        ],
    ),
    assign=extend_schema(
        parameters=[
            OpenApiParameter(
                name="id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                required=True,
            ),
        ],
    ),
    transition=extend_schema(
        parameters=[
            OpenApiParameter(
                name="id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                required=True,
            ),
        ],
    ),
)
class OnboardingTaskViewSet(viewsets.GenericViewSet):
    """Expose onboarding tasks and controlled workflow operations."""

    serializer_class = OnboardingTaskSerializer
    permission_classes = (OnboardingTaskPermission,)

    def get_queryset(self):
        user = self.request.user

        queryset = OnboardingTask.objects.select_related(
            "journey__employee__user",
            "assigned_to",
        )

        if user.role in {
            "SUPER_ADMIN",
            "HR_ADMIN",
            "HR_MANAGER",
        }:
            return queryset

        if user.role == "EMPLOYEE":
            return queryset.filter(
                Q(journey__employee__user_id=user.pk)
                | Q(assigned_to_id=user.pk)
            ).distinct()

        return queryset.none()

    def get_serializer_class(self):
        if getattr(self, "action", None) == "assign":
            return OnboardingTaskAssignmentSerializer

        if getattr(self, "action", None) == "transition":
            return OnboardingTaskTransitionSerializer

        return OnboardingTaskSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = OnboardingTaskSerializer(
                page,
                many=True,
                context=self.get_serializer_context(),
            )
            return self.get_paginated_response(serializer.data)

        serializer = OnboardingTaskSerializer(
            queryset,
            many=True,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        task = self.get_object()
        serializer = OnboardingTaskSerializer(
            task,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        task = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            task = TaskAssignmentService.assign_task(
                task_id=task.pk,
                assigned_to_id=serializer.validated_data["assigned_to_id"],
                actor=request.user,
            )
        except DjangoValidationError as exc:
            detail = (
                exc.message_dict
                if hasattr(exc, "message_dict")
                else exc.messages
            )
            raise ValidationError(detail) from exc

        return Response(
            OnboardingTaskSerializer(
                task,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        task = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            task = WorkflowEngine.transition_task(
                task_id=task.pk,
                target_status=serializer.validated_data["target_status"],
                actor=request.user,
            )
        except DjangoValidationError as exc:
            detail = (
                exc.message_dict
                if hasattr(exc, "message_dict")
                else exc.messages
            )
            raise ValidationError(detail) from exc

        return Response(
            OnboardingTaskSerializer(
                task,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_200_OK,
        )


class DocumentAccessLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only API for authorized HR staff to inspect document audit logs."""

    queryset = DocumentAccessLog.objects.select_related(
        "user",
        "document",
        "document__employee",
    ).all()

    serializer_class = DocumentAccessLogSerializer
    permission_classes = (DocumentAccessLogPermission,)

    filter_backends = (
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    )
    filterset_class = DocumentAccessLogFilter

    search_fields = (
        "request_path",
        "details",
        "user__email",
        "user__name",
    )

    ordering_fields = (
        "created_at",
        "action",
        "user__email",
    )
    ordering = ("-created_at",)

    def get_queryset(self):
        """Restrict HR managers to their own department's document logs."""

        queryset = super().get_queryset()
        user = self.request.user

        if user.role == "HR_MANAGER":
            try:
                manager_profile = user.employee_profile
            except EmployeeProfile.DoesNotExist:
                raise DRFPermissionDenied(
                    "An employee profile is required for HR managers."
                )

            if manager_profile.department_id is None:
                raise DRFPermissionDenied(
                    "A department is required for HR managers."
                )

            queryset = queryset.filter(
                document__employee__department_id=(
                    manager_profile.department_id
                )
            )

        # HR_ADMIN and SUPER_ADMIN retain global access.
        return queryset


class DashboardView(APIView):
    """
    Read-only API endpoint for aggregated HR dashboard metrics.

    HR managers are restricted to their own department.
    Super admins and HR admins retain global access.
    """

    permission_classes = (DashboardPermission,)

    @extend_schema(
        operation_id="employees_dashboard_retrieve",
        summary="Retrieve HR dashboard metrics",
        description=(
            "Returns aggregated HR dashboard metrics across workforce, "
            "compliance, onboarding, operations, security, audit, risk, "
            "and recruitment. Recruitment metrics include job posting "
            "and application status distributions, applications received, "
            "hires during the selected period, and daily application activity. "
            "No candidate personal information is exposed. "
            "SUPER_ADMIN and HR_ADMIN users can access global data or filter "
            "by department. HR_MANAGER users are restricted to their own "
            "department. An HR_MANAGER cannot request another department."
        ),
        parameters=[
            OpenApiParameter(
                name="department_id",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter dashboard metrics by department ID.",
            ),
            OpenApiParameter(
                name="as_of",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Reference date in YYYY-MM-DD format. Future dates are rejected.",
            ),
            OpenApiParameter(
                name="days",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Analysis period in days (1–365). Defaults to 7.",
            ),
            OpenApiParameter(
                name="recent_limit",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Maximum number of recent records (1–100). Defaults to 10.",
            ),
        ],
        responses={
            200: DashboardResponseSerializer,
            400: OpenApiResponse(
                description="Invalid query parameters.",
            ),
            401: OpenApiResponse(
                description="Authentication credentials were not provided or are invalid.",
            ),
            403: OpenApiResponse(
                description="The user does not have dashboard access or requested a forbidden department.",
            ),
        },
        tags=["HR Dashboard"],
    )
    def get(self, request):
        """
        Validate filters, enforce department scope,
        and return aggregated dashboard metrics.
        """

        serializer = DashboardFilterSerializer(
            data=request.query_params
        )
        serializer.is_valid(raise_exception=True)

        dashboard_filters = dict(serializer.validated_data)

        if request.user.role == "HR_MANAGER":
            try:
                manager_profile = request.user.employee_profile
            except EmployeeProfile.DoesNotExist:
                raise DRFPermissionDenied(
                    "HR managers must have an employee profile "
                    "with an assigned department."
                )

            manager_department_id = manager_profile.department_id

            if manager_department_id is None:
                raise DRFPermissionDenied(
                    "HR managers must have an employee profile "
                    "with an assigned department."
                )

            requested_department_id = dashboard_filters.get(
                "department_id"
            )

            if (
                requested_department_id is not None
                and requested_department_id != manager_department_id
            ):
                raise DRFPermissionDenied(
                    "You can only access dashboard data "
                    "for your own department."
                )

            dashboard_filters["department_id"] = manager_department_id

        dashboard_data = DashboardService.get_dashboard(
            **dashboard_filters
        )

        # HR managers can view aggregated security metrics,
        # but not individual IP addresses or request paths.
        if request.user.role == "HR_MANAGER":
            security_metrics = dashboard_data.get("security", {})

            for event in security_metrics.get("recent_events", []):
                event["ip_address"] = None
                event["request_path"] = ""

        return Response(
            dashboard_data,
            status=status.HTTP_200_OK,
        )
