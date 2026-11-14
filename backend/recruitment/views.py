from django.core.exceptions import (
    PermissionDenied as DjangoPermissionDenied,
    ValidationError as DjangoValidationError,
)
from drf_spectacular.utils import extend_schema

from rest_framework import status
from rest_framework.exceptions import (
    PermissionDenied as DRFPermissionDenied,
    ValidationError as DRFValidationError,
)
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from config.pagination import StandardResultsSetPagination

from recruitment.models import Candidate, JobPosting, JobApplication
from recruitment.permissions import IsActiveRecruitmentManager
from recruitment.serializers import (
    ApplicationStatusChangeSerializer,
    CandidateSerializer,
    CandidateCreateSerializer,
    JobApplicationAssignmentSerializer,
    JobApplicationSerializer,
    JobPostingSerializer,
    PublicJobPostingSerializer,
    ApplicationSubmissionResponseSerializer,
)
from recruitment.services.candidate import CandidateService
from recruitment.services.job_posting import JobPostingService
from recruitment.services.job_application import JobApplicationService
from recruitment.services.application_status import ApplicationStatusService

def execute_service(service_method, **kwargs):
    """Translate Django service exceptions into DRF exceptions."""

    try:
        return service_method(**kwargs)

    except DjangoPermissionDenied as exc:
        raise DRFPermissionDenied(str(exc)) from exc

    except DjangoValidationError as exc:
        detail = (
            exc.message_dict
            if hasattr(exc, "message_dict")
            else exc.messages
        )
        raise DRFValidationError(detail) from exc

class JobPostingCreateView(GenericAPIView):
    """Create job postings and publicly list open postings."""

    serializer_class = JobPostingSerializer
    pagination_class = StandardResultsSetPagination

    permission_classes = [
        IsAuthenticated,
        IsActiveRecruitmentManager,
    ]

    throttle_classes = [ScopedRateThrottle]

    def get_throttles(self):
        self.throttle_scope = (
            "public_job_list"
            if self.request.method == "GET"
            else "hr_recruitment"
        )
        return super().get_throttles()

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]

        return super().get_permissions()
    @extend_schema(
        operation_id="list_public_job_postings",
        responses={200: PublicJobPostingSerializer(many=True)},
    )
    def get(self, request):
        postings = JobPosting.objects.filter(
            status=JobPosting.Status.OPEN,
        ).select_related("department", "position")

        page = self.paginate_queryset(postings)

        serializer = PublicJobPostingSerializer(
            page,
            many=True,
        )

        return self.get_paginated_response(serializer.data)
    @extend_schema(
        operation_id="create_job_posting",
        request=JobPostingSerializer,
        responses={201: JobPostingSerializer},
    )
    def post(self, request):
        serializer = JobPostingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        posting = execute_service(
            JobPostingService.create_job_posting,
            actor=request.user,
            **serializer.validated_data,
        )

        return Response(
            JobPostingSerializer(posting).data,
            status=status.HTTP_201_CREATED,
        )

class JobPostingDetailView(APIView):
    """Update an existing recruitment job posting."""

    permission_classes = [
        IsAuthenticated,
        IsActiveRecruitmentManager,
    ]
    @extend_schema(
        request=JobPostingSerializer,
        responses={200: JobPostingSerializer},
    )
    def patch(self, request, posting_id):
        serializer = JobPostingSerializer(
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)

        posting = execute_service(
            JobPostingService.update_job_posting,
            posting_id=posting_id,
            actor=request.user,
            **serializer.validated_data,
        )

        return Response(
            JobPostingSerializer(posting).data,
            status=status.HTTP_200_OK,
        )

