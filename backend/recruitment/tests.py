from datetime import date, timedelta
from decimal import Decimal
from copy import deepcopy

from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from django.urls import reverse
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.exceptions import PermissionDenied

from accounts.models import AuditLog
from types import SimpleNamespace
from rest_framework.test import APIClient
from rest_framework import status
from recruitment.permissions import (
    IsActiveRecruitmentManager,
    IsRecruitmentAdmin,
)
from recruitment.services.job_posting import JobPostingService
from recruitment.services.candidate import CandidateService
from recruitment.services.job_application import JobApplicationService
from recruitment.services.application_status import ApplicationStatusService

from recruitment.serializers import (
    ApplicationStatusHistorySerializer,
    CandidateSerializer,
    JobApplicationSerializer,
    JobPostingSerializer,
)

from employees.models import Department, Position, EmployeeProfile

from .models import (
    ApplicationStatusHistory,
    Candidate,
    JobApplication,
    JobPosting,
)
from unittest.mock import patch

User = get_user_model()


class RecruitmentBaseTestCase(TestCase):
    """Shared fixtures for recruitment model tests."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="hr.admin@example.com",
            name="HR Administrator",
            password="StrongPassword123!",
            role="HR_ADMIN",
        )

        self.department = Department.objects.create(
            name="Human Resources",
            code="HR",
        )

        self.position = Position.objects.create(
            title="Recruitment Specialist",
            department=self.department,
        )

        self.candidate = Candidate.objects.create(
            first_name="John",
            last_name="Smith",
            email="john.smith@example.com",
            department=self.department,
        )

        self.job_posting = JobPosting.objects.create(
            title="Recruitment Specialist",
            department=self.department,
            position=self.position,
            description="Manage recruitment activities.",
            employment_type=JobPosting.EmploymentType.FULL_TIME,
            created_by=self.user,
        )

class CandidateModelTests(RecruitmentBaseTestCase):
    """Tests for external candidate profiles."""

    def test_create_candidate(self):
        self.assertEqual(self.candidate.first_name, "John")
        self.assertEqual(
            self.candidate.email,
            "john.smith@example.com",
        )

    def test_candidate_string_representation(self):
        self.assertEqual(str(self.candidate), "John Smith")

    def test_email_is_unique_case_insensitively(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Candidate.objects.create(
                    first_name="Jane",
                    last_name="Smith",
                    email="JOHN.SMITH@EXAMPLE.COM",
                    department=self.department,
                )

    def test_clean_normalizes_email(self):
        candidate = Candidate(
            first_name="Jane",
            last_name="Doe",
            email="  JANE.DOE@EXAMPLE.COM  ",
            department=self.department,
        )

        candidate.full_clean()

        self.assertEqual(
            candidate.email,
            "jane.doe@example.com",
        )

    def test_same_email_is_allowed_in_different_departments(self):
        other_department = Department.objects.create(
            name="Finance",
            code="FIN",
        )

        candidate = Candidate.objects.create(
            first_name="John",
            last_name="Smith",
            email="john.smith@example.com",
            department=other_department,
        )

        self.assertNotEqual(candidate.pk, self.candidate.pk)
        self.assertEqual(candidate.email, self.candidate.email)

class JobPostingModelTests(RecruitmentBaseTestCase):
    """Tests for job postings."""

    def test_create_job_posting(self):
        self.assertEqual(
            self.job_posting.status,
            JobPosting.Status.DRAFT,
        )

        self.assertEqual(
            self.job_posting.department,
            self.department,
        )

    def test_job_posting_string_representation(self):
        self.assertEqual(
            str(self.job_posting),
            "Recruitment Specialist",
        )

    def test_position_must_belong_to_selected_department(self):
        another_department = Department.objects.create(
            name="Finance",
            code="FIN",
        )

        another_position = Position.objects.create(
            title="Financial Analyst",
            department=another_department,
        )

        posting = JobPosting(
            title="Invalid Posting",
            department=self.department,
            position=another_position,
            description="Test description.",
            employment_type=JobPosting.EmploymentType.FULL_TIME,
            created_by=self.user,
        )

        with self.assertRaises(ValidationError):
            posting.full_clean()

    def test_deadline_cannot_precede_publication_date(self):
        publication_date = timezone.now()

        posting = JobPosting(
            title="Deadline Test",
            department=self.department,
            position=self.position,
            description="Test description.",
            employment_type=JobPosting.EmploymentType.FULL_TIME,
            created_by=self.user,
            published_at=publication_date,
            application_deadline=(
                publication_date.date() - timedelta(days=1)
            ),
        )

        with self.assertRaises(ValidationError):
            posting.full_clean()

    def test_salary_max_cannot_be_lower_than_salary_min(self):
        # The database constraint must reject this invalid range.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                JobPosting.objects.create(
                    title="Salary Test",
                    department=self.department,
                    position=self.position,
                    description="Test description.",
                    employment_type=JobPosting.EmploymentType.FULL_TIME,
                    created_by=self.user,
                    salary_min=Decimal("60000.00"),
                    salary_max=Decimal("50000.00"),
                )

class JobApplicationModelTests(RecruitmentBaseTestCase):
    """Tests for job applications."""

    def test_create_application(self):
        application = JobApplication.objects.create(
            candidate=self.candidate,
            job_posting=self.job_posting,
        )

        self.assertEqual(
            application.status,
            JobApplication.Status.SUBMITTED,
        )

    def test_candidate_cannot_apply_twice_to_same_job(self):
        JobApplication.objects.create(
            candidate=self.candidate,
            job_posting=self.job_posting,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                JobApplication.objects.create(
                    candidate=self.candidate,
                    job_posting=self.job_posting,
                )

    def test_consent_requires_timestamp(self):
        application = JobApplication(
            candidate=self.candidate,
            job_posting=self.job_posting,
            privacy_consent=True,
        )

        with self.assertRaises(ValidationError):
            application.full_clean()

    def test_timestamp_requires_consent(self):
        application = JobApplication(
            candidate=self.candidate,
            job_posting=self.job_posting,
            privacy_consent=False,
            privacy_consent_at=timezone.now(),
        )

        with self.assertRaises(ValidationError):
            application.full_clean()

    def test_valid_privacy_consent(self):
        application = JobApplication(
            candidate=self.candidate,
            job_posting=self.job_posting,
            privacy_consent=True,
            privacy_consent_at=timezone.now(),
        )

        application.full_clean()

class JobApplicationServiceTests(RecruitmentBaseTestCase):
    """Tests for job application business logic."""

    def _open_posting(self):
        self.job_posting.status = JobPosting.Status.OPEN
        self.job_posting.published_at = timezone.now()
        self.job_posting.save(
            update_fields=["status", "published_at"]
        )
        return self.job_posting

    def _candidate_data(self):
        return {
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane.doe@example.com",
            "phone": "4015550100",
        }

    def _create_manager(self, department=None):
        manager = User.objects.create_user(
            email="manager@example.com",
            name="HR Manager",
            password="StrongPassword123!",
            role=User.Role.HR_MANAGER,
        )
        EmployeeProfile.objects.create(
            user=manager,
            employee_id="EMP-HRM-TEST",
            department=department or self.department,
            position=self.position,
            hire_date=date.today(),
        )
        return manager
    def _create_other_department(self):
        department = Department.objects.create(
            name="Finance",
            code="FIN",
        )
        position = Position.objects.create(
            title="Financial Analyst",
            department=department,
        )
        posting = JobPosting.objects.create(
            title="Financial Analyst",
            department=department,
            position=position,
            description="Finance activities.",
            employment_type=JobPosting.EmploymentType.FULL_TIME,
            created_by=self.user,
        )
        return department, posting

    def test_public_application_creates_candidate_and_application(self):
        posting = self._open_posting()

        application = JobApplicationService.submit_application(
            posting_id=posting.pk,
            candidate_data=self._candidate_data(),
            cover_letter="I am interested in this position.",
            privacy_consent=True,
        )

        self.assertEqual(
            application.status,
            JobApplication.Status.SUBMITTED,
        )
        self.assertEqual(
            application.candidate.email,
            "jane.doe@example.com",
        )
        self.assertTrue(application.privacy_consent)
        self.assertIsNotNone(application.privacy_consent_at)
        self.assertIsNone(application.assigned_to)

        self.assertFalse(
            User.objects.filter(
                email="jane.doe@example.com"
            ).exists()
        )

    def test_public_application_reuses_existing_candidate(self):
        posting = self._open_posting()

        application = JobApplicationService.submit_application(
            posting_id=posting.pk,
            candidate_data={
                "first_name": "Changed",
                "last_name": "Name",
                "email": self.candidate.email.upper(),
            },
            privacy_consent=True,
        )

        self.assertEqual(application.candidate.pk, self.candidate.pk)
        self.assertEqual(application.candidate.first_name, "John")
        self.assertEqual(application.candidate.last_name, "Smith")

    def test_public_application_creates_initial_status_history(self):
        posting = self._open_posting()

        application = JobApplicationService.submit_application(
            posting_id=posting.pk,
            candidate_data=self._candidate_data(),
            privacy_consent=True,
        )

        history = ApplicationStatusHistory.objects.get(
            application=application
        )

        self.assertEqual(history.previous_status, "")
        self.assertEqual(
            history.new_status,
            JobApplication.Status.SUBMITTED,
        )
        self.assertIsNone(history.changed_by)

    def test_public_application_records_anonymous_audit(self):
        posting = self._open_posting()

        application = JobApplicationService.submit_application(
            posting_id=posting.pk,
            candidate_data=self._candidate_data(),
            privacy_consent=True,
        )

        audit = AuditLog.objects.get(
            action="JOB_APPLICATION_SUBMITTED",
        )

        self.assertIsNone(audit.user)
        self.assertIn(str(application.pk), audit.details)
        self.assertNotIn(
            "jane.doe@example.com",
            audit.details,
        )


    def test_public_application_rolls_back_when_history_creation_fails(self):
        posting = self._open_posting()
        candidate_data = self._candidate_data()
        candidate_data["email"] = "rollback.history@example.com"

        with patch(
            "recruitment.services.job_application."
            "ApplicationStatusHistory.objects.create",
            side_effect=RuntimeError("History creation failed."),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "History creation failed.",
            ):
                JobApplicationService.submit_application(
                    posting_id=posting.pk,
                    candidate_data=candidate_data,
                    privacy_consent=True,
                )

        self.assertFalse(
            Candidate.objects.filter(
                email="rollback.history@example.com",
                department=self.department,
            ).exists()
        )
        self.assertFalse(
            JobApplication.objects.filter(
                job_posting=posting,
                candidate__email="rollback.history@example.com",
            ).exists()
        )
        self.assertFalse(
            AuditLog.objects.filter(
                action="JOB_APPLICATION_SUBMITTED",
            ).exists()
        )

    def test_public_application_rolls_back_when_audit_creation_fails(self):
        posting = self._open_posting()
        candidate_data = self._candidate_data()
        candidate_data["email"] = "rollback.audit@example.com"

        with patch(
            "recruitment.services.job_application.AuditLog.objects.create",
            side_effect=RuntimeError("Audit creation failed."),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "Audit creation failed.",
            ):
                JobApplicationService.submit_application(
                    posting_id=posting.pk,
                    candidate_data=candidate_data,
                    privacy_consent=True,
                )

        self.assertFalse(
            Candidate.objects.filter(
                email="rollback.audit@example.com",
                department=self.department,
            ).exists()
        )
        self.assertFalse(
            JobApplication.objects.filter(
                job_posting=posting,
                candidate__email="rollback.audit@example.com",
            ).exists()
        )
        self.assertFalse(
            ApplicationStatusHistory.objects.filter(
                application__candidate__email="rollback.audit@example.com",
            ).exists()
        )
        self.assertFalse(
            AuditLog.objects.filter(
                action="JOB_APPLICATION_SUBMITTED",
            ).exists()
        )


    def test_public_application_requires_privacy_consent(self):
        posting = self._open_posting()

        with self.assertRaises(ValidationError):
            JobApplicationService.submit_application(
                posting_id=posting.pk,
                candidate_data=self._candidate_data(),
                privacy_consent=False,
            )

        self.assertFalse(
            Candidate.objects.filter(
                email="jane.doe@example.com"
            ).exists()
        )

    def test_public_application_rejects_closed_posting(self):
        with self.assertRaises(ValidationError):
            JobApplicationService.submit_application(
                posting_id=self.job_posting.pk,
                candidate_data=self._candidate_data(),
                privacy_consent=True,
            )

    def test_public_application_rejects_expired_deadline(self):
        posting = self._open_posting()
        posting.application_deadline = (
            timezone.localdate() - timedelta(days=1)
        )
        posting.save(update_fields=["application_deadline"])

        with self.assertRaises(ValidationError):
            JobApplicationService.submit_application(
                posting_id=posting.pk,
                candidate_data=self._candidate_data(),
                privacy_consent=True,
            )

    def test_public_application_rejects_duplicate_application(self):
        posting = self._open_posting()

        JobApplication.objects.create(
            candidate=self.candidate,
            job_posting=posting,
            privacy_consent=True,
            privacy_consent_at=timezone.now(),
        )

        with self.assertRaises(ValidationError):
            JobApplicationService.submit_application(
                posting_id=posting.pk,
                candidate_data={
                    "first_name": "John",
                    "last_name": "Smith",
                    "email": self.candidate.email,
                },
                privacy_consent=True,
            )

    def test_hr_admin_can_list_applications(self):
        application = JobApplication.objects.create(
            candidate=self.candidate,
            job_posting=self.job_posting,
            privacy_consent=True,
            privacy_consent_at=timezone.now(),
        )

        applications = JobApplicationService.list_applications(
            actor=self.user
        )

        self.assertIn(application, applications)

    def test_hr_admin_can_get_application(self):
        application = JobApplication.objects.create(
            candidate=self.candidate,
            job_posting=self.job_posting,
            privacy_consent=True,
            privacy_consent_at=timezone.now(),
        )

        result = JobApplicationService.get_application(
            application_id=application.pk,
            actor=self.user,
        )

        self.assertEqual(result, application)

    def test_employee_cannot_list_applications(self):
        employee = User.objects.create_user(
            email="employee@example.com",
            name="Regular Employee",
            password="StrongPassword123!",
            role=User.Role.EMPLOYEE,
        )

        with self.assertRaises(PermissionDenied):
            JobApplicationService.list_applications(actor=employee)

    def test_inactive_hr_admin_cannot_list_applications(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        with self.assertRaises(PermissionDenied):
            JobApplicationService.list_applications(actor=self.user)

    def test_hr_manager_can_access_own_department_application(self):
        manager = self._create_manager()

        application = JobApplication.objects.create(
            candidate=self.candidate,
            job_posting=self.job_posting,
            privacy_consent=True,
            privacy_consent_at=timezone.now(),
        )

        result = JobApplicationService.get_application(
            application_id=application.pk,
            actor=manager,
        )

        self.assertEqual(result, application)

    def test_hr_manager_cannot_access_other_department_application(self):
        # Créer le HR Manager
        manager = self._create_manager()

        # Créer un autre département et son offre d'emploi
        other_department, other_posting = self._create_other_department()

        # Créer un candidat appartenant à l'autre département
        other_candidate = Candidate.objects.create(
            first_name="Finance",
            last_name="Candidate",
            email="finance.candidate@example.com",
            department=other_department,
        )

        # Créer une candidature associée à l'offre de cet autre département
        application = JobApplication.objects.create(
            candidate=other_candidate,
            job_posting=other_posting,
            privacy_consent=True,
            privacy_consent_at=timezone.now(),
        )

        # Vérifier que le HR Manager ne peut pas accéder à cette candidature
        with self.assertRaises(PermissionDenied):
            JobApplicationService.get_application(
                application_id=application.pk,
                actor=manager,
            )

    def test_hr_manager_list_is_limited_to_own_department(self):
        manager = self._create_manager()

        # Créer un autre département et son offre d'emploi
        other_department, other_posting = self._create_other_department()

        # Créer une candidature dans le département du manager
        own_application = JobApplication.objects.create(
            candidate=self.candidate,
            job_posting=self.job_posting,
            privacy_consent=True,
            privacy_consent_at=timezone.now(),
        )

        # Créer un candidat dans l'autre département
        other_candidate = Candidate.objects.create(
            first_name="Finance",
            last_name="Candidate",
            email="finance@example.com",
            department=other_department,
        )

        # Créer une candidature dans l'autre département
        other_application = JobApplication.objects.create(
            candidate=other_candidate,
            job_posting=other_posting,
            privacy_consent=True,
            privacy_consent_at=timezone.now(),
        )

        # Récupérer les candidatures accessibles au HR Manager
        applications = JobApplicationService.list_applications(
            actor=manager
        )

        # Vérifier l'isolation entre départements
        self.assertIn(own_application, applications)
        self.assertNotIn(other_application, applications)

    def test_hr_manager_without_employee_profile_cannot_list(self):
        manager = User.objects.create_user(
            email="manager-no-profile@example.com",
            name="Manager Without Profile",
            password="StrongPassword123!",
            role=User.Role.HR_MANAGER,
        )

        with self.assertRaises(PermissionDenied):
            JobApplicationService.list_applications(actor=manager)
    def test_hr_admin_can_assign_application_to_hr_manager(self):
        manager = self._create_manager()

        application = JobApplication.objects.create(
            candidate=self.candidate,
            job_posting=self.job_posting,
            privacy_consent=True,
            privacy_consent_at=timezone.now(),
        )

        result = JobApplicationService.assign_application(
            application_id=application.pk,
            assigned_to_id=manager.pk,
            actor=self.user,
        )

        self.assertEqual(result.assigned_to, manager)

        audit = AuditLog.objects.get(
            action="JOB_APPLICATION_ASSIGNED"
        )

        self.assertEqual(audit.user, self.user)
        self.assertIn(str(application.pk), audit.details)

    def test_hr_admin_cannot_assign_to_inactive_user(self):
        assignee = User.objects.create_user(
            email="inactive@example.com",
            name="Inactive HR",
            password="StrongPassword123!",
            role=User.Role.HR_ADMIN,
            is_active=False,
        )

        application = JobApplication.objects.create(
            candidate=self.candidate,
            job_posting=self.job_posting,
            privacy_consent=True,
            privacy_consent_at=timezone.now(),
        )

        with self.assertRaises(ValidationError):
            JobApplicationService.assign_application(
                application_id=application.pk,
                assigned_to_id=assignee.pk,
                actor=self.user,
            )

    def test_hr_admin_cannot_assign_to_employee(self):
        employee = User.objects.create_user(
            email="employee@example.com",
            name="Regular Employee",
            password="StrongPassword123!",
            role=User.Role.EMPLOYEE,
        )

        application = JobApplication.objects.create(
            candidate=self.candidate,
            job_posting=self.job_posting,
            privacy_consent=True,
            privacy_consent_at=timezone.now(),
        )

        with self.assertRaises(ValidationError):
            JobApplicationService.assign_application(
                application_id=application.pk,
                assigned_to_id=employee.pk,
                actor=self.user,
            )

    def test_hr_manager_cannot_assign_application_outside_department(self):
        manager = self._create_manager()

        # Créer d'abord le département et son offre
        other_department, other_posting = self._create_other_department()

        other_candidate = Candidate.objects.create(
            # autres champs...
            department=other_department,
        )

        application = JobApplication.objects.create(
            candidate=self.candidate,
            job_posting=other_posting,
            privacy_consent=True,
            privacy_consent_at=timezone.now(),
        )

        with self.assertRaises(PermissionDenied):
            JobApplicationService.assign_application(
                application_id=application.pk,
                assigned_to_id=self.user.pk,
                actor=manager,
            )

    def test_hr_admin_cannot_assign_to_nonexistent_user(self):
        application = JobApplication.objects.create(
            candidate=self.candidate,
            job_posting=self.job_posting,
            privacy_consent=True,
            privacy_consent_at=timezone.now(),
        )

        with self.assertRaises(ValidationError):
            JobApplicationService.assign_application(
                application_id=application.pk,
                assigned_to_id=999999999,
                actor=self.user,
            )

class ApplicationStatusHistoryModelTests(RecruitmentBaseTestCase):
    """Tests for application status history."""

    def setUp(self):
        super().setUp()

        self.application = JobApplication.objects.create(
            candidate=self.candidate,
            job_posting=self.job_posting,
        )

    def test_create_initial_status_history(self):
        history = ApplicationStatusHistory.objects.create(
            application=self.application,
            previous_status="",
            new_status=JobApplication.Status.SUBMITTED,
            changed_by=self.user,
        )

        self.assertEqual(
            history.new_status,
            JobApplication.Status.SUBMITTED,
        )

    def test_status_history_rejects_identical_statuses(self):
        history = ApplicationStatusHistory(
            application=self.application,
            previous_status=JobApplication.Status.SUBMITTED,
            new_status=JobApplication.Status.SUBMITTED,
        )

        with self.assertRaises(ValidationError):
            history.full_clean()

    def test_status_history_string_representation(self):
        history = ApplicationStatusHistory.objects.create(
            application=self.application,
            previous_status="",
            new_status=JobApplication.Status.SUBMITTED,
        )

        self.assertIn(
            "INITIAL -> SUBMITTED",
            str(history),
        )

class JobPostingServiceTests(RecruitmentBaseTestCase):
    """Tests for job posting business logic."""

    def test_create_job_posting(self):
        posting = JobPostingService.create_job_posting(
            actor=self.user,
            title="Software Engineer",
            department=self.department,
            position=self.position,
            description="Develop software.",
            employment_type=JobPosting.EmploymentType.FULL_TIME,
        )

        self.assertEqual(posting.status, JobPosting.Status.DRAFT)
        self.assertEqual(posting.created_by, self.user)

        self.assertTrue(
            AuditLog.objects.filter(
                user=self.user,
                action="JOB_POSTING_CREATED",
            ).exists()
        )

    def test_employee_cannot_create_job_posting(self):
        employee = User.objects.create_user(
            email="employee@example.com",
            name="Regular Employee",
            password="StrongPassword123!",
            role=User.Role.EMPLOYEE,
        )

        with self.assertRaises(PermissionDenied):
            JobPostingService.create_job_posting(
                actor=employee,
                title="Unauthorized Posting",
                department=self.department,
                position=self.position,
                description="Not allowed.",
                employment_type=JobPosting.EmploymentType.FULL_TIME,
            )

    def test_hr_manager_can_manage_own_department(self):
        manager = User.objects.create_user(
            email="manager@example.com",
            name="HR Manager",
            password="StrongPassword123!",
            role=User.Role.HR_MANAGER,
        )

        EmployeeProfile.objects.create(
            user=manager,
            employee_id="EMP-HRM-001",
            department=self.department,
            position=self.position,
            hire_date=date.today(),
        )

        posting = JobPostingService.create_job_posting(
            actor=manager,
            title="HR Assistant",
            department=self.department,
            position=self.position,
            description="HR support.",
            employment_type=JobPosting.EmploymentType.FULL_TIME,
        )

        self.assertEqual(posting.created_by, manager)

    def test_hr_manager_cannot_manage_another_department(self):
        manager = User.objects.create_user(
            email="manager2@example.com",
            name="HR Manager",
            password="StrongPassword123!",
            role=User.Role.HR_MANAGER,
        )

        EmployeeProfile.objects.create(
            user=manager,
            employee_id="EMP-HRM-002",
            department=self.department,
            position=self.position,
            hire_date=date.today(),
        )

        other_department = Department.objects.create(
            name="Finance",
            code="FIN",
        )

        other_position = Position.objects.create(
            title="Financial Analyst",
            department=other_department,
        )

        with self.assertRaises(PermissionDenied):
            JobPostingService.create_job_posting(
                actor=manager,
                title="Financial Analyst",
                department=other_department,
                position=other_position,
                description="Finance position.",
                employment_type=JobPosting.EmploymentType.FULL_TIME,
            )

    def test_hr_manager_requires_employee_profile(self):
        manager = User.objects.create_user(
            email="manager3@example.com",
            name="HR Manager",
            password="StrongPassword123!",
            role=User.Role.HR_MANAGER,
        )

        with self.assertRaises(PermissionDenied):
            JobPostingService.create_job_posting(
                actor=manager,
                title="HR Assistant",
                department=self.department,
                position=self.position,
                description="HR support.",
                employment_type=JobPosting.EmploymentType.FULL_TIME,
            )

    def test_update_draft_job_posting(self):
        posting = JobPostingService.update_job_posting(
            posting_id=self.job_posting.pk,
            actor=self.user,
            title="Updated Recruitment Specialist",
        )

        self.assertEqual(
            posting.title,
            "Updated Recruitment Specialist",
        )

        self.assertTrue(
            AuditLog.objects.filter(
                user=self.user,
                action="JOB_POSTING_UPDATED",
            ).exists()
        )

    def test_update_rejects_system_managed_fields(self):
        with self.assertRaises(ValidationError):
            JobPostingService.update_job_posting(
                posting_id=self.job_posting.pk,
                actor=self.user,
                status=JobPosting.Status.OPEN,
            )

    def test_publish_draft_job_posting(self):
        posting = JobPostingService.publish_job_posting(
            posting_id=self.job_posting.pk,
            actor=self.user,
        )

        self.assertEqual(posting.status, JobPosting.Status.OPEN)
        self.assertIsNotNone(posting.published_at)

        self.assertTrue(
            AuditLog.objects.filter(
                user=self.user,
                action="JOB_POSTING_PUBLISHED",
            ).exists()
        )

    def test_publish_rejects_expired_deadline(self):
        self.job_posting.application_deadline = (
            date.today() - timedelta(days=1)
        )
        self.job_posting.save()

        with self.assertRaises(ValidationError):
            JobPostingService.publish_job_posting(
                posting_id=self.job_posting.pk,
                actor=self.user,
            )

    def test_cannot_publish_already_open_posting(self):
        self.job_posting.status = JobPosting.Status.OPEN
        self.job_posting.published_at = timezone.now()
        self.job_posting.save()

        with self.assertRaises(ValidationError):
            JobPostingService.publish_job_posting(
                posting_id=self.job_posting.pk,
                actor=self.user,
            )

    def test_close_open_job_posting(self):
        self.job_posting.status = JobPosting.Status.OPEN
        self.job_posting.published_at = timezone.now()
        self.job_posting.save()

        posting = JobPostingService.close_job_posting(
            posting_id=self.job_posting.pk,
            actor=self.user,
        )

        self.assertEqual(posting.status, JobPosting.Status.CLOSED)

    def test_cannot_close_draft_job_posting(self):
        with self.assertRaises(ValidationError):
            JobPostingService.close_job_posting(
                posting_id=self.job_posting.pk,
                actor=self.user,
            )

    def test_cancel_draft_job_posting(self):
        posting = JobPostingService.cancel_job_posting(
            posting_id=self.job_posting.pk,
            actor=self.user,
        )

        self.assertEqual(posting.status, JobPosting.Status.CANCELLED)

    def test_cancel_open_job_posting(self):
        self.job_posting.status = JobPosting.Status.OPEN
        self.job_posting.published_at = timezone.now()
        self.job_posting.save()

        posting = JobPostingService.cancel_job_posting(
            posting_id=self.job_posting.pk,
            actor=self.user,
        )

        self.assertEqual(posting.status, JobPosting.Status.CANCELLED)

    def test_cannot_cancel_closed_job_posting(self):
        self.job_posting.status = JobPosting.Status.CLOSED
        self.job_posting.published_at = timezone.now()
        self.job_posting.save()

        with self.assertRaises(ValidationError):
            JobPostingService.cancel_job_posting(
                posting_id=self.job_posting.pk,
                actor=self.user,
            )

class CandidateServiceTests(RecruitmentBaseTestCase):
    """Tests for candidate business logic and access control."""

    def _create_manager(self, department=None):
        manager = User.objects.create_user(
            email="manager@example.com",
            name="HR Manager",
            password="StrongPassword123!",
            role=User.Role.HR_MANAGER,
        )

        EmployeeProfile.objects.create(
            user=manager,
            employee_id="EMP-HRM-TEST",
            department=department or self.department,
            position=self.position,
            hire_date=date.today(),
        )

        return manager

    def _create_application(self, candidate, posting):
        return JobApplication.objects.create(
            candidate=candidate,
            job_posting=posting,
            privacy_consent=True,
            privacy_consent_at=timezone.now(),
        )

    def _create_other_department(self):
        department = Department.objects.create(
            name="Finance",
            code="FIN",
        )

        position = Position.objects.create(
            title="Financial Analyst",
            department=department,
        )

        posting = JobPosting.objects.create(
            title="Financial Analyst",
            department=department,
            position=position,
            description="Finance activities.",
            employment_type=JobPosting.EmploymentType.FULL_TIME,
            created_by=self.user,
        )

        return department, posting

    def test_admin_can_create_candidate_without_user_account(self):
        candidate = CandidateService.create_candidate(
            actor=self.user,
            first_name="Jane",
            last_name="Doe",
            email="jane.doe@example.com",
            department=self.department,
        )

        self.assertEqual(candidate.first_name, "Jane")

        self.assertFalse(
            User.objects.filter(
                email="jane.doe@example.com"
            ).exists()
        )

        self.assertTrue(
            AuditLog.objects.filter(
                user=self.user,
                action="CANDIDATE_CREATED",
            ).exists()
        )

    def test_employee_cannot_create_candidate(self):
        employee = User.objects.create_user(
            email="employee@example.com",
            name="Regular Employee",
            password="StrongPassword123!",
            role=User.Role.EMPLOYEE,
        )

        with self.assertRaises(PermissionDenied):
            CandidateService.create_candidate(
                actor=employee,
                first_name="Jane",
                last_name="Doe",
                email="jane.doe@example.com",
            )

    def test_hr_manager_cannot_create_standalone_candidate(self):
        manager = self._create_manager()

        with self.assertRaises(PermissionDenied):
            CandidateService.create_candidate(
                actor=manager,
                first_name="Jane",
                last_name="Doe",
                email="jane.doe@example.com",
            )

    def test_inactive_user_cannot_manage_candidates(self):
        inactive_admin = User.objects.create_user(
            email="inactive@example.com",
            name="Inactive Admin",
            password="StrongPassword123!",
            role=User.Role.HR_ADMIN,
        )
        inactive_admin.is_active = False
        inactive_admin.save(update_fields=["is_active"])

        with self.assertRaises(PermissionDenied):
            CandidateService.list_candidates(actor=inactive_admin)

    def test_create_rejects_system_managed_fields(self):
        with self.assertRaises(ValidationError):
            CandidateService.create_candidate(
                actor=self.user,
                first_name="Jane",
                last_name="Doe",
                email="jane.doe@example.com",
                id="invalid-field",
                department=self.department,
            )

    def test_create_rejects_duplicate_email_case_insensitively(self):
        with self.assertRaises(ValidationError):
            CandidateService.create_candidate(
                actor=self.user,
                first_name="Another",
                last_name="Candidate",
                email="JOHN.SMITH@EXAMPLE.COM",
                department=self.department,
            )

    def test_admin_can_list_all_candidates(self):
        another_candidate = Candidate.objects.create(
            first_name="Jane",
            last_name="Doe",
            email="jane.doe@example.com",
            department=self.department,
        )

        candidates = CandidateService.list_candidates(
            actor=self.user
        )

        self.assertIn(self.candidate, candidates)
        self.assertIn(another_candidate, candidates)

    def test_admin_can_update_candidate(self):
        candidate = CandidateService.update_candidate(
            candidate_id=self.candidate.pk,
            actor=self.user,
            first_name="Jonathan",
        )

        self.assertEqual(candidate.first_name, "Jonathan")

        self.assertTrue(
            AuditLog.objects.filter(
                user=self.user,
                action="CANDIDATE_UPDATED",
            ).exists()
        )

    def test_update_rejects_system_managed_fields(self):
        with self.assertRaises(ValidationError):
            CandidateService.update_candidate(
                candidate_id=self.candidate.pk,
                actor=self.user,
                created_at=timezone.now(),
            )

    def test_update_rejects_empty_data(self):
        with self.assertRaises(ValidationError):
            CandidateService.update_candidate(
                candidate_id=self.candidate.pk,
                actor=self.user,
            )


    def test_audit_log_does_not_expose_candidate_pii(self):
        CandidateService.update_candidate(
            candidate_id=self.candidate.pk,
            actor=self.user,
            first_name="Updated",
        )

        audit = AuditLog.objects.get(
            user=self.user,
            action="CANDIDATE_UPDATED",
        )

        sensitive_values = [
            self.candidate.first_name,
            self.candidate.last_name,
            self.candidate.email,
            self.candidate.phone,
        ]

        for value in sensitive_values:
            if value:
                with self.subTest(value=value):
                    self.assertNotIn(value, audit.details)


    def test_hr_manager_can_access_candidate_in_own_department(self):
        manager = self._create_manager()

        self._create_application(
            self.candidate,
            self.job_posting,
        )

        candidate = CandidateService.get_candidate(
            candidate_id=self.candidate.pk,
            actor=manager,
        )

        self.assertEqual(candidate, self.candidate)

    def test_hr_manager_can_update_candidate_in_own_department(self):
        manager = self._create_manager()

        self._create_application(
            self.candidate,
            self.job_posting,
        )

        candidate = CandidateService.update_candidate(
            candidate_id=self.candidate.pk,
            actor=manager,
            first_name="Updated",
        )

        self.assertEqual(candidate.first_name, "Updated")

    def test_hr_manager_cannot_access_candidate_from_another_department(self):
        manager = self._create_manager()
        other_department, other_posting = (
            self._create_other_department()
        )

        other_candidate = Candidate.objects.create(
            first_name="Finance",
            last_name="Candidate",
            email="finance.candidate@example.com",
            department=other_department,
        )

        self._create_application(
            other_candidate,
            other_posting,
        )

        with self.assertRaises(PermissionDenied):
            CandidateService.get_candidate(
                candidate_id=other_candidate.pk,
                actor=manager,
            )

    def test_hr_manager_list_is_limited_to_own_department(self):
        manager = self._create_manager()
        other_department, other_posting = self._create_other_department()
        own_candidate = self.candidate

        other_candidate = Candidate.objects.create(
            first_name="Finance",
            last_name="Candidate",
            email="finance.candidate@example.com",
            department=other_department,
        )

        self._create_application(
            own_candidate,
            self.job_posting,
        )
        self._create_application(
            other_candidate,
            other_posting,
        )

        candidates = CandidateService.list_candidates(
            actor=manager
        )

        self.assertIn(own_candidate, candidates)
        self.assertNotIn(other_candidate, candidates)

    def test_hr_manager_can_access_candidate_in_own_department_without_application(self):
        manager = self._create_manager()

        candidate = CandidateService.get_candidate(
            candidate_id=self.candidate.pk,
            actor=manager,
        )

        self.assertEqual(candidate, self.candidate)

    def test_hr_manager_requires_employee_profile(self):
        manager = User.objects.create_user(
            email="manager-no-profile@example.com",
            name="Manager Without Profile",
            password="StrongPassword123!",
            role=User.Role.HR_MANAGER,
        )

        with self.assertRaises(PermissionDenied):
                CandidateService.list_candidates(actor=manager)

class ApplicationStatusServiceTests(RecruitmentBaseTestCase):
    """Tests for application status transitions."""

    def _create_application(self, status=None, posting=None):
        return JobApplication.objects.create(
            candidate=self.candidate,
            job_posting=posting or self.job_posting,
            status=status or JobApplication.Status.SUBMITTED,
            privacy_consent=True,
            privacy_consent_at=timezone.now(),
        )

    def _create_manager(self, department=None):
        manager = User.objects.create_user(
            email="status.manager@example.com",
            name="HR Manager",
            password="StrongPassword123!",
            role=User.Role.HR_MANAGER,
        )

        EmployeeProfile.objects.create(
            user=manager,
            employee_id="EMP-STATUS-MGR",
            department=department or self.department,
            position=self.position,
            hire_date=date.today(),
        )

        return manager

    def _create_other_department(self):
        department = Department.objects.create(
            name="Finance",
            code="FIN-STATUS",
        )

        position = Position.objects.create(
            title="Financial Analyst",
            department=department,
        )

        posting = JobPosting.objects.create(
            title="Financial Analyst",
            department=department,
            position=position,
            description="Finance activities.",
            employment_type=JobPosting.EmploymentType.FULL_TIME,
            created_by=self.user,
        )

        return department, posting

    def test_hr_admin_can_change_application_status(self):
        application = self._create_application()

        result = ApplicationStatusService.change_status(
            application_id=application.pk,
            new_status=JobApplication.Status.SCREENING,
            actor=self.user,
        )

        application.refresh_from_db()

        self.assertEqual(
            result.status,
            JobApplication.Status.SCREENING,
        )
        self.assertEqual(
            application.status,
            JobApplication.Status.SCREENING,
        )

    def test_status_change_creates_history(self):
        application = self._create_application()

        ApplicationStatusService.change_status(
            application_id=application.pk,
            new_status=JobApplication.Status.SCREENING,
            actor=self.user,
            note="Initial screening started.",
        )

        history = ApplicationStatusHistory.objects.get(
            application=application,
        )

        self.assertEqual(
            history.previous_status,
            JobApplication.Status.SUBMITTED,
        )
        self.assertEqual(
            history.new_status,
            JobApplication.Status.SCREENING,
        )
        self.assertEqual(history.changed_by, self.user)
        self.assertEqual(history.note, "Initial screening started.")

    def test_status_change_creates_audit_log_without_candidate_pii(self):
        application = self._create_application()

        ApplicationStatusService.change_status(
            application_id=application.pk,
            new_status=JobApplication.Status.SCREENING,
            actor=self.user,
        )

        audit = AuditLog.objects.get(
            action="JOB_APPLICATION_STATUS_CHANGED",
        )

        self.assertEqual(audit.user, self.user)
        self.assertIn(str(application.pk), audit.details)
        self.assertIn(
            JobApplication.Status.SUBMITTED,
            audit.details,
        )
        self.assertIn(
            JobApplication.Status.SCREENING,
            audit.details,
        )

        sensitive_values = [
            self.candidate.first_name,
            self.candidate.last_name,
            self.candidate.email,
            self.candidate.phone,
            application.cover_letter,
        ]

        for value in sensitive_values:
            if value:
                with self.subTest(value=value):
                    self.assertNotIn(value, audit.details)


    def test_invalid_status_is_rejected(self):
        application = self._create_application()

        with self.assertRaises(ValidationError):
            ApplicationStatusService.change_status(
                application_id=application.pk,
                new_status="INVALID_STATUS",
                actor=self.user,
            )

        application.refresh_from_db()

        self.assertEqual(
            application.status,
            JobApplication.Status.SUBMITTED,
        )

    def test_forbidden_transition_is_rejected(self):
        application = self._create_application(
            status=JobApplication.Status.SUBMITTED,
        )

        with self.assertRaises(ValidationError):
            ApplicationStatusService.change_status(
                application_id=application.pk,
                new_status=JobApplication.Status.HIRED,
                actor=self.user,
            )

        application.refresh_from_db()

        self.assertEqual(
            application.status,
            JobApplication.Status.SUBMITTED,
        )

    def test_terminal_status_cannot_be_changed(self):
        application = self._create_application(
            status=JobApplication.Status.HIRED,
        )

        with self.assertRaises(ValidationError):
            ApplicationStatusService.change_status(
                application_id=application.pk,
                new_status=JobApplication.Status.REJECTED,
                actor=self.user,
            )

        application.refresh_from_db()

        self.assertEqual(
            application.status,
            JobApplication.Status.HIRED,
        )

    def test_employee_cannot_change_application_status(self):
        employee = User.objects.create_user(
            email="status.employee@example.com",
            name="Regular Employee",
            password="StrongPassword123!",
            role=User.Role.EMPLOYEE,
        )

        application = self._create_application()

        with self.assertRaises(PermissionDenied):
            ApplicationStatusService.change_status(
                application_id=application.pk,
                new_status=JobApplication.Status.SCREENING,
                actor=employee,
            )

    def test_inactive_hr_admin_cannot_change_status(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        application = self._create_application()

        with self.assertRaises(PermissionDenied):
            ApplicationStatusService.change_status(
                application_id=application.pk,
                new_status=JobApplication.Status.SCREENING,
                actor=self.user,
            )

    def test_hr_manager_can_change_status_in_own_department(self):
        manager = self._create_manager()
        application = self._create_application()

        result = ApplicationStatusService.change_status(
            application_id=application.pk,
            new_status=JobApplication.Status.SCREENING,
            actor=manager,
        )

        self.assertEqual(
            result.status,
            JobApplication.Status.SCREENING,
        )

    def test_hr_manager_cannot_change_status_in_other_department(self):
        # Créer le HR Manager
        manager = self._create_manager()

        # Créer un autre département et son offre d'emploi
        other_department, other_posting = self._create_other_department()

        # Créer un candidat dans l'autre département
        other_candidate = Candidate.objects.create(
            first_name="Finance",
            last_name="Candidate",
            email="finance.status@example.com",
            department=other_department,
        )

        # Créer une candidature associée à l'offre de cet autre département
        application = JobApplication.objects.create(
            candidate=other_candidate,
            job_posting=other_posting,
            privacy_consent=True,
            privacy_consent_at=timezone.now(),
        )

        # Vérifier que le HR Manager ne peut pas modifier son statut
        with self.assertRaises(PermissionDenied):
            ApplicationStatusService.change_status(
                application_id=application.pk,
                new_status=JobApplication.Status.SCREENING,
                actor=manager,
            )

        # Vérifier que le statut n'a pas été modifié
        application.refresh_from_db()

        self.assertEqual(
            application.status,
            JobApplication.Status.SUBMITTED,
        )

    def test_hr_manager_without_employee_profile_is_rejected(self):
        manager = User.objects.create_user(
            email="status.manager.no.profile@example.com",
            name="Manager Without Profile",
            password="StrongPassword123!",
            role=User.Role.HR_MANAGER,
        )

        application = self._create_application()

        with self.assertRaises(PermissionDenied):
            ApplicationStatusService.change_status(
                application_id=application.pk,
                new_status=JobApplication.Status.SCREENING,
                actor=manager,
            )

    def test_nonexistent_application_is_rejected(self):
        with self.assertRaises(ValidationError):
            ApplicationStatusService.change_status(
                application_id="00000000-0000-0000-0000-000000000000",
                new_status=JobApplication.Status.SCREENING,
                actor=self.user,
            )

class RecruitmentPermissionTests(RecruitmentBaseTestCase):
    """Tests for recruitment role-based permissions."""

    def setUp(self):
        super().setUp()

        self.manager_permission = IsActiveRecruitmentManager()
        self.admin_permission = IsRecruitmentAdmin()

    def make_request(self, user):
        return SimpleNamespace(user=user)

    def create_user_with_role(self, email, role, is_active=True):
        return User.objects.create_user(
            email=email,
            name=f"Test {role}",
            password="StrongPassword123!",
            role=role,
            is_active=is_active,
        )

    def test_anonymous_user_is_denied(self):
        request = self.make_request(AnonymousUser())

        self.assertFalse(
            self.manager_permission.has_permission(request, None)
        )
        self.assertFalse(
            self.admin_permission.has_permission(request, None)
        )

    def test_inactive_hr_admin_is_denied(self):
        user = self.create_user_with_role(
            "inactive.admin@example.com",
            User.Role.HR_ADMIN,
            is_active=False,
        )
        request = self.make_request(user)

        self.assertFalse(
            self.manager_permission.has_permission(request, None)
        )
        self.assertFalse(
            self.admin_permission.has_permission(request, None)
        )

    def test_super_admin_has_both_permissions(self):
        user = self.create_user_with_role(
            "super.admin@example.com",
            User.Role.SUPER_ADMIN,
        )
        request = self.make_request(user)

        self.assertTrue(
            self.manager_permission.has_permission(request, None)
        )
        self.assertTrue(
            self.admin_permission.has_permission(request, None)
        )

    def test_hr_admin_has_both_permissions(self):
        request = self.make_request(self.user)

        self.assertTrue(
            self.manager_permission.has_permission(request, None)
        )
        self.assertTrue(
            self.admin_permission.has_permission(request, None)
        )

    def test_hr_manager_has_management_permission_only(self):
        user = self.create_user_with_role(
            "hr.manager@example.com",
            User.Role.HR_MANAGER,
        )
        request = self.make_request(user)

        self.assertTrue(
            self.manager_permission.has_permission(request, None)
        )
        self.assertFalse(
            self.admin_permission.has_permission(request, None)
        )

    def test_employee_is_denied_both_permissions(self):
        user = self.create_user_with_role(
            "employee@example.com",
            User.Role.EMPLOYEE,
        )
        request = self.make_request(user)

        self.assertFalse(
            self.manager_permission.has_permission(request, None)
        )
        self.assertFalse(
            self.admin_permission.has_permission(request, None)
        )

class RecruitmentSerializerTests(RecruitmentBaseTestCase):
    """Tests for recruitment API serializers."""

    def test_job_posting_serializer_valid_data(self):
        serializer = JobPostingSerializer(
            data={
                "title": "Software Engineer",
                "department": self.department.pk,
                "position": self.position.pk,
                "description": "Develop software applications.",
                "employment_type": JobPosting.EmploymentType.FULL_TIME,
                "salary_min": "50000.00",
                "salary_max": "80000.00",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_job_posting_rejects_invalid_salary_range(self):
        serializer = JobPostingSerializer(
            data={
                "title": "Software Engineer",
                "department": self.department.pk,
                "position": self.position.pk,
                "description": "Develop software applications.",
                "employment_type": JobPosting.EmploymentType.FULL_TIME,
                "salary_min": "80000.00",
                "salary_max": "50000.00",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("salary_max", serializer.errors)

    def test_job_posting_rejects_position_from_another_department(self):
        another_department = Department.objects.create(
            name="Finance",
            code="FIN",
        )
        another_position = Position.objects.create(
            title="Financial Analyst",
            department=another_department,
        )

        serializer = JobPostingSerializer(
            data={
                "title": "Software Engineer",
                "department": self.department.pk,
                "position": another_position.pk,
                "description": "Develop software applications.",
                "employment_type": JobPosting.EmploymentType.FULL_TIME,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("position", serializer.errors)

    def test_job_posting_system_fields_are_read_only(self):
        serializer = JobPostingSerializer()

        for field in (
            "id",
            "status",
            "published_at",
            "created_by",
            "created_at",
            "updated_at",
        ):
            self.assertTrue(serializer.fields[field].read_only)

    def test_candidate_serializer_normalizes_email(self):
        serializer = CandidateSerializer(
            data={
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "  JANE.DOE@EXAMPLE.COM  ",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["email"],
            "jane.doe@example.com",
        )

    def test_job_application_requires_privacy_consent(self):
        serializer = JobApplicationSerializer(
            data={
                "candidate_data": {
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "email": "jane.doe@example.com",
                },
                "job_posting": self.job_posting.pk,
                "privacy_consent": False,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("privacy_consent", serializer.errors)

    def test_job_application_accepts_valid_candidate_data(self):
        serializer = JobApplicationSerializer(
            data={
                "candidate_data": {
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "email": "jane.doe@example.com",
                },
                "job_posting": self.job_posting.pk,
                "cover_letter": "I am interested in this position.",
                "privacy_consent": True,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["candidate_data"]["email"],
            "jane.doe@example.com",
        )

    def test_job_application_system_fields_are_read_only(self):
        serializer = JobApplicationSerializer()

        for field in (
            "id",
            "status",
            "assigned_to",
            "privacy_consent_at",
            "applied_at",
            "updated_at",
        ):
            self.assertTrue(serializer.fields[field].read_only)

    def test_status_history_serializer_is_read_only(self):
        serializer = ApplicationStatusHistorySerializer()

        for field in serializer.fields.values():
            self.assertTrue(field.read_only)

class JobPostingAPITests(RecruitmentBaseTestCase):
    """Integration tests for JobPosting API endpoints."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()

        self.create_url = reverse("job-posting-create")
        self.detail_url = reverse(
            "job-posting-detail",
            kwargs={"posting_id": self.job_posting.pk},
        )

        self.valid_payload = {
            "title": "Software Engineer",
            "department": self.department.pk,
            "position": self.position.pk,
            "description": "Develop and maintain software.",
            "employment_type": JobPosting.EmploymentType.FULL_TIME,
            "location": "Rhode Island",
        }

    def create_hr_manager(self):
        manager = User.objects.create_user(
            email="manager.api@example.com",
            name="HR Manager",
            password="StrongPassword123!",
            role=User.Role.HR_MANAGER,
        )

        EmployeeProfile.objects.create(
            user=manager,
            employee_id="EMP-HRM-API",
            department=self.department,
            position=self.position,
            hire_date=date.today(),
        )

        return manager

    def create_other_department_posting(self):
        department = Department.objects.create(
            name="Finance",
            code="FIN-API",
        )

        position = Position.objects.create(
            title="Financial Analyst",
            department=department,
        )

        return JobPosting.objects.create(
            title="Financial Analyst",
            department=department,
            position=position,
            description="Finance activities.",
            employment_type=JobPosting.EmploymentType.FULL_TIME,
            created_by=self.user,
        )
    def authenticate(self, user=None):
        self.client.force_authenticate(user=user or self.user)

    def action_url(self, action):
        return reverse(
            "job-posting-action",
            kwargs={
                "posting_id": self.job_posting.pk,
                "action": action,
            },
        )

    def test_anonymous_user_cannot_create_job_posting(self):
        response = self.client.post(
            self.create_url, self.valid_payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_employee_cannot_create_job_posting(self):
        employee = User.objects.create_user(
            email="employee.api@example.com",
            name="Employee",
            password="StrongPassword123!",
            role=User.Role.EMPLOYEE,
        )
        self.authenticate(employee)

        response = self.client.post(
            self.create_url, self.valid_payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_hr_admin_can_create_job_posting(self):
        self.authenticate()

        response = self.client.post(
            self.create_url, self.valid_payload, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], JobPosting.Status.DRAFT)
        self.assertEqual(response.data["created_by"], self.user.pk)

    def test_hr_admin_can_update_draft_job_posting(self):
        self.authenticate()

        response = self.client.patch(
            self.detail_url,
            {"title": "Updated Recruitment Specialist"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Updated Recruitment Specialist")

    def test_hr_admin_can_publish_job_posting(self):
        self.authenticate()

        response = self.client.post(
            self.action_url("publish"), {}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], JobPosting.Status.OPEN)
        self.assertIsNotNone(response.data["published_at"])

    def test_hr_admin_can_close_open_job_posting(self):
        self.job_posting.status = JobPosting.Status.OPEN
        self.job_posting.published_at = timezone.now()
        self.job_posting.save()

        self.authenticate()
        response = self.client.post(
            self.action_url("close"), {}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], JobPosting.Status.CLOSED)

    def test_hr_admin_can_cancel_draft_job_posting(self):
        self.authenticate()
        response = self.client.post(
            self.action_url("cancel"), {}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], JobPosting.Status.CANCELLED)

    def test_invalid_action_returns_bad_request(self):
        self.authenticate()
        response = self.client.post(
            self.action_url("invalid"), {}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_salary_range_returns_bad_request(self):
        self.authenticate()

        payload = {
            **self.valid_payload,
            "salary_min": "90000.00",
            "salary_max": "50000.00",
        }

        response = self.client.post(
            self.create_url, payload, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_anonymous_user_can_list_open_job_postings(self):
        self.job_posting.status = JobPosting.Status.OPEN
        self.job_posting.published_at = timezone.now()
        self.job_posting.save()

        response = self.client.get(self.create_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            str(self.job_posting.pk),
        )

    def test_public_listing_excludes_non_open_job_postings(self):
        self.job_posting.status = JobPosting.Status.DRAFT
        self.job_posting.save()

        response = self.client.get(self.create_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_public_listing_does_not_expose_internal_fields(self):
        self.job_posting.status = JobPosting.Status.OPEN
        self.job_posting.published_at = timezone.now()
        self.job_posting.save()

        response = self.client.get(self.create_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result = response.data["results"][0]

        self.assertNotIn("created_by", result)
        self.assertNotIn("created_at", result)
        self.assertNotIn("updated_at", result)

    def test_hr_manager_can_update_own_department_posting(self):
        manager = self.create_hr_manager()
        self.authenticate(manager)

        response = self.client.patch(
            self.detail_url,
            {"title": "Updated by HR Manager"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Updated by HR Manager")

    def test_hr_manager_cannot_update_another_department_posting(self):
        manager = self.create_hr_manager()
        other_posting = self.create_other_department_posting()

        self.authenticate(manager)

        url = reverse(
            "job-posting-detail",
            kwargs={"posting_id": other_posting.pk},
        )

        response = self.client.patch(
            url,
            {"title": "Unauthorized update"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_hr_manager_cannot_publish_another_department_posting(self):
        manager = self.create_hr_manager()
        other_posting = self.create_other_department_posting()

        self.authenticate(manager)

        url = reverse(
            "job-posting-action",
            kwargs={
                "posting_id": other_posting.pk,
                "action": "publish",
            },
        )

        response = self.client.post(url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        other_posting.refresh_from_db()
        self.assertEqual(other_posting.status, JobPosting.Status.DRAFT)

    def test_hr_admin_can_update_another_department_posting(self):
        other_posting = self.create_other_department_posting()
        self.authenticate(self.user)

        url = reverse(
            "job-posting-detail",
            kwargs={"posting_id": other_posting.pk},
        )

        response = self.client.patch(
            url,
            {"title": "Updated Finance Position"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Updated Finance Position")

    def test_super_admin_can_update_another_department_posting(self):
        super_admin = User.objects.create_user(
            email="super.admin.api@example.com",
            name="Super Administrator",
            password="StrongPassword123!",
            role=User.Role.SUPER_ADMIN,
        )
        other_posting = self.create_other_department_posting()
        self.authenticate(super_admin)

        url = reverse(
            "job-posting-detail",
            kwargs={"posting_id": other_posting.pk},
        )

        response = self.client.patch(
            url,
            {"title": "Updated by Super Admin"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Updated by Super Admin")

    def test_hr_manager_cannot_close_another_department_posting(self):
        manager = self.create_hr_manager()
        other_posting = self.create_other_department_posting()
        other_posting.status = JobPosting.Status.OPEN
        other_posting.published_at = timezone.now()
        other_posting.save(update_fields=["status", "published_at"])

        self.authenticate(manager)

        url = reverse(
            "job-posting-action",
            kwargs={
                "posting_id": other_posting.pk,
                "action": "close",
            },
        )

        response = self.client.post(url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        other_posting.refresh_from_db()
        self.assertEqual(other_posting.status, JobPosting.Status.OPEN)

    def test_hr_manager_cannot_cancel_another_department_posting(self):
        manager = self.create_hr_manager()
        other_posting = self.create_other_department_posting()

        self.authenticate(manager)

        url = reverse(
            "job-posting-action",
            kwargs={
                "posting_id": other_posting.pk,
                "action": "cancel",
            },
        )

        response = self.client.post(url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        other_posting.refresh_from_db()
        self.assertEqual(other_posting.status, JobPosting.Status.DRAFT)

    def test_update_nonexistent_job_posting_returns_400(self):
        self.authenticate(self.user)

        url = reverse(
            "job-posting-detail",
            kwargs={
                "posting_id": "00000000-0000-0000-0000-000000000000"
            },
        )

        response = self.client.patch(
            url,
            {"title": "Updated title"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_publish_nonexistent_job_posting_returns_400(self):
        self.authenticate(self.user)

        url = reverse(
            "job-posting-action",
            kwargs={
                "posting_id": "00000000-0000-0000-0000-000000000000",
                "action": "publish",
            },
        )

        response = self.client.post(url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_publish_already_open_job_posting(self):
        self.job_posting.status = JobPosting.Status.OPEN
        self.job_posting.save(update_fields=["status"])

        self.authenticate(self.user)

        response = self.client.post(
            self.action_url("publish"),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.job_posting.refresh_from_db()
        self.assertEqual(self.job_posting.status, JobPosting.Status.OPEN)

    def test_cannot_close_draft_job_posting(self):
        self.authenticate(self.user)

        response = self.client.post(
            self.action_url("close"),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.job_posting.refresh_from_db()
        self.assertEqual(self.job_posting.status, JobPosting.Status.DRAFT)

    def test_cannot_cancel_closed_job_posting(self):
        self.job_posting.status = JobPosting.Status.CLOSED
        self.job_posting.save(update_fields=["status"])

        self.authenticate(self.user)

        response = self.client.post(
            self.action_url("cancel"),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.job_posting.refresh_from_db()
        self.assertEqual(self.job_posting.status, JobPosting.Status.CLOSED)

    def test_public_job_listing_is_throttled(self):
        cache.clear()
        self.addCleanup(cache.clear)
        for index in range(1, 61):
            response = self.client.get(self.create_url)

            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                msg=f"Public listing request {index} should be accepted.",
            )

        response = self.client.get(self.create_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

class CandidateAPITests(RecruitmentBaseTestCase):
    """Integration tests for Candidate API endpoints."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()

        self.list_url = reverse("candidate-list-create")
        self.detail_url = reverse(
            "candidate-detail",
            kwargs={"candidate_id": self.candidate.pk},
        )

        self.valid_payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane.doe@example.com",
            "phone": "4015551234",
            "linkedin_url": "https://www.linkedin.com/in/janedoe",
            "portfolio_url": "https://janedoe.example.com",
            "department": self.department.pk,
        }

    def authenticate(self, user=None):
        self.client.force_authenticate(user=user or self.user)

    def create_hr_manager(self):
        manager = User.objects.create_user(
            email="candidate.manager@example.com",
            name="Candidate HR Manager",
            password="StrongPassword123!",
            role=User.Role.HR_MANAGER,
        )

        EmployeeProfile.objects.create(
            user=manager,
            employee_id="EMP-CAND-API",
            department=self.department,
            position=self.position,
            hire_date=date.today(),
        )

        return manager

    def create_application(self, candidate, posting=None):
        return JobApplication.objects.create(
            candidate=candidate,
            job_posting=posting or self.job_posting,
            privacy_consent=True,
            privacy_consent_at=timezone.now(),
        )

    def test_anonymous_user_cannot_list_candidates(self):
        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_employee_cannot_list_candidates(self):
        employee = User.objects.create_user(
            email="candidate.employee@example.com",
            name="Employee",
            password="StrongPassword123!",
            role=User.Role.EMPLOYEE,
        )
        self.authenticate(employee)

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_hr_admin_can_list_candidates(self):
        self.authenticate()

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["email"],
            self.candidate.email,
        )

    def test_hr_admin_can_create_candidate(self):
        self.authenticate()

        response = self.client.post(
            self.list_url,
            self.valid_payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(
            response.data["email"],
            "jane.doe@example.com",
        )
        self.assertTrue(
            Candidate.objects.filter(
                email="jane.doe@example.com"
            ).exists()
        )

    def test_hr_manager_cannot_create_candidate(self):
        manager = self.create_hr_manager()
        self.authenticate(manager)

        response = self.client.post(
            self.list_url,
            self.valid_payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_hr_admin_can_retrieve_candidate(self):
        self.authenticate()

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["id"],
            str(self.candidate.pk),
        )

    def test_hr_admin_can_update_candidate(self):
        self.authenticate()

        response = self.client.patch(
            self.detail_url,
            {"first_name": "Updated"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["first_name"], "Updated")

    def test_hr_manager_can_access_candidate_in_own_department(self):
        manager = self.create_hr_manager()
        self.create_application(self.candidate)

        self.authenticate(manager)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_hr_manager_can_access_candidate_in_own_department_without_application(self):
        manager = self.create_hr_manager()
        self.authenticate(manager)

        response = self.client.get(self.detail_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_hr_manager_cannot_retrieve_other_department_candidate(self):
        manager = self.create_hr_manager()

        other_department = Department.objects.create(
            name="Finance Candidate API",
            code="FIN-CAND-API",
        )

        other_position = Position.objects.create(
            title="Financial Analyst",
            department=other_department,
        )

        other_posting = JobPosting.objects.create(
            title="Finance Analyst API",
            department=other_department,
            position=other_position,
            description="Finance recruitment.",
            employment_type=JobPosting.EmploymentType.FULL_TIME,
            created_by=self.user,
        )

        other_candidate = Candidate.objects.create(
            first_name="Finance",
            last_name="Candidate",
            email="finance.candidate.api@example.com",
            department=other_department,
        )

        self.create_application(
            other_candidate,
            posting=other_posting,
        )

        self.authenticate(manager)

        other_candidate_url = reverse(
            "candidate-detail",
            kwargs={"candidate_id": other_candidate.pk},
        )

        response = self.client.get(other_candidate_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_hr_admin_can_list_candidates_across_departments(self):
        other_department = Department.objects.create(
            name="Finance Global",
            code="FIN-CAND-GLOBAL",
        )
        Candidate.objects.create(
            first_name="Finance",
            last_name="Candidate",
            email="finance.global@example.com",
            department=other_department,
        )

        self.authenticate(self.user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_super_admin_can_list_candidates_across_departments(self):
        super_admin = User.objects.create_user(
            email="super.admin.candidate@example.com",
            name="Super Administrator",
            password="StrongPassword123!",
            role=User.Role.SUPER_ADMIN,
        )

        other_department = Department.objects.create(
            name="Finance Super",
            code="FIN-CAND-SUPER",
        )
        Candidate.objects.create(
            first_name="Finance",
            last_name="Candidate",
            email="finance.super@example.com",
            department=other_department,
        )

        self.authenticate(super_admin)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_hr_manager_list_is_limited_to_own_department(self):
        manager = self.create_hr_manager()

        other_department = Department.objects.create(
            name="Finance Manager",
            code="FIN-CAND-MANAGER",
        )
        Candidate.objects.create(
            first_name="Finance",
            last_name="Candidate",
            email="finance.manager@example.com",
            department=other_department,
        )

        self.authenticate(manager)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

        candidate_ids = {
            item["id"] for item in response.data["results"]
        }
        self.assertIn(str(self.candidate.pk), candidate_ids)

    def test_hr_manager_can_update_candidate_in_own_department(self):
        manager = self.create_hr_manager()
        self.authenticate(manager)

        response = self.client.patch(
            self.detail_url,
            {"first_name": "Updated by Manager"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["first_name"],
            "Updated by Manager",
        )

    def test_hr_manager_cannot_update_other_department_candidate(self):
        manager = self.create_hr_manager()

        other_department = Department.objects.create(
            name="Finance Update",
            code="FIN-CAND-UPDATE",
        )
        other_candidate = Candidate.objects.create(
            first_name="Finance",
            last_name="Candidate",
            email="finance.update@example.com",
            department=other_department,
        )

        self.authenticate(manager)

        url = reverse(
            "candidate-detail",
            kwargs={"candidate_id": other_candidate.pk},
        )

        response = self.client.patch(
            url,
            {"first_name": "Unauthorized Update"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        other_candidate.refresh_from_db()
        self.assertEqual(other_candidate.first_name, "Finance")

    def test_hr_admin_cannot_change_candidate_department(self):
        self.authenticate(self.user)

        original_department_id = self.candidate.department_id

        response = self.client.patch(
            self.detail_url,
            {"department": self.department.pk + 1},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("At least one field must be provided.", str(response.data))

        self.candidate.refresh_from_db()
        self.assertEqual(
            self.candidate.department_id,
            original_department_id,
        )

    def test_duplicate_candidate_email_returns_bad_request(self):
        self.authenticate()

        payload = {
            **self.valid_payload,
            "email": self.candidate.email.upper(),
        }

        response = self.client.post(
            self.list_url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

class JobApplicationAPITests(RecruitmentBaseTestCase):
    """Integration tests for JobApplication API endpoints."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()

        self.list_url = reverse("application-list-create")

        self.job_posting.status = JobPosting.Status.OPEN
        self.job_posting.published_at = timezone.now()
        self.job_posting.save(
            update_fields=["status", "published_at"]
        )

        self.valid_payload = {
            "job_posting": str(self.job_posting.pk),
            "candidate_data": {
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane.application@example.com",
                "phone": "4015551234",
                "linkedin_url": "https://www.linkedin.com/in/janedoe",
                "portfolio_url": "https://janedoe.example.com",
            },
            "cover_letter": "I am interested in this position.",
            "privacy_consent": True,
        }

    def authenticate(self, user=None):
        self.client.force_authenticate(user=user or self.user)

    def create_application(self, status_value=None):
        application = JobApplication.objects.create(
            candidate=self.candidate,
            job_posting=self.job_posting,
            privacy_consent=True,
            privacy_consent_at=timezone.now(),
        )

        if status_value:
            application.status = status_value
            application.save(update_fields=["status"])

        return application

    def application_url(self, application):
        return reverse(
            "application-detail",
            kwargs={"application_id": application.pk},
        )

    def assignment_url(self, application):
        return reverse(
            "application-assign",
            kwargs={"application_id": application.pk},
        )

    def status_url(self, application):
        return reverse(
            "application-status",
            kwargs={"application_id": application.pk},
        )

    def _create_api_manager(self):
        manager = User.objects.create_user(
            email="api.manager@example.com",
            name="API HR Manager",
            password="StrongPassword123!",
            role=User.Role.HR_MANAGER,
        )

        EmployeeProfile.objects.create(
            user=manager,
            employee_id="EMP-API-MGR",
            department=self.department,
            position=self.position,
            hire_date=date.today(),
        )

        return manager

    def _create_other_department_application(self):
        department = Department.objects.create(
            name="Finance API",
            code="FIN-API",
        )

        position = Position.objects.create(
            title="Financial Analyst API",
            department=department,
        )

        posting = JobPosting.objects.create(
            title="Financial Analyst API",
            department=department,
            position=position,
            description="Finance recruitment.",
            employment_type=JobPosting.EmploymentType.FULL_TIME,
            created_by=self.user,
        )

        candidate = Candidate.objects.create(
            first_name="Finance",
            last_name="Candidate",
            email="finance.api.candidate@example.com",
            department=department,
        )

        return JobApplication.objects.create(
            candidate=candidate,
            job_posting=posting,
            privacy_consent=True,
            privacy_consent_at=timezone.now(),
        )

    def test_hr_manager_cannot_retrieve_other_department_application(self):
        manager = self._create_api_manager()
        application = self._create_other_department_application()

        self.authenticate(manager)

        response = self.client.get(
            self.application_url(application)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_hr_manager_cannot_assign_other_department_application(self):
        manager = self._create_api_manager()
        application = self._create_other_department_application()

        self.authenticate(manager)

        response = self.client.post(
            self.assignment_url(application),
            {"assigned_to_id": self.user.pk},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        application.refresh_from_db()
        self.assertIsNone(application.assigned_to)

    def test_hr_manager_cannot_change_status_in_other_department(self):
        manager = self._create_api_manager()
        application = self._create_other_department_application()

        self.authenticate(manager)

        response = self.client.post(
            self.status_url(application),
            {"status": JobApplication.Status.SCREENING},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        application.refresh_from_db()
        self.assertEqual(
            application.status,
            JobApplication.Status.SUBMITTED,
        )
    # ---------------------------------------------------------
    # LIST AND PUBLIC SUBMISSION
    # ---------------------------------------------------------

    def test_anonymous_user_cannot_list_applications(self):
        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_hr_admin_can_list_applications(self):
        application = self.create_application()
        self.authenticate()

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            str(application.pk),
        )

    def test_employee_cannot_list_applications(self):
        employee = User.objects.create_user(
            email="application.employee@example.com",
            name="Employee",
            password="StrongPassword123!",
            role=User.Role.EMPLOYEE,
        )
        self.authenticate(employee)

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_anonymous_user_can_submit_application(self):
        response = self.client.post(
            self.list_url,
            self.valid_payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(
            response.data,
            {
                "detail": "Your application has been submitted successfully."
            },
        )
        self.assertTrue(
            JobApplication.objects.filter(
                candidate__email="jane.application@example.com",
                job_posting=self.job_posting,
            ).exists()
        )

    def test_application_submission_requires_privacy_consent(self):
        payload = {
            **self.valid_payload,
            "privacy_consent": False,
        }

        response = self.client.post(
            self.list_url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_duplicate_application_returns_bad_request(self):
        self.create_application()

        payload = {
            **self.valid_payload,
            "candidate_data": {
                "first_name": self.candidate.first_name,
                "last_name": self.candidate.last_name,
                "email": self.candidate.email,
            },
        }

        response = self.client.post(
            self.list_url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    # ---------------------------------------------------------
    # APPLICATION DETAIL
    # ---------------------------------------------------------

    def test_hr_admin_can_retrieve_application(self):
        application = self.create_application()
        self.authenticate()

        response = self.client.get(
            self.application_url(application)
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(
            response.data["id"],
            str(application.pk),
        )

        self.assertEqual(
            response.data["candidate"]["email"],
            application.candidate.email,
        )
        self.assertEqual(
            response.data["candidate"]["first_name"],
            application.candidate.first_name,
        )
        self.assertEqual(
            response.data["candidate"]["last_name"],
            application.candidate.last_name,
        )
        self.assertEqual(
            response.data["candidate"]["phone"],
            application.candidate.phone,
        )

        self.assertIn("cover_letter", response.data)
        self.assertIn("status", response.data)
        self.assertIn("job_posting", response.data)

    def test_anonymous_user_cannot_retrieve_application(self):
        application = self.create_application()

        response = self.client.get(
            self.application_url(application)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_employee_cannot_retrieve_application(self):
        application = self.create_application()

        employee = User.objects.create_user(
            email="application.detail.employee@example.com",
            name="Employee",
            password="StrongPassword123!",
            role=User.Role.EMPLOYEE,
        )
        self.authenticate(employee)

        response = self.client.get(
            self.application_url(application)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    # ---------------------------------------------------------
    # APPLICATION ASSIGNMENT
    # ---------------------------------------------------------

    def test_hr_admin_can_assign_application(self):
        application = self.create_application()
        self.authenticate()

        response = self.client.post(
            self.assignment_url(application),
            {"assigned_to_id": self.user.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["assigned_to"],
            self.user.pk,
        )

    def test_employee_cannot_assign_application(self):
        application = self.create_application()

        employee = User.objects.create_user(
            email="application.assign.employee@example.com",
            name="Employee",
            password="StrongPassword123!",
            role=User.Role.EMPLOYEE,
        )
        self.authenticate(employee)

        response = self.client.post(
            self.assignment_url(application),
            {"assigned_to_id": self.user.pk},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_assignment_requires_valid_assignee_id(self):
        application = self.create_application()
        self.authenticate()

        response = self.client.post(
            self.assignment_url(application),
            {"assigned_to_id": 999999},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    # ---------------------------------------------------------
    # APPLICATION STATUS
    # ---------------------------------------------------------

    def test_hr_admin_can_change_application_status(self):
        application = self.create_application()
        self.authenticate()

        response = self.client.post(
            self.status_url(application),
            {
                "status": JobApplication.Status.SCREENING,
                "note": "Initial screening started.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["status"],
            JobApplication.Status.SCREENING,
        )

        application.refresh_from_db()
        self.assertEqual(
            application.status,
            JobApplication.Status.SCREENING,
        )

    def test_status_change_creates_history(self):
        application = self.create_application()
        self.authenticate()

        response = self.client.post(
            self.status_url(application),
            {
                "status": JobApplication.Status.SCREENING,
                "note": "Candidate meets initial requirements.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        history = ApplicationStatusHistory.objects.get(
            application=application,
            new_status=JobApplication.Status.SCREENING,
        )

        self.assertEqual(
            history.previous_status,
            JobApplication.Status.SUBMITTED,
        )
        self.assertEqual(history.changed_by, self.user)
        self.assertEqual(
            history.note,
            "Candidate meets initial requirements.",
        )

    def test_employee_cannot_change_application_status(self):
        application = self.create_application()

        employee = User.objects.create_user(
            email="application.status.employee@example.com",
            name="Employee",
            password="StrongPassword123!",
            role=User.Role.EMPLOYEE,
        )
        self.authenticate(employee)

        response = self.client.post(
            self.status_url(application),
            {"status": JobApplication.Status.SCREENING},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_invalid_status_transition_returns_bad_request(self):
        application = self.create_application(
            status_value=JobApplication.Status.SUBMITTED
        )
        self.authenticate()

        response = self.client.post(
            self.status_url(application),
            {"status": JobApplication.Status.HIRED},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_terminal_application_status_cannot_be_changed(self):
        application = self.create_application(
            status_value=JobApplication.Status.REJECTED
        )
        self.authenticate()

        response = self.client.post(
            self.status_url(application),
            {"status": JobApplication.Status.SCREENING},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_public_submission_does_not_expose_sensitive_data(self):
        response = self.client.post(
            self.list_url,
            self.valid_payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertEqual(
            response.data,
            {
                "detail": (
                    "Your application has been submitted successfully."
                )
            },
        )

        sensitive_values = [
            self.valid_payload["candidate_data"]["first_name"],
            self.valid_payload["candidate_data"]["last_name"],
            self.valid_payload["candidate_data"]["email"],
            self.valid_payload["candidate_data"].get("phone", ""),
            self.valid_payload.get("cover_letter", ""),
        ]

        response_content = str(response.data)

        for value in sensitive_values:
            if value:
                with self.subTest(value=value):
                    self.assertNotIn(value, response_content)

    def test_hr_manager_cannot_assign_to_manager_from_another_department(self):
        manager = self._create_api_manager()
        application = self.create_application()

        other_department = Department.objects.create(
            name="Finance Assignee",
            code="FIN-ASG",
        )

        other_position = Position.objects.create(
            title="Finance HR Manager",
            department=other_department,
        )

        other_manager = User.objects.create_user(
            email="finance.manager.api@example.com",
            name="Finance HR Manager",
            password="StrongPassword123!",
            role=User.Role.HR_MANAGER,
        )

        EmployeeProfile.objects.create(
            user=other_manager,
            employee_id="EMP-FIN-ASG",
            department=other_department,
            position=other_position,
            hire_date=date.today(),
        )

        self.authenticate(manager)

        response = self.client.post(
            self.assignment_url(application),
            {"assigned_to_id": other_manager.pk},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        application.refresh_from_db()
        self.assertIsNone(application.assigned_to)

    def test_public_application_submission_is_throttled(self):
        cache.clear()
        self.addCleanup(cache.clear)
        for index in range(1, 6):
            payload = deepcopy(self.valid_payload)
            payload["candidate_data"]["email"] = (
                f"throttle-candidate-{index}@example.com"
            )

            response = self.client.post(
                self.list_url,
                payload,
                format="json",
            )

            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                msg=f"Submission {index} should be accepted.",
            )

        payload = deepcopy(self.valid_payload)
        payload["candidate_data"]["email"] = (
            "throttle-candidate-6@example.com"
        )

        response = self.client.post(
            self.list_url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

    def test_hr_application_listing_is_throttled(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.authenticate()

        for index in range(1, 61):
            response = self.client.get(self.list_url)

            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                msg=f"HR listing request {index} should be accepted.",
            )

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

class JobApplicationORMBaselineTests(RecruitmentBaseTestCase):
    """Measure recruitment ORM queries before optimization."""

    def setUp(self):
        super().setUp()
        self.manager = User.objects.create_user(
            email="orm.manager@example.com",
            name="ORM HR Manager",
            password="StrongPassword123!",
            role=User.Role.HR_MANAGER,
        )

        EmployeeProfile.objects.create(
            user=self.manager,
            employee_id="EMP-ORM-MGR",
            department=self.department,
            position=self.position,
            hire_date=date.today(),
        )
        self.job_posting.status = JobPosting.Status.OPEN
        self.job_posting.published_at = timezone.now()
        self.job_posting.save(
            update_fields=["status", "published_at"]
        )

        self.applications = []

        for index in range(10):
            candidate = Candidate.objects.create(
                first_name=f"Candidate{index}",
                last_name="Baseline",
                email=f"candidate{index}@baseline.example.com",
                department=self.department,
            )

            application = JobApplication.objects.create(
                candidate=candidate,
                job_posting=self.job_posting,
                privacy_consent=True,
                privacy_consent_at=timezone.now(),
            )

            self.applications.append(application)

    def test_list_service_query_baseline(self):
        with CaptureQueriesContext(connection) as queries:
            queryset = JobApplicationService.list_applications(
                actor=self.user,
            )

            data = JobApplicationSerializer(
                list(queryset),
                many=True,
            ).data

        self.assertEqual(len(data), 10)

        print(
            "\n[ORM BASELINE] Service + serialization:",
            len(queries),
            "SQL queries for 10 applications",
        )


    def test_list_api_query_baseline(self):
        client = APIClient()
        client.force_authenticate(user=self.user)

        url = reverse("application-list-create")

        with CaptureQueriesContext(connection) as queries:
            response = client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 10)

        print(
            "\n[ORM BASELINE] API GET:",
            len(queries),
            "SQL queries for 10 applications",
        )

    def test_detail_service_query_baseline(self):
        with CaptureQueriesContext(connection) as queries:
            application = JobApplicationService.get_application(
                application_id=self.applications[0].pk,
                actor=self.user,
            )
            data = JobApplicationSerializer(application).data

        self.assertEqual(
            data["candidate"]["email"],
            self.applications[0].candidate.email,
        )

        print(
            "\n[ORM BASELINE] Detail service + serialization:",
            len(queries),
            "SQL queries for 1 application",
        )

    def test_detail_api_query_baseline(self):
        application = self.applications[0]

        client = APIClient()
        client.force_authenticate(user=self.user)

        url = reverse(
            "application-detail",
            kwargs={"application_id": application.pk},
        )

        with CaptureQueriesContext(connection) as queries:
            response = client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(application.pk))
        print(
            "\n[ORM BASELINE] Detail API GET:",
            len(queries),
            "SQL queries for 1 application",
        )


    def test_candidate_list_service_query_baseline(self):
        queryset = CandidateService.list_candidates(
            actor=self.user,
        )

        with CaptureQueriesContext(connection) as queries:
            data = CandidateSerializer(
                list(queryset),
                many=True,
            ).data

        self.assertEqual(len(data), 11)

        print(
            "\n[ORM BASELINE] Candidate list service + serialization:",
            len(queries),
            "SQL queries for 11 candidates",
        )

    def test_candidate_list_api_query_baseline(self):
        client = APIClient()
        client.force_authenticate(user=self.user)

        url = reverse("candidate-list-create")

        with CaptureQueriesContext(connection) as queries:
            response = client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 11)

        print(
            "\n[ORM BASELINE] Candidate list API GET:",
            len(queries),
            "SQL queries for 11 candidates",
        )

    def test_candidate_detail_service_query_baseline(self):
        candidate = self.applications[0].candidate

        with CaptureQueriesContext(connection) as queries:
            retrieved_candidate = CandidateService.get_candidate(
                candidate_id=candidate.pk,
                actor=self.user,
            )

            data = CandidateSerializer(retrieved_candidate).data

        self.assertEqual(data["id"], str(candidate.pk))

        print(
            "\n[ORM BASELINE] Candidate detail service + serialization:",
            len(queries),
            "SQL queries for 1 candidate",
        )

    def test_candidate_detail_api_query_baseline(self):
        candidate = self.applications[0].candidate

        client = APIClient()
        client.force_authenticate(user=self.user)

        url = reverse(
            "candidate-detail",
            kwargs={"candidate_id": candidate.pk},
        )

        with CaptureQueriesContext(connection) as queries:
            response = client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(candidate.pk))

        print(
            "\n[ORM BASELINE] Candidate detail API GET:",
            len(queries),
            "SQL queries for 1 candidate",
        )

    def test_manager_candidate_list_service_query_baseline(self):
        with CaptureQueriesContext(connection) as queries:
            queryset = CandidateService.list_candidates(
                actor=self.manager,
            )
            data = CandidateSerializer(
                list(queryset),
                many=True,
            ).data

        self.assertEqual(len(data), 11)

        print(
            "\n[ORM BASELINE] HR_MANAGER Candidate list service:",
            len(queries),
            "SQL queries for 11 candidates",
        )

    def test_manager_candidate_list_api_query_baseline(self):
        client = APIClient()
        client.force_authenticate(user=self.manager)

        with CaptureQueriesContext(connection) as queries:
            response = client.get(
                reverse("candidate-list-create")
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 11)

        print(
            "\n[ORM BASELINE] HR_MANAGER Candidate list API:",
            len(queries),
            "SQL queries for 11 candidates",
        )

    def test_manager_candidate_detail_service_query_baseline(self):
        candidate = self.applications[0].candidate

        with CaptureQueriesContext(connection) as queries:
            retrieved = CandidateService.get_candidate(
                candidate_id=candidate.pk,
                actor=self.manager,
            )
            data = CandidateSerializer(retrieved).data

        self.assertEqual(data["id"], str(candidate.pk))

        print(
            "\n[ORM BASELINE] HR_MANAGER Candidate detail service:",
            len(queries),
            "SQL queries for 1 candidate",
        )

    def test_manager_candidate_detail_api_query_baseline(self):
        candidate = self.applications[0].candidate
        client = APIClient()
        client.force_authenticate(user=self.manager)

        with CaptureQueriesContext(connection) as queries:
            response = client.get(
                reverse(
                    "candidate-detail",
                    kwargs={"candidate_id": candidate.pk},
                )
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(candidate.pk))

        print(
            "\n[ORM BASELINE] HR_MANAGER Candidate detail API:",
            len(queries),
            "SQL queries for 1 candidate",
        )

    def test_manager_application_list_service_query_baseline(self):
        with CaptureQueriesContext(connection) as queries:
            queryset = JobApplicationService.list_applications(
                actor=self.manager,
            )
            data = JobApplicationSerializer(
                list(queryset),
                many=True,
            ).data

        self.assertEqual(len(data), 10)

        print(
            "\n[ORM BASELINE] HR_MANAGER Application list service:",
            len(queries),
            "SQL queries for 10 applications",
        )


    def test_manager_application_list_api_query_baseline(self):
        client = APIClient()
        client.force_authenticate(user=self.manager)

        with CaptureQueriesContext(connection) as queries:
            response = client.get(
                reverse("application-list-create")
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 10)

        print(
            "\n[ORM BASELINE] HR_MANAGER Application list API:",
            len(queries),
            "SQL queries for 10 applications",
        )

    def test_manager_application_detail_service_query_baseline(self):
        application = self.applications[0]

        with CaptureQueriesContext(connection) as queries:
            retrieved = JobApplicationService.get_application(
                application_id=application.pk,
                actor=self.manager,
            )
            data = JobApplicationSerializer(retrieved).data

        self.assertEqual(data["id"], str(application.pk))

        print(
            "\n[ORM BASELINE] HR_MANAGER Application detail service:",
            len(queries),
            "SQL queries for 1 application",
        )


    def test_manager_application_detail_api_query_baseline(self):
        application = self.applications[0]
        client = APIClient()
        client.force_authenticate(user=self.manager)

        with CaptureQueriesContext(connection) as queries:
            response = client.get(
                reverse(
                    "application-detail",
                    kwargs={"application_id": application.pk},
                )
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(application.pk))

        print(
            "\n[ORM BASELINE] HR_MANAGER Application detail API:",
            len(queries),
            "SQL queries for 1 application",
        )

class JobPostingORMBaselineTests(RecruitmentBaseTestCase):
    """Measure JobPosting ORM queries before optimization."""

    def setUp(self):
        super().setUp()

        self.manager = User.objects.create_user(
            email="posting.orm.manager@example.com",
            name="Job Posting ORM Manager",
            password="StrongPassword123!",
            role=User.Role.HR_MANAGER,
        )

        EmployeeProfile.objects.create(
            user=self.manager,
            employee_id="EMP-POSTING-ORM-MGR",
            department=self.department,
            position=self.position,
            hire_date=date.today(),
        )

    def _create_posting(self, title, status=JobPosting.Status.DRAFT):
        posting = JobPosting.objects.create(
            title=title,
            department=self.department,
            position=self.position,
            description="ORM baseline job posting.",
            employment_type=JobPosting.EmploymentType.FULL_TIME,
            created_by=self.user,
            status=status,
            published_at=(
                timezone.now()
                if status == JobPosting.Status.OPEN
                else None
            ),
        )
        return posting

    def _measure_service(self, operation, actor, posting):
        with CaptureQueriesContext(connection) as queries:
            result = operation(
                posting_id=posting.pk,
                actor=actor,
            )

        self.assertEqual(result.pk, posting.pk)

        return len(queries)

    def _measure_api_request(
        self,
        actor,
        method,
        url,
        data=None,
        expected_status=200,
    ):
        client = APIClient()
        client.force_authenticate(user=actor)

        with CaptureQueriesContext(connection) as queries:
            response = getattr(client, method)(
                url,
                data or {},
                format="json",
            )

        self.assertEqual(
            response.status_code,
            expected_status,
            response.data,
        )

        return len(queries), response

    def test_public_job_posting_list_api_query_baseline(self):
        self._create_posting(
            "Public ORM Posting",
            status=JobPosting.Status.OPEN,
        )

        client = APIClient()

        with CaptureQueriesContext(connection) as queries:
            response = client.get(
                reverse("job-posting-create")
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

        print(
            "\n[ORM BASELINE] Public JobPosting API GET:",
            len(queries),
            "SQL queries for 1 posting",
        )

    def test_admin_update_service_query_baseline(self):
        posting = self._create_posting("Admin Update Baseline")

        count = self._measure_service(
            JobPostingService.update_job_posting,
            self.user,
            posting,
        )

        print(
            "\n[ORM BASELINE] HR_ADMIN JobPosting update:",
            count,
            "SQL queries",
        )

    def test_admin_publish_service_query_baseline(self):
        posting = self._create_posting("Admin Publish Baseline")

        count = self._measure_service(
            JobPostingService.publish_job_posting,
            self.user,
            posting,
        )

        print(
            "\n[ORM BASELINE] HR_ADMIN JobPosting publish:",
            count,
            "SQL queries",
        )

    def test_admin_close_service_query_baseline(self):
        posting = self._create_posting(
            "Admin Close Baseline",
            status=JobPosting.Status.OPEN,
        )

        count = self._measure_service(
            JobPostingService.close_job_posting,
            self.user,
            posting,
        )

        print(
            "\n[ORM BASELINE] HR_ADMIN JobPosting close:",
            count,
            "SQL queries",
        )

    def test_admin_cancel_service_query_baseline(self):
        posting = self._create_posting("Admin Cancel Baseline")

        count = self._measure_service(
            JobPostingService.cancel_job_posting,
            self.user,
            posting,
        )

        print(
            "\n[ORM BASELINE] HR_ADMIN JobPosting cancel:",
            count,
            "SQL queries",
        )

    def test_admin_create_api_query_baseline(self):
        payload = {
            "title": "API ORM Baseline Posting",
            "department": self.department.pk,
            "position": self.position.pk,
            "description": "API ORM baseline.",
            "employment_type": JobPosting.EmploymentType.FULL_TIME,
            "location": "Rhode Island",
        }

        count, response = self._measure_api_request(
            actor=self.user,
            method="post",
            url=reverse("job-posting-create"),
            data=payload,
            expected_status=201,
        )

        self.assertEqual(
            response.data["status"],
            JobPosting.Status.DRAFT,
        )

        print(
            "\n[ORM BASELINE] HR_ADMIN JobPosting CREATE API:",
            count,
            "SQL queries",
        )

    def test_admin_update_api_query_baseline(self):
        posting = self._create_posting("Admin API Update Baseline")

        count, response = self._measure_api_request(
            actor=self.user,
            method="patch",
            url=reverse(
                "job-posting-detail",
                kwargs={"posting_id": posting.pk},
            ),
            data={"title": "Updated by API"},
        )

        self.assertEqual(response.data["title"], "Updated by API")

        print(
            "\n[ORM BASELINE] HR_ADMIN JobPosting UPDATE API:",
            count,
            "SQL queries",
        )

    def test_admin_publish_api_query_baseline(self):
        posting = self._create_posting("Admin API Publish Baseline")

        count, response = self._measure_api_request(
            actor=self.user,
            method="post",
            url=reverse(
                "job-posting-action",
                kwargs={
                    "posting_id": posting.pk,
                    "action": "publish",
                },
            ),
        )

        self.assertEqual(
            response.data["status"],
            JobPosting.Status.OPEN,
        )

        print(
            "\n[ORM BASELINE] HR_ADMIN JobPosting PUBLISH API:",
            count,
            "SQL queries",
        )

    def test_admin_close_api_query_baseline(self):
        posting = self._create_posting(
            "Admin API Close Baseline",
            status=JobPosting.Status.OPEN,
        )

        count, response = self._measure_api_request(
            actor=self.user,
            method="post",
            url=reverse(
                "job-posting-action",
                kwargs={
                    "posting_id": posting.pk,
                    "action": "close",
                },
            ),
        )

        self.assertEqual(
            response.data["status"],
            JobPosting.Status.CLOSED,
        )

        print(
            "\n[ORM BASELINE] HR_ADMIN JobPosting CLOSE API:",
            count,
            "SQL queries",
        )

    def test_admin_cancel_api_query_baseline(self):
        posting = self._create_posting("Admin API Cancel Baseline")

        count, response = self._measure_api_request(
            actor=self.user,
            method="post",
            url=reverse(
                "job-posting-action",
                kwargs={
                    "posting_id": posting.pk,
                    "action": "cancel",
                },
            ),
        )

        self.assertEqual(
            response.data["status"],
            JobPosting.Status.CANCELLED,
        )

        print(
            "\n[ORM BASELINE] HR_ADMIN JobPosting CANCEL API:",
            count,
            "SQL queries",
        )

    def test_manager_update_service_query_baseline(self):
        posting = self._create_posting("Manager Update Baseline")

        count = self._measure_service(
            JobPostingService.update_job_posting,
            self.manager,
            posting,
        )

        print(
            "\n[ORM BASELINE] HR_MANAGER JobPosting update:",
            count,
            "SQL queries",
        )

    def test_manager_publish_service_query_baseline(self):
        posting = self._create_posting("Manager Publish Baseline")

        count = self._measure_service(
            JobPostingService.publish_job_posting,
            self.manager,
            posting,
        )

        print(
            "\n[ORM BASELINE] HR_MANAGER JobPosting publish:",
            count,
            "SQL queries",
        )

    def test_manager_close_service_query_baseline(self):
        posting = self._create_posting(
            "Manager Close Baseline",
            status=JobPosting.Status.OPEN,
        )

        count = self._measure_service(
            JobPostingService.close_job_posting,
            self.manager,
            posting,
        )

        print(
            "\n[ORM BASELINE] HR_MANAGER JobPosting close:",
            count,
            "SQL queries",
        )

    def test_manager_cancel_service_query_baseline(self):
        posting = self._create_posting("Manager Cancel Baseline")

        count = self._measure_service(
            JobPostingService.cancel_job_posting,
            self.manager,
            posting,
        )

        print(
            "\n[ORM BASELINE] HR_MANAGER JobPosting cancel:",
            count,
            "SQL queries",
        )

    def test_manager_create_api_query_baseline(self):
        payload = {
            "title": "Manager API ORM Baseline",
            "department": self.department.pk,
            "position": self.position.pk,
            "description": "Manager API ORM baseline.",
            "employment_type": JobPosting.EmploymentType.FULL_TIME,
            "location": "Rhode Island",
        }

        count, response = self._measure_api_request(
            actor=self.manager,
            method="post",
            url=reverse("job-posting-create"),
            data=payload,
            expected_status=201,
        )

        self.assertEqual(
            response.data["status"],
            JobPosting.Status.DRAFT,
        )

        print(
            "\n[ORM BASELINE] HR_MANAGER JobPosting CREATE API:",
            count,
            "SQL queries",
        )

    def test_manager_update_api_query_baseline(self):
        posting = self._create_posting("Manager API Update Baseline")

        count, response = self._measure_api_request(
            actor=self.manager,
            method="patch",
            url=reverse(
                "job-posting-detail",
                kwargs={"posting_id": posting.pk},
            ),
            data={"title": "Updated by Manager API"},
        )

        self.assertEqual(
            response.data["title"],
            "Updated by Manager API",
        )

        print(
            "\n[ORM BASELINE] HR_MANAGER JobPosting UPDATE API:",
            count,
            "SQL queries",
        )

    def test_manager_publish_api_query_baseline(self):
        posting = self._create_posting("Manager API Publish Baseline")

        count, response = self._measure_api_request(
            actor=self.manager,
            method="post",
            url=reverse(
                "job-posting-action",
                kwargs={
                    "posting_id": posting.pk,
                    "action": "publish",
                },
            ),
        )

        self.assertEqual(
            response.data["status"],
            JobPosting.Status.OPEN,
        )

        print(
            "\n[ORM BASELINE] HR_MANAGER JobPosting PUBLISH API:",
            count,
            "SQL queries",
        )

    def test_manager_close_api_query_baseline(self):
        posting = self._create_posting(
            "Manager API Close Baseline",
            status=JobPosting.Status.OPEN,
        )

        count, response = self._measure_api_request(
            actor=self.manager,
            method="post",
            url=reverse(
                "job-posting-action",
                kwargs={
                    "posting_id": posting.pk,
                    "action": "close",
                },
            ),
        )

        self.assertEqual(
            response.data["status"],
            JobPosting.Status.CLOSED,
        )

        print(
            "\n[ORM BASELINE] HR_MANAGER JobPosting CLOSE API:",
            count,
            "SQL queries",
        )

    def test_manager_cancel_api_query_baseline(self):
        posting = self._create_posting("Manager API Cancel Baseline")

        count, response = self._measure_api_request(
            actor=self.manager,
            method="post",
            url=reverse(
                "job-posting-action",
                kwargs={
                    "posting_id": posting.pk,
                    "action": "cancel",
                },
            ),
        )

        self.assertEqual(
            response.data["status"],
            JobPosting.Status.CANCELLED,
        )

        print(
            "\n[ORM BASELINE] HR_MANAGER JobPosting CANCEL API:",
            count,
            "SQL queries",
        )

    def test_public_job_posting_list_api_query_scaling(self):
        for index in range(10):
            self._create_posting(
                f"Public Scaling Posting {index}",
                status=JobPosting.Status.OPEN,
            )

        client = APIClient()

        with CaptureQueriesContext(connection) as queries:
            response = client.get(
                reverse("job-posting-create")
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 10)

        print(
            "\n[ORM BASELINE] Public JobPosting API GET:",
            len(queries),
            "SQL queries for 10 postings",
        )