class JobPostingActionView(APIView):
    """Publish, close, or cancel a job posting."""
    serializer_class = JobPostingSerializer
    permission_classes = [
        IsAuthenticated,
        IsActiveRecruitmentManager,
    ]

    ACTIONS = {
        "publish": JobPostingService.publish_job_posting,
        "close": JobPostingService.close_job_posting,
        "cancel": JobPostingService.cancel_job_posting,
    }
    @extend_schema(
        operation_id="perform_job_posting_action",
        request=None,
        responses={200: JobPostingSerializer},
    )
    def post(self, request, posting_id, action):
        service_method = self.ACTIONS.get(action)

        if service_method is None:
            return Response(
                {"detail": "Invalid job posting action."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        posting = execute_service(
            service_method,
            posting_id=posting_id,
            actor=request.user,
        )

        return Response(
            JobPostingSerializer(posting).data,
            status=status.HTTP_200_OK,
        )

class CandidateListCreateView(GenericAPIView):
    """List and create external candidates."""

    serializer_class = CandidateSerializer
    pagination_class = StandardResultsSetPagination

    permission_classes = [
        IsAuthenticated,
        IsActiveRecruitmentManager,
    ]
    @extend_schema(
        operation_id="list_candidates",
        responses={200: CandidateSerializer(many=True)},
    )
    def get(self, request):
        candidates = execute_service(
            CandidateService.list_candidates,
            actor=request.user,
        )

        page = self.paginate_queryset(candidates)

        serializer = CandidateSerializer(
            page,
            many=True,
        )

        return self.get_paginated_response(serializer.data)
    @extend_schema(
        operation_id="create_candidate",
        request=CandidateCreateSerializer,
        responses={201: CandidateSerializer},
    )
    def post(self, request):
        serializer = CandidateCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        candidate = execute_service(
            CandidateService.create_candidate,
            actor=request.user,
            **serializer.validated_data,
        )

        return Response(
            CandidateSerializer(candidate).data,
            status=status.HTTP_201_CREATED,
        )

class CandidateDetailView(APIView):
    """Retrieve and update an external candidate."""

    permission_classes = [
        IsAuthenticated,
        IsActiveRecruitmentManager,
    ]
    @extend_schema(
        responses={200: CandidateSerializer},
    )
    def get(self, request, candidate_id):
        candidate = execute_service(
            CandidateService.get_candidate,
            candidate_id=candidate_id,
            actor=request.user,
        )

        return Response(
            CandidateSerializer(candidate).data,
            status=status.HTTP_200_OK,
        )
    @extend_schema(
        request=CandidateSerializer,
        responses={200: CandidateSerializer},
    )
    def patch(self, request, candidate_id):
        serializer = CandidateSerializer(
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)

        candidate = execute_service(
            CandidateService.update_candidate,
            candidate_id=candidate_id,
            actor=request.user,
            **serializer.validated_data,
        )

        return Response(
            CandidateSerializer(candidate).data,
            status=status.HTTP_200_OK,
        )

class JobApplicationListCreateView(GenericAPIView):
    """Submit public applications and list applications for HR users."""

    serializer_class = JobApplicationSerializer
    pagination_class = StandardResultsSetPagination

    permission_classes = [
        IsAuthenticated,
        IsActiveRecruitmentManager,
    ]
    throttle_classes = [ScopedRateThrottle]

    def get_throttles(self):
        self.throttle_scope = (
            "public_application_submit"
            if self.request.method == "POST"
            else "hr_recruitment"
        )
        return super().get_throttles()

    def get_permissions(self):
        if self.request.method == "POST":
            return [AllowAny()]

        return super().get_permissions()
    @extend_schema(
        operation_id="list_job_applications",
        responses={200: JobApplicationSerializer(many=True)},
    )
    def get(self, request):
        applications = execute_service(
            JobApplicationService.list_applications,
            actor=request.user,
        )

        page = self.paginate_queryset(applications)

        serializer = JobApplicationSerializer(
            page,
            many=True,
        )

        return self.get_paginated_response(serializer.data)
    @extend_schema(
        operation_id="submit_job_application",
        request=JobApplicationSerializer,
        responses={201: ApplicationSubmissionResponseSerializer},
    )
    def post(self, request):
        serializer = JobApplicationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        application = execute_service(
            JobApplicationService.submit_application,
            posting_id=serializer.validated_data["job_posting"].pk,
            candidate_data=serializer.validated_data["candidate_data"],
            cover_letter=serializer.validated_data.get(
                "cover_letter",
                "",
            ),
            privacy_consent=serializer.validated_data["privacy_consent"],
        )

        return Response(
            {"detail": "Your application has been submitted successfully."},
            status=status.HTTP_201_CREATED,
        )

class JobApplicationDetailView(APIView):
    """Retrieve a job application for authorized HR users."""

    permission_classes = [
        IsAuthenticated,
        IsActiveRecruitmentManager,
    ]
    @extend_schema(
        responses={200: JobApplicationSerializer},
    )
    def get(self, request, application_id):
        application = execute_service(
            JobApplicationService.get_application,
            application_id=application_id,
            actor=request.user,
        )

        serializer = JobApplicationSerializer(application)

        return Response(serializer.data)

class JobApplicationAssignmentView(APIView):
    """Assign an application to an authorized HR user."""

    permission_classes = [
        IsAuthenticated,
        IsActiveRecruitmentManager,
    ]
    @extend_schema(
        request=JobApplicationAssignmentSerializer,
        responses={200: JobApplicationSerializer},
    )
    def post(self, request, application_id):
        serializer = JobApplicationAssignmentSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        application = execute_service(
            JobApplicationService.assign_application,
            application_id=application_id,
            assigned_to_id=serializer.validated_data["assigned_to_id"],
            actor=request.user,
        )

        return Response(JobApplicationSerializer(application).data)

class JobApplicationStatusView(APIView):
    """Change the status of a job application."""

    permission_classes = [
        IsAuthenticated,
        IsActiveRecruitmentManager,
    ]
    @extend_schema(
        request=ApplicationStatusChangeSerializer,
        responses={200: JobApplicationSerializer},
    )
    def post(self, request, application_id):
        serializer = ApplicationStatusChangeSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        application = execute_service(
            ApplicationStatusService.change_status,
            application_id=application_id,
            new_status=serializer.validated_data["status"],
            actor=request.user,
            note=serializer.validated_data.get("note", ""),
        )

        return Response(JobApplicationSerializer(application).data)
