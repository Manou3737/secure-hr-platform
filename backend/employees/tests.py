from django.test import TestCase
from datetime import date, datetime, timedelta
from unittest.mock import patch
from cryptography.fernet import Fernet
from employees.encryption import encrypt_bank_data, decrypt_bank_data
from accounts.models import User, SecurityEvent, AuditLog
import uuid
from zoneinfo import ZoneInfo
from copy import deepcopy

from rest_framework import status
from rest_framework.test import APIClient

from django.core.cache import cache
from django.db.models.deletion import ProtectedError
from django.db import IntegrityError
from django.db import connection
from django.db import transaction
from django.core.management import call_command, CommandError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError, PermissionDenied

from employees.storage import hr_document_storage
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
from .serializers import (
    BankAccountSerializer,
    EmployeeProfileSerializer,
    HRDocumentSerializer,
    LeaveRequestSerializer,
    PerformanceReviewSerializer,
    DashboardFilterSerializer,
)

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
    DocumentVersion,
    DocumentReview,
    DocumentAccessLog,
    DocumentRetentionPolicy,
    NotificationJob,
    NotificationSchedulerState,
)
from unittest.mock import patch
from employees.antivirus import AntivirusUnavailable, MalwareDetected
from employees.services.onboarding import OnboardingService
from employees.models import OnboardingActivityTemplate
from employees.permissions import DashboardPermission

class EmployeeProfileModelTests(TestCase):
    """Tests for the EmployeeProfile model."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="employee@example.com",
            name="Test Employee",
            password="TestPass123!",
        )

        self.department = Department.objects.create(
            name="Engineering",
            code="ENG",
        )

        self.position = Position.objects.create(
            title="Software Engineer",
            department=self.department,
        )

        self.profile = EmployeeProfile.objects.create(
            user=self.user,
            employee_id="EMP-001",
            department=self.department,
            position=self.position,
            phone="401-555-0101",
            hire_date=date.today(),
        )

    def test_employee_profile_is_created(self):
        self.assertEqual(
            self.profile.employee_id,
            "EMP-001",
        )
        self.assertEqual(
            self.profile.department,
            self.department,
        )
        self.assertEqual(
            self.profile.department.name,
            "Engineering",
        )
        self.assertEqual(
            self.profile.position,
            self.position,
        )
        self.assertEqual(
            self.profile.position.title,
            "Software Engineer",
        )

    def test_employee_profile_is_linked_to_user(self):
        self.assertEqual(
            self.profile.user,
            self.user,
        )
        self.assertEqual(
            self.user.employee_profile,
            self.profile,
        )

    def test_employee_id_is_unique(self):
        with self.assertRaises(Exception):
            EmployeeProfile.objects.create(
                user=User.objects.create_user(
                    email="employee2@example.com",
                    name="Second Employee",
                    password="StrongPassword123!",
                ),
                employee_id="EMP-001",
                department=self.department,
                position=self.position,
                hire_date=date(2026, 2, 1),
            )


class EmployeeProfileSerializerTests(TestCase):
    """Tests for the EmployeeProfile serializer."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="employee@example.com",
            name="John Employee",
            password="StrongPassword123!",
        )

        self.department = Department.objects.create(
            name="Engineering",
            code="ENG",
        )

        self.position = Position.objects.create(
            title="Software Engineer",
            department=self.department,
        )

        self.profile = EmployeeProfile.objects.create(
            user=self.user,
            employee_id="EMP-001",
            department=self.department,
            position=self.position,
            phone="401-555-0100",
            hire_date=date(2026, 1, 15),
        )

    def test_serializer_contains_expected_fields(self):
        serializer = EmployeeProfileSerializer(
            self.profile
        )

        expected_fields = {
            "id",
            "user",
            "employee_id",
            "department",
            "position",
            "phone",
            "hire_date",
            "date_of_birth",
            "address",
            "created_at",
            "updated_at",
        }

        self.assertEqual(
            set(serializer.data.keys()),
            expected_fields,
        )

    def test_read_only_fields(self):
        serializer = EmployeeProfileSerializer(
            self.profile
        )

        self.assertTrue(
            serializer.fields["id"].read_only
        )
        self.assertTrue(
            serializer.fields["created_at"].read_only
        )
        self.assertTrue(
            serializer.fields["updated_at"].read_only
        )

class EmployeeProfileRBACAPITests(TestCase):
    """Tests for employee API role-based access control."""

    def setUp(self):
        self.client = APIClient()

        self.super_admin = User.objects.create_user(
            email="admin@example.com",
            name="Super Admin",
            password="StrongPassword123!",
            role="SUPER_ADMIN",
            is_staff=True,
            is_superuser=True,
        )

        self.hr_admin = User.objects.create_user(
            email="hradmin@example.com",
            name="HR Admin",
            password="StrongPassword123!",
            role="HR_ADMIN",
        )

        self.hr_manager = User.objects.create_user(
            email="manager@example.com",
            name="HR Manager",
            password="StrongPassword123!",
            role="HR_MANAGER",
        )

        self.employee = User.objects.create_user(
            email="employee@example.com",
            name="John Employee",
            password="StrongPassword123!",
            role="EMPLOYEE",
        )

        self.other_employee = User.objects.create_user(
            email="other@example.com",
            name="Other Employee",
            password="StrongPassword123!",
            role="EMPLOYEE",
        )

        self.engineering = Department.objects.create(
            name="Engineering",
            code="ENG",
        )

        self.software_engineer = Position.objects.create(
            title="Software Engineer",
            department=self.engineering,
        )

        self.hr = Department.objects.create(
            name="HR",
            code="HR",
        )

        self.hr_specialist = Position.objects.create(
            title="HR Specialist",
            department=self.hr,
        )

        self.finance = Department.objects.create(
            name="Finance",
            code="FIN",
        )

        self.financial_analyst = Position.objects.create(
            title="Financial Analyst",
            department=self.finance,
        )

        self.backend_developer = Position.objects.create(
            title="Backend Developer",
            department=self.engineering,
        )

        self.senior_software_engineer = Position.objects.create(
            title="Senior Software Engineer",
            department=self.engineering,
        )

        self.profile = EmployeeProfile.objects.create(
            user=self.employee,
            employee_id="EMP-001",
            department=self.engineering,
            position=self.software_engineer,
            hire_date=date(2026, 1, 15),
        )

        self.other_profile = EmployeeProfile.objects.create(
            user=self.other_employee,
            employee_id="EMP-002",
            department=self.hr,
            position=self.hr_specialist,
            hire_date=date(2026, 2, 1),
        )

        self.url = "/api/v1/employees/"

    def authenticate(self, user):
        """Authenticate the API client as the given user."""

        self.client.force_authenticate(
            user=user
        )

    def test_unauthenticated_user_is_rejected(self):
        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_employee_can_only_see_own_profile(self):
        self.authenticate(self.employee)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            1,
        )

        self.assertEqual(
            response.data["results"][0]["employee_id"],
            "EMP-001",
        )

    def test_employee_cannot_access_other_employee_profile(self):
        self.authenticate(self.employee)

        response = self.client.get(
            f"{self.url}{self.other_profile.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        event = SecurityEvent.objects.get(
            event_type="UNAUTHORIZED_ACCESS"
        )

        self.assertEqual(
            event.user,
            self.employee,
        )
        self.assertEqual(
            event.ip_address,
            "127.0.0.1",
        )
        self.assertEqual(
            event.request_path,
            f"{self.url}{self.other_profile.id}/",
        )
        self.assertIn(
            "Unauthorized access",
            event.details,
        )

    def test_hr_manager_can_view_all_profiles(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            2,
        )

    def test_hr_admin_can_create_employee_profile(self):
        self.authenticate(self.hr_admin)

        new_user = User.objects.create_user(
            email="newemployee@example.com",
            name="New Employee",
            password="StrongPassword123!",
            role="EMPLOYEE",
        )

        response = self.client.post(
            self.url,
            {
                "user": new_user.id,
                "employee_id": "EMP-003",
                "department": self.finance.id,
                "position": self.financial_analyst.id,
                "phone": "401-555-0101",
                "hire_date": "2026-03-01",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

    def test_hr_manager_cannot_create_employee_profile(self):
        self.authenticate(self.hr_manager)

        new_user = User.objects.create_user(
            email="newemployee@example.com",
            name="New Employee",
            password="StrongPassword123!",
            role="EMPLOYEE",
        )

        response = self.client.post(
            self.url,
            {
                "user": new_user.id,
                "employee_id": "EMP-003",
                "department": self.finance.id,
                "position": self.financial_analyst.id,
                "hire_date": "2026-03-01",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_employee_cannot_update_profile(self):
        self.authenticate(self.employee)

        response = self.client.patch(
            f"{self.url}{self.profile.id}/",
            {
                "department": self.finance.id,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_hr_admin_cannot_delete_profile(self):
        self.authenticate(self.hr_admin)

        response = self.client.delete(
            f"{self.url}{self.profile.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_super_admin_can_delete_profile(self):
        self.authenticate(self.super_admin)

        response = self.client.delete(
            f"{self.url}{self.profile.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

    def test_hr_admin_cannot_create_duplicate_employee_profile(
        self,
    ):
        self.authenticate(self.hr_admin)

        response = self.client.post(
            self.url,
            {
                "user": self.employee.id,
                "employee_id": "EMP-003",
                "department": self.finance.id,
                "position": self.financial_analyst.id,
                "hire_date": "2026-03-01",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertIn(
            "user",
            response.data,
        )

    def test_employee_profile_department_filter_rejects_sql_injection_payload(
        self,
    ):
        """Department filter must reject SQL-like input."""
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {
                "department": "1 OR 1=1",
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_employee_profile_position_filter_rejects_sql_injection_payload(
        self,
    ):
        """Position filter must reject SQL-like input."""
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {
                "position": "1 OR 1=1",
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_employee_profiles_can_be_ordered_by_hire_date_descending(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"ordering": "-hire_date"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            2,
        )

        self.assertEqual(
            response.data["results"][0]["employee_id"],
            "EMP-002",
        )

        self.assertEqual(
            response.data["results"][1]["employee_id"],
            "EMP-001",
        )

    def test_employee_profiles_can_be_ordered_by_created_at(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"ordering": "created_at"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            2,
        )

        returned_ids = [
            profile["employee_id"]
            for profile in response.data["results"]
        ]

        self.assertEqual(
            set(returned_ids),
            {"EMP-001", "EMP-002"},
        )

    def test_employee_profiles_can_be_ordered_by_updated_at(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"ordering": "updated_at"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            2,
        )

        returned_ids = [
            profile["employee_id"]
            for profile in response.data["results"]
        ]

        self.assertEqual(
            set(returned_ids),
            {"EMP-001", "EMP-002"},
        )

    def test_employee_profiles_cannot_order_by_sensitive_field(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"ordering": "date_of_birth"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        returned_ids = [
            profile["employee_id"]
            for profile in response.data["results"]
        ]

        self.assertEqual(
            set(returned_ids),
            {"EMP-001", "EMP-002"},
        )

    def test_employee_profiles_can_combine_filters(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {
                "department": self.engineering.id,
                "hire_date": "2026-01-15",
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            1,
        )

        self.assertEqual(
            response.data["results"][0]["employee_id"],
            "EMP-001",
        )

    def test_employee_profiles_can_use_descending_employee_id_ordering(
        self,
    ):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"ordering": "-employee_id"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            2,
        )

        self.assertEqual(
            response.data["results"][0]["employee_id"],
            "EMP-002",
        )

        self.assertEqual(
            response.data["results"][1]["employee_id"],
            "EMP-001",
        )


    def test_employee_creation_creates_security_event(self):
        """Creating an employee creates an audit event."""

        self.authenticate(self.super_admin)

        new_user = User.objects.create_user(
            email="auditcreate@example.com",
            name="Audit Create",
            password="StrongPassword123!",
            role="EMPLOYEE",
        )

        self.client.defaults["HTTP_USER_AGENT"] = (
            "Test-Audit-Create"
        )

        response = self.client.post(
            self.url,
            {
                "user": new_user.id,
                "employee_id": "EMP-003",
                "department": self.engineering.id,
                "position": self.backend_developer.id,
                "hire_date": "2026-03-01",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        event = SecurityEvent.objects.filter(
            event_type="EMPLOYEE_CREATED"
        ).latest("created_at")

        self.assertEqual(
            event.user,
            self.super_admin,
        )
        self.assertEqual(
            event.user_agent,
            "Test-Audit-Create",
        )
        self.assertEqual(
            event.request_path,
            "/api/v1/employees/",
        )
        self.assertIn(
            "EMP-003",
            event.details,
        )

    def test_employee_update_creates_security_event(self):
        """Updating an employee creates an audit event."""

        self.authenticate(self.super_admin)

        self.client.defaults["HTTP_USER_AGENT"] = (
            "Test-Audit-Update"
        )

        response = self.client.patch(
            f"{self.url}{self.profile.id}/",
            {
                "position": self.senior_software_engineer.id,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        event = SecurityEvent.objects.filter(
            event_type="EMPLOYEE_UPDATED"
        ).latest("created_at")

        self.assertEqual(
            event.user,
            self.super_admin,
        )
        self.assertEqual(
            event.user_agent,
            "Test-Audit-Update",
        )
        self.assertEqual(
            event.request_path,
            f"{self.url}{self.profile.id}/",
        )
        self.assertIn(
            "EMP-001",
            event.details,
        )

    def test_employee_deletion_creates_security_event(self):
        """Deleting an employee creates an audit event."""

        self.authenticate(self.super_admin)

        self.client.defaults["HTTP_USER_AGENT"] = (
            "Test-Audit-Delete"
        )

        employee_id = self.profile.employee_id
        profile_id = self.profile.id

        response = self.client.delete(
            f"{self.url}{profile_id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        event = SecurityEvent.objects.filter(
            event_type="EMPLOYEE_DELETED"
        ).latest("created_at")

        self.assertEqual(
            event.user,
            self.super_admin,
        )
        self.assertEqual(
            event.user_agent,
            "Test-Audit-Delete",
        )
        self.assertEqual(
            event.request_path,
            f"{self.url}{profile_id}/",
        )
        self.assertIn(
            employee_id,
            event.details,
        )

    def test_employee_profiles_can_be_filtered_by_department(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"department": self.engineering.id},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            1,
        )

        self.assertEqual(
            response.data["results"][0]["employee_id"],
            "EMP-001",
        )

    def test_employee_profiles_can_be_filtered_by_position(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"position": self.hr_specialist.id},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            1,
        )

        self.assertEqual(
            response.data["results"][0]["employee_id"],
            "EMP-002",
        )

    def test_employee_profiles_can_be_filtered_by_hire_date(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"hire_date": "2026-01-15"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            1,
        )

        self.assertEqual(
            response.data["results"][0]["employee_id"],
            "EMP-001",
        )

    def test_employee_profiles_can_be_ordered_by_employee_id(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"ordering": "employee_id"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            2,
        )

        self.assertEqual(
            response.data["results"][0]["employee_id"],
            "EMP-001",
        )

        self.assertEqual(
            response.data["results"][1]["employee_id"],
            "EMP-002",
        )

    def test_request_with_disallowed_host_is_rejected(self):
        """Requests with an untrusted Host header must be rejected."""
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            HTTP_HOST="malicious.example.com",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

class DepartmentModelTests(TestCase):
    """Test Department model behavior."""

    def test_department_is_created(self):
        department = Department.objects.create(
            name="Engineering",
            code="ENG",
            description="Engineering department",
        )

        self.assertEqual(
            department.name,
            "Engineering",
        )
        self.assertEqual(
            department.code,
            "ENG",
        )

    def test_department_name_must_be_unique(self):
        Department.objects.create(
            name="Engineering",
            code="ENG",
        )

        with self.assertRaises(IntegrityError):
            Department.objects.create(
                name="Engineering",
                code="ENG2",
            )

    def test_department_code_must_be_unique(self):
        Department.objects.create(
            name="Engineering",
            code="ENG",
        )

        with self.assertRaises(IntegrityError):
            Department.objects.create(
                name="Human Resources",
                code="ENG",
            )

class PositionModelTests(TestCase):
    """Test Position model behavior."""

    def setUp(self):
        self.department = Department.objects.create(
            name="Engineering",
            code="ENG",
        )

    def test_position_is_created(self):
        position = Position.objects.create(
            title="Software Engineer",
            department=self.department,
            description="Software engineering position",
        )

        self.assertEqual(
            position.title,
            "Software Engineer",
        )
        self.assertEqual(
            position.department,
            self.department,
        )

    def test_position_belongs_to_department(self):
        position = Position.objects.create(
            title="Software Engineer",
            department=self.department,
        )

        self.assertIn(
            position,
            self.department.positions.all(),
        )

    def test_department_cannot_be_deleted_if_position_exists(self):
        Position.objects.create(
            title="Software Engineer",
            department=self.department,
        )

        with self.assertRaises(ProtectedError):
            self.department.delete()

class LeaveRequestModelTests(TestCase):
    """Test LeaveRequest model behavior."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="leave@example.com",
            name="Leave Employee",
            password="StrongPassword123!",
        )

        self.department = Department.objects.create(
            name="Engineering",
            code="ENG",
        )

        self.position = Position.objects.create(
            title="Software Engineer",
            department=self.department,
        )

        self.employee = EmployeeProfile.objects.create(
            user=self.user,
            employee_id="EMP-001",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 15),
        )

    def test_leave_request_is_created(self):
        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type="VACATION",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 5),
            reason="Family vacation",
        )

        self.assertEqual(
            leave_request.employee,
            self.employee,
        )
        self.assertEqual(
            leave_request.leave_type,
            "VACATION",
        )
        self.assertEqual(
            leave_request.status,
            "PENDING",
        )

    def test_leave_request_is_linked_to_employee(self):
        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type="SICK",
            start_date=date(2026, 9, 20),
            end_date=date(2026, 9, 21),
        )

        self.assertIn(
            leave_request,
            self.employee.leave_requests.all(),
        )

    def test_leave_request_string_representation(self):
        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type="VACATION",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 5),
        )

        self.assertEqual(
            str(leave_request),
            "EMP-001 - VACATION - 2026-10-01",
        )

    def test_review_fields_are_optional(self):
        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type="PERSONAL",
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 1),
        )

        self.assertIsNone(
            leave_request.reviewed_by,
        )
        self.assertIsNone(
            leave_request.reviewed_at,
        )

    def test_leave_request_can_be_approved(self):
        reviewer = User.objects.create_user(
            email="hr@example.com",
            name="HR Reviewer",
            password="StrongPassword123!",
            role="HR_ADMIN",
        )

        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type="VACATION",
            start_date=date(2026, 12, 1),
            end_date=date(2026, 12, 5),
        )

        leave_request.approve(reviewer)

        leave_request.refresh_from_db()

        self.assertEqual(
            leave_request.status,
            "APPROVED",
        )
        self.assertEqual(
            leave_request.reviewed_by,
            reviewer,
        )
        self.assertIsNotNone(
            leave_request.reviewed_at,
        )

    def test_end_date_cannot_be_before_start_date(self):
        leave_request = LeaveRequest(
            employee=self.employee,
            leave_type="VACATION",
            start_date=date(2026, 10, 10),
            end_date=date(2026, 10, 5),
        )

        with self.assertRaises(ValidationError):
            leave_request.full_clean()

    def test_pending_leave_request_can_be_rejected(self):
        reviewer = User.objects.create_user(
            email="reject@example.com",
            name="HR Reviewer",
            password="StrongPassword123!",
            role="HR_ADMIN",
        )

        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type="VACATION",
            start_date=date(2026, 12, 1),
            end_date=date(2026, 12, 5),
        )

        leave_request.reject(reviewer)

        leave_request.refresh_from_db()

        self.assertEqual(
            leave_request.status,
            "REJECTED",
        )
        self.assertEqual(
            leave_request.reviewed_by,
            reviewer,
        )
        self.assertIsNotNone(
            leave_request.reviewed_at,
        )

    def test_pending_leave_request_can_be_cancelled(self):
        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type="PERSONAL",
            start_date=date(2026, 12, 10),
            end_date=date(2026, 12, 10),
        )

        leave_request.cancel()

        leave_request.refresh_from_db()

        self.assertEqual(
            leave_request.status,
            "CANCELLED",
        )

    def test_approved_leave_request_cannot_be_approved_again(self):
        reviewer = User.objects.create_user(
            email="approve@example.com",
            name="HR Reviewer",
            password="StrongPassword123!",
            role="HR_ADMIN",
        )

        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type="VACATION",
            start_date=date(2026, 12, 1),
            end_date=date(2026, 12, 5),
        )

        leave_request.approve(reviewer)

        with self.assertRaises(ValidationError):
            leave_request.approve(reviewer)

    def test_rejected_leave_request_cannot_be_cancelled(self):
        reviewer = User.objects.create_user(
            email="reject-cancel@example.com",
            name="HR Reviewer",
            password="StrongPassword123!",
            role="HR_ADMIN",
        )

        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type="SICK",
            start_date=date(2026, 12, 15),
            end_date=date(2026, 12, 16),
        )

        leave_request.reject(reviewer)

        with self.assertRaises(ValidationError):
            leave_request.cancel()

class LeaveRequestSerializerTests(TestCase):
    """Test LeaveRequest serializer behavior."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="serializer@example.com",
            name="Serializer Employee",
            password="StrongPassword123!",
        )

        self.department = Department.objects.create(
            name="Engineering",
            code="ENG",
        )

        self.position = Position.objects.create(
            title="Software Engineer",
            department=self.department,
        )

        self.employee = EmployeeProfile.objects.create(
            user=self.user,
            employee_id="EMP-001",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 15),
        )

    def test_valid_leave_request_data(self):
        data = {
            "employee": self.employee.id,
            "leave_type": "VACATION",
            "start_date": "2026-10-01",
            "end_date": "2026-10-05",
            "reason": "Family vacation",
        }

        serializer = LeaveRequestSerializer(
            data=data,
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

    def test_end_date_cannot_be_before_start_date(self):
        data = {
            "employee": self.employee.id,
            "leave_type": "VACATION",
            "start_date": "2026-10-10",
            "end_date": "2026-10-05",
            "reason": "Invalid date range",
        }

        serializer = LeaveRequestSerializer(
            data=data,
        )

        self.assertFalse(
            serializer.is_valid(),
        )

        self.assertIn(
            "end_date",
            serializer.errors,
        )

    def test_status_is_read_only(self):
        data = {
            "employee": self.employee.id,
            "leave_type": "VACATION",
            "start_date": "2026-10-01",
            "end_date": "2026-10-05",
            "status": "APPROVED",
        }

        serializer = LeaveRequestSerializer(
            data=data,
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

        leave_request = serializer.save()

        self.assertEqual(
            leave_request.status,
            "PENDING",
        )

    def test_reviewed_by_is_read_only(self):
        reviewer = User.objects.create_user(
            email="reviewer@example.com",
            name="HR Reviewer",
            password="StrongPassword123!",
            role="HR_ADMIN",
        )

        data = {
            "employee": self.employee.id,
            "leave_type": "PERSONAL",
            "start_date": "2026-10-10",
            "end_date": "2026-10-10",
            "reviewed_by": reviewer.id,
        }

        serializer = LeaveRequestSerializer(
            data=data,
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

        leave_request = serializer.save()

        self.assertIsNone(
            leave_request.reviewed_by,
        )

    def test_reviewed_at_is_read_only(self):
        data = {
            "employee": self.employee.id,
            "leave_type": "SICK",
            "start_date": "2026-10-15",
            "end_date": "2026-10-16",
            "reviewed_at": "2026-10-01T10:00:00Z",
        }

        serializer = LeaveRequestSerializer(
            data=data,
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

        leave_request = serializer.save()

        self.assertIsNone(
            leave_request.reviewed_at,
        )

    def test_leave_type_is_required(self):
        data = {
            "employee": self.employee.id,
            "start_date": "2026-10-01",
            "end_date": "2026-10-05",
        }

        serializer = LeaveRequestSerializer(
            data=data,
        )

        self.assertFalse(
            serializer.is_valid(),
        )

        self.assertIn(
            "leave_type",
            serializer.errors,
        )

    def test_employee_is_required(self):
        data = {
            "leave_type": "VACATION",
            "start_date": "2026-10-01",
            "end_date": "2026-10-05",
        }

        serializer = LeaveRequestSerializer(
            data=data,
        )

        self.assertFalse(
            serializer.is_valid(),
        )

        self.assertIn(
            "employee",
            serializer.errors,
        )

class LeaveRequestRBACAPITests(TestCase):
    """Tests for leave request API role-based access control."""

    def setUp(self):
        self.client = APIClient()

        self.super_admin = User.objects.create_user(
            email="admin@example.com",
            name="Super Admin",
            password="StrongPassword123!",
            role="SUPER_ADMIN",
            is_staff=True,
            is_superuser=True,
        )

        self.hr_admin = User.objects.create_user(
            email="hradmin@example.com",
            name="HR Admin",
            password="StrongPassword123!",
            role="HR_ADMIN",
        )

        self.hr_manager = User.objects.create_user(
            email="manager@example.com",
            name="HR Manager",
            password="StrongPassword123!",
            role="HR_MANAGER",
        )

        self.employee = User.objects.create_user(
            email="employee@example.com",
            name="John Employee",
            password="StrongPassword123!",
            role="EMPLOYEE",
        )

        self.other_employee = User.objects.create_user(
            email="other@example.com",
            name="Other Employee",
            password="StrongPassword123!",
            role="EMPLOYEE",
        )

        self.department = Department.objects.create(
            name="Engineering",
            code="ENG",
        )

        self.position = Position.objects.create(
            title="Software Engineer",
            department=self.department,
        )

        self.manager_profile = EmployeeProfile.objects.create(
            user=self.hr_manager,
            employee_id="EMP-003",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 10),
        )

        self.finance_department = Department.objects.create(
            name="Finance",
            code="FIN",
        )

        self.finance_position = Position.objects.create(
            title="Financial Analyst",
            department=self.finance_department,
        )

        self.finance_employee = User.objects.create_user(
            email="finance@example.com",
            name="Finance Employee",
            password="StrongPassword123!",
            role="EMPLOYEE",
        )

        self.finance_employee_profile = EmployeeProfile.objects.create(
            user=self.finance_employee,
            employee_id="EMP-004",
            department=self.finance_department,
            position=self.finance_position,
            hire_date=date(2026, 3, 1),
        )
        self.employee_profile = EmployeeProfile.objects.create(
            user=self.employee,
            employee_id="EMP-001",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 15),
        )

        self.other_employee_profile = (
            EmployeeProfile.objects.create(
                user=self.other_employee,
                employee_id="EMP-002",
                department=self.department,
                position=self.position,
                hire_date=date(2026, 2, 1),
            )
        )

        self.leave_request = LeaveRequest.objects.create(
            employee=self.employee_profile,
            leave_type="VACATION",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 5),
            reason="Annual vacation.",
        )

        self.other_leave_request = (
            LeaveRequest.objects.create(
                employee=self.other_employee_profile,
                leave_type="SICK",
                start_date=date(2026, 10, 10),
                end_date=date(2026, 10, 12),
                reason="Medical leave.",
            )
        )

        self.finance_leave_request = LeaveRequest.objects.create(
            employee=self.finance_employee_profile,
            leave_type="PERSONAL",
            start_date=date(2026, 11, 15),
            end_date=date(2026, 11, 17),
            reason="Finance department leave.",
        )
        self.url = "/api/v1/employees/leave-requests/"

    def authenticate(self, user):
        """Authenticate the API client as the given user."""

        self.client.force_authenticate(
            user=user
        )

    def test_unauthenticated_user_is_rejected(self):
        """Unauthenticated users cannot access leave requests."""

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_employee_can_list_own_leave_requests(self):
        """Employees can only list their own requests."""

        self.authenticate(self.employee)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            1,
        )

        self.assertEqual(
            response.data["results"][0]["employee"],
            self.employee_profile.id,
        )

    def test_employee_cannot_retrieve_other_employee_request(
        self,
    ):
        """Employees cannot access another employee's request."""

        self.authenticate(self.employee)

        response = self.client.get(
            f"{self.url}{self.other_leave_request.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_employee_cannot_assign_leave_request_to_other_employee(self):
        """Employees can create their own leave requests."""

        self.authenticate(self.employee)

        response = self.client.post(
            self.url,
            {
                "employee": self.other_employee_profile.id,
                "leave_type": "VACATION",
                "start_date": "2026-11-01",
                "end_date": "2026-11-05",
                "reason": "Personal vacation.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        leave_request = LeaveRequest.objects.get(
            id=response.data["id"]
        )

        self.assertEqual(
            leave_request.employee,
            self.employee_profile,
        )

    def test_employee_cannot_approve_leave_request(self):
        """Employees cannot approve leave requests."""

        self.authenticate(self.employee)

        response = self.client.post(
            f"{self.url}{self.leave_request.id}/approve/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_employee_cannot_reject_leave_request(self):
        """Employees cannot reject leave requests."""

        self.authenticate(self.employee)

        response = self.client.post(
            f"{self.url}{self.leave_request.id}/reject/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_employee_can_cancel_own_pending_request(self):
        """Employees can cancel their own pending requests."""

        self.authenticate(self.employee)

        response = self.client.post(
            f"{self.url}{self.leave_request.id}/cancel/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.leave_request.refresh_from_db()

        self.assertEqual(
            self.leave_request.status,
            "CANCELLED",
        )

    def test_employee_cannot_cancel_other_employee_request(self,):
        """Employees cannot cancel another employee's request."""

        self.authenticate(self.employee)

        response = self.client.post(
            f"{self.url}{self.other_leave_request.id}/cancel/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_hr_manager_can_list_department_leave_requests(self):
        """HR managers can view all leave requests."""

        self.authenticate(self.hr_manager)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            2,
        )


    def test_hr_manager_cannot_retrieve_other_department_request(self):
        """HR managers cannot retrieve requests from another department."""

        self.authenticate(self.hr_manager)

        response = self.client.get(
            f"{self.url}{self.finance_leave_request.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_hr_manager_cannot_approve_other_department_request(self):
        """HR managers cannot approve requests from another department."""

        self.authenticate(self.hr_manager)

        response = self.client.post(
            f"{self.url}{self.finance_leave_request.id}/approve/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        self.finance_leave_request.refresh_from_db()

        self.assertEqual(
            self.finance_leave_request.status,
            "PENDING",
        )


    def test_hr_manager_can_approve_leave_request(self):
        """HR managers can approve pending requests."""

        self.authenticate(self.hr_manager)

        response = self.client.post(
            f"{self.url}{self.leave_request.id}/approve/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.leave_request.refresh_from_db()

        self.assertEqual(
            self.leave_request.status,
            "APPROVED",
        )

        self.assertEqual(
            self.leave_request.reviewed_by,
            self.hr_manager,
        )

    def test_hr_manager_can_reject_leave_request(self):
        """HR managers can reject pending requests."""

        self.authenticate(self.hr_manager)

        response = self.client.post(
            f"{self.url}{self.leave_request.id}/reject/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.leave_request.refresh_from_db()

        self.assertEqual(
            self.leave_request.status,
            "REJECTED",
        )

        self.assertEqual(
            self.leave_request.reviewed_by,
            self.hr_manager,
        )

    def test_hr_admin_can_approve_leave_request(self):
        """HR admins can approve pending requests."""

        self.authenticate(self.hr_admin)

        response = self.client.post(
            f"{self.url}{self.leave_request.id}/approve/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.leave_request.refresh_from_db()

        self.assertEqual(
            self.leave_request.status,
            "APPROVED",
        )


    def test_hr_admin_can_list_all_department_leave_requests(self):
        """HR admins can view requests across all departments."""

        self.authenticate(self.hr_admin)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        returned_ids = {
            leave["id"]
            for leave in response.data["results"]
        }

        self.assertEqual(
            returned_ids,
            {
                self.leave_request.id,
                self.other_leave_request.id,
                self.finance_leave_request.id,
            },
        )


    def test_super_admin_can_approve_leave_request(self):
        """Super admins can approve pending requests."""

        self.authenticate(self.super_admin)

        response = self.client.post(
            f"{self.url}{self.leave_request.id}/approve/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.leave_request.refresh_from_db()

        self.assertEqual(
            self.leave_request.status,
            "APPROVED",
        )

    def test_delete_leave_request_is_not_allowed(self):
        """Leave requests cannot be directly deleted."""

        self.authenticate(self.super_admin)

        response = self.client.delete(
            f"{self.url}{self.leave_request.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

        self.assertTrue(
            LeaveRequest.objects.filter(
                id=self.leave_request.id
            ).exists()
        )

    def test_employee_cannot_modify_status_directly(self):
        """Employees cannot modify leave status directly."""

        self.authenticate(self.employee)

        response = self.client.patch(
            f"{self.url}{self.leave_request.id}/",
            {
                "status": "APPROVED",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.leave_request.refresh_from_db()

        self.assertEqual(
            self.leave_request.status,
            "PENDING",
        )

    def test_leave_request_creation_creates_security_event(self):
        """Creating a leave request creates a SIEM event."""

        self.authenticate(self.employee)

        response = self.client.post(
            self.url,
            {
                "employee": self.employee_profile.id,
                "leave_type": "PERSONAL",
                "start_date": "2026-12-01",
                "end_date": "2026-12-02",
                "reason": "Personal matter.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        event = SecurityEvent.objects.filter(
            event_type="LEAVE_REQUEST_CREATED"
        ).latest("created_at")

        self.assertEqual(
            event.user,
            self.employee,
        )

        self.assertEqual(
            event.request_path,
            self.url,
        )

    def test_approval_creates_security_event(self):
        """Approving a leave request creates a SIEM event."""

        self.authenticate(self.hr_manager)

        response = self.client.post(
            f"{self.url}{self.leave_request.id}/approve/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        event = SecurityEvent.objects.filter(
            event_type="LEAVE_REQUEST_APPROVED"
        ).latest("created_at")

        self.assertEqual(
            event.user,
            self.hr_manager,
        )

    def test_rejection_creates_security_event(self):
        """Rejecting a leave request creates a SIEM event."""

        self.authenticate(self.hr_manager)

        response = self.client.post(
            f"{self.url}{self.leave_request.id}/reject/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        event = SecurityEvent.objects.filter(
            event_type="LEAVE_REQUEST_REJECTED"
        ).latest("created_at")

        self.assertEqual(
            event.user,
            self.hr_manager,
        )

    def test_cancellation_creates_security_event(self):
        """Cancelling a leave request creates a SIEM event."""

        self.authenticate(self.employee)

        response = self.client.post(
            f"{self.url}{self.leave_request.id}/cancel/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        event = SecurityEvent.objects.filter(
            event_type="LEAVE_REQUEST_CANCELLED"
        ).latest("created_at")

        self.assertEqual(
            event.user,
            self.employee,
        )


    def test_leave_requests_can_be_filtered_by_leave_type(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"leave_type": "VACATION"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            1,
        )

        self.assertEqual(
            response.data["results"][0]["id"],
            self.leave_request.id,
        )

    def test_leave_requests_can_be_filtered_by_status(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"status": "PENDING"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            2,
        )

    def test_leave_requests_can_be_filtered_by_start_date(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"start_date": "2026-10-01"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            1,
        )

        self.assertEqual(
            response.data["results"][0]["id"],
            self.leave_request.id,
        )

    def test_leave_requests_can_be_filtered_by_end_date(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"end_date": "2026-10-12"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            1,
        )

        self.assertEqual(
            response.data["results"][0]["id"],
            self.other_leave_request.id,
        )

    def test_leave_requests_can_be_filtered_by_employee(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"employee": self.employee_profile.id},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            1,
        )

        self.assertEqual(
            response.data["results"][0]["id"],
            self.leave_request.id,
        )

    def test_leave_requests_can_be_ordered_by_start_date(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"ordering": "start_date"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            2,
        )

        self.assertEqual(
            response.data["results"][0]["id"],
            self.leave_request.id,
        )

        self.assertEqual(
            response.data["results"][1]["id"],
            self.other_leave_request.id,
        )

    def test_leave_requests_can_be_ordered_by_end_date_descending(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"ordering": "-end_date"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            2,
        )

        self.assertEqual(
            response.data["results"][0]["id"],
            self.other_leave_request.id,
        )

        self.assertEqual(
            response.data["results"][1]["id"],
            self.leave_request.id,
        )

    def test_leave_requests_can_be_ordered_by_created_at(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"ordering": "created_at"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            2,
        )

        returned_ids = [
            leave["id"]
            for leave in response.data["results"]
        ]

        self.assertEqual(
            set(returned_ids),
            {
                self.leave_request.id,
                self.other_leave_request.id,
            },
        )

    def test_leave_requests_can_be_ordered_by_updated_at(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"ordering": "updated_at"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            2,
        )

        returned_ids = [
            leave["id"]
            for leave in response.data["results"]
        ]

        self.assertEqual(
            set(returned_ids),
            {
                self.leave_request.id,
                self.other_leave_request.id,
            },
        )

    def test_leave_requests_cannot_be_filtered_by_reason(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"reason": "Annual vacation."},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            2,
        )

    def test_leave_requests_can_combine_filters(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {
                "leave_type": "VACATION",
                "start_date": "2026-10-01",
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            1,
        )

        self.assertEqual(
            response.data["results"][0]["id"],
            self.leave_request.id,
        )

    def test_hr_manager_without_profile_is_forbidden(self):
        """HR managers without an employee profile are denied."""

        manager_without_profile = User.objects.create_user(
            email="manager.noprofile@example.com",
            name="Manager Without Profile",
            password="StrongPassword123!",
            role="HR_MANAGER",
        )

        self.authenticate(manager_without_profile)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_employee_without_profile_gets_forbidden_on_create(self):
        """Employees without a profile cannot submit leave requests."""

        employee_without_profile = User.objects.create_user(
            email="employee.noprofile@example.com",
            name="Employee Without Profile",
            password="StrongPassword123!",
            role="EMPLOYEE",
        )

        self.authenticate(employee_without_profile)

        response = self.client.post(
            self.url,
            {
                "leave_type": "VACATION",
                "start_date": "2026-12-10",
                "end_date": "2026-12-12",
                "reason": "Personal vacation.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

class PayPeriodModelTests(TestCase):
    """Tests for PayPeriod business rules."""

    def test_pay_period_can_be_created(self):
        """A valid pay period can be created."""

        pay_period = PayPeriod.objects.create(
            name="October 1-15, 2026",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 15),
            payment_date=date(2026, 10, 20),
        )

        self.assertEqual(
            pay_period.name,
            "October 1-15, 2026",
        )

        self.assertEqual(
            pay_period.status,
            "OPEN",
        )

    def test_pay_period_defaults_to_open(self):
        """New pay periods default to OPEN."""

        pay_period = PayPeriod.objects.create(
            name="October 16-31, 2026",
            start_date=date(2026, 10, 16),
            end_date=date(2026, 10, 31),
            payment_date=date(2026, 11, 5),
        )

        self.assertEqual(
            pay_period.status,
            "OPEN",
        )

    def test_start_date_cannot_be_after_end_date(self):
        """Start date cannot be after end date."""

        with self.assertRaises(ValidationError):
            PayPeriod.objects.create(
                name="Invalid Period",
                start_date=date(2026, 10, 20),
                end_date=date(2026, 10, 15),
                payment_date=date(2026, 10, 20),
            )

    def test_payment_date_cannot_be_before_end_date(self):
        """Payment date cannot be before the period end date."""

        with self.assertRaises(ValidationError):
            PayPeriod.objects.create(
                name="Invalid Payment Date",
                start_date=date(2026, 10, 1),
                end_date=date(2026, 10, 15),
                payment_date=date(2026, 10, 10),
            )

    def test_pay_period_name_must_be_unique(self):
        """Pay period names must be unique."""

        PayPeriod.objects.create(
            name="November 1-15, 2026",
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 15),
            payment_date=date(2026, 11, 20),
        )

        with self.assertRaises(ValidationError):
            PayPeriod.objects.create(
                name="November 1-15, 2026",
                start_date=date(2026, 11, 1),
                end_date=date(2026, 11, 15),
                payment_date=date(2026, 11, 20),
            )

    def test_pay_period_string_representation(self):
        """Pay period string representation returns its name."""

        pay_period = PayPeriod.objects.create(
            name="December 1-15, 2026",
            start_date=date(2026, 12, 1),
            end_date=date(2026, 12, 15),
            payment_date=date(2026, 12, 20),
        )

        self.assertEqual(
            str(pay_period),
            "December 1-15, 2026",
        )

class PayrollModelTests(TestCase):
    """Tests for Payroll business rules."""

    def setUp(self):
        self.admin = User.objects.create_user(
            email="payroll-admin@example.com",
            name="Payroll Admin",
            password="StrongPassword123!",
            role="HR_ADMIN",
        )

        self.pay_period = PayPeriod.objects.create(
            name="January 1-15, 2027",
            start_date=date(2027, 1, 1),
            end_date=date(2027, 1, 15),
            payment_date=date(2027, 1, 20),
        )

    def test_payroll_can_be_created(self):
        """A valid payroll can be created."""

        payroll = Payroll.objects.create(
            pay_period=self.pay_period,
        )

        self.assertEqual(
            payroll.pay_period,
            self.pay_period,
        )

        self.assertEqual(
            payroll.status,
            "DRAFT",
        )

    def test_payroll_defaults_to_draft(self):
        """New payrolls default to DRAFT."""

        payroll = Payroll.objects.create(
            pay_period=self.pay_period,
        )

        self.assertEqual(
            payroll.status,
            "DRAFT",
        )

    def test_pay_period_can_have_only_one_payroll(self):
        """A pay period cannot have multiple payrolls."""

        Payroll.objects.create(
            pay_period=self.pay_period,
        )

        with self.assertRaises(ValidationError):
            Payroll.objects.create(
                pay_period=self.pay_period,
            )

    def test_processed_payroll_requires_processed_at(self):
        """Processed payrolls must have a processed date."""

        with self.assertRaises(ValidationError):
            Payroll.objects.create(
                pay_period=self.pay_period,
                status="PROCESSED",
                processed_by=self.admin,
            )

    def test_processed_payroll_requires_processed_by(self):
        """Processed payrolls must have a processor."""

        with self.assertRaises(ValidationError):
            Payroll.objects.create(
                pay_period=self.pay_period,
                status="PROCESSED",
                processed_at=timezone.now(),
            )

    def test_processed_payroll_can_be_created(self):
        """A processed payroll requires both processing fields."""

        processed_at = timezone.now()

        payroll = Payroll.objects.create(
            pay_period=self.pay_period,
            status="PROCESSED",
            processed_at=processed_at,
            processed_by=self.admin,
        )

        self.assertEqual(
            payroll.status,
            "PROCESSED",
        )

        self.assertEqual(
            payroll.processed_by,
            self.admin,
        )

        self.assertEqual(
            payroll.processed_at,
            processed_at,
        )

    def test_payroll_string_representation(self):
        """Payroll string representation includes period and status."""

        payroll = Payroll.objects.create(
            pay_period=self.pay_period,
        )

        self.assertEqual(
            str(payroll),
            "January 1-15, 2027 - DRAFT",
        )

class PayrollRecordModelTests(TestCase):
    """Tests for PayrollRecord business rules."""

    def setUp(self):
        self.admin = User.objects.create_user(
            email="payroll-admin@example.com",
            name="Payroll Admin",
            password="StrongPassword123!",
            role="HR_ADMIN",
        )

        self.employee_user = User.objects.create_user(
            email="employee-payroll@example.com",
            name="Payroll Employee",
            password="StrongPassword123!",
            role="EMPLOYEE",
        )

        self.department = Department.objects.create(
            name="Finance",
            code="FIN",
        )

        self.position = Position.objects.create(
            title="Accountant",
            department=self.department,
        )

        self.employee = EmployeeProfile.objects.create(
            user=self.employee_user,
            employee_id="PAY-001",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 15),
        )

        self.pay_period = PayPeriod.objects.create(
            name="January 1-15, 2027",
            start_date=date(2027, 1, 1),
            end_date=date(2027, 1, 15),
            payment_date=date(2027, 1, 20),
        )

        self.payroll = Payroll.objects.create(
            pay_period=self.pay_period,
        )

    def test_payroll_record_can_be_created(self):
        """A valid payroll record can be created."""

        record = PayrollRecord.objects.create(
            payroll=self.payroll,
            employee=self.employee,
            base_salary=3000,
            total_earnings=500,
            gross_pay=3500,
            total_deductions=700,
            net_pay=2800,
        )

        self.assertEqual(
            record.employee,
            self.employee,
        )

        self.assertEqual(
            record.payroll,
            self.payroll,
        )

    def test_payroll_record_defaults_to_pending(self):
        """New payroll records default to PENDING."""

        record = PayrollRecord.objects.create(
            payroll=self.payroll,
            employee=self.employee,
            base_salary=3000,
            total_earnings=500,
            gross_pay=3500,
            total_deductions=700,
            net_pay=2800,
        )

        self.assertEqual(
            record.status,
            "PENDING",
        )

    def test_base_salary_cannot_be_negative(self):
        """Base salary cannot be negative."""

        with self.assertRaises(ValidationError):
            PayrollRecord.objects.create(
                payroll=self.payroll,
                employee=self.employee,
                base_salary=-100,
                total_earnings=500,
                gross_pay=400,
                total_deductions=100,
                net_pay=300,
            )

    def test_total_earnings_cannot_be_negative(self):
        """Total earnings cannot be negative."""

        with self.assertRaises(ValidationError):
            PayrollRecord.objects.create(
                payroll=self.payroll,
                employee=self.employee,
                base_salary=3000,
                total_earnings=-500,
                gross_pay=2500,
                total_deductions=500,
                net_pay=2000,
            )

    def test_total_deductions_cannot_be_negative(self):
        """Total deductions cannot be negative."""

        with self.assertRaises(ValidationError):
            PayrollRecord.objects.create(
                payroll=self.payroll,
                employee=self.employee,
                base_salary=3000,
                total_earnings=500,
                gross_pay=3500,
                total_deductions=-500,
                net_pay=4000,
            )

    def test_gross_pay_must_match_calculation(self):
        """Gross pay must equal base salary plus earnings."""

        with self.assertRaises(ValidationError):
            PayrollRecord.objects.create(
                payroll=self.payroll,
                employee=self.employee,
                base_salary=3000,
                total_earnings=500,
                gross_pay=3200,
                total_deductions=500,
                net_pay=2700,
            )

    def test_net_pay_must_match_calculation(self):
        """Net pay must equal gross pay minus deductions."""

        with self.assertRaises(ValidationError):
            PayrollRecord.objects.create(
                payroll=self.payroll,
                employee=self.employee,
                base_salary=3000,
                total_earnings=500,
                gross_pay=3500,
                total_deductions=500,
                net_pay=2500,
            )

    def test_net_pay_cannot_be_negative(self):
        """Net pay cannot be negative."""

        with self.assertRaises(ValidationError):
            PayrollRecord.objects.create(
                payroll=self.payroll,
                employee=self.employee,
                base_salary=3000,
                total_earnings=500,
                gross_pay=3500,
                total_deductions=4000,
                net_pay=-500,
            )

    def test_employee_can_have_only_one_record_per_payroll(self):
        """An employee cannot have duplicate payroll records."""

        PayrollRecord.objects.create(
            payroll=self.payroll,
            employee=self.employee,
            base_salary=3000,
            total_earnings=500,
            gross_pay=3500,
            total_deductions=700,
            net_pay=2800,
        )

        with self.assertRaises(ValidationError):
            PayrollRecord.objects.create(
                payroll=self.payroll,
                employee=self.employee,
                base_salary=3000,
                total_earnings=300,
                gross_pay=3300,
                total_deductions=600,
                net_pay=2700,
            )

    def test_payroll_record_string_representation(self):
        """Payroll record string representation is readable."""

        record = PayrollRecord.objects.create(
            payroll=self.payroll,
            employee=self.employee,
            base_salary=3000,
            total_earnings=500,
            gross_pay=3500,
            total_deductions=700,
            net_pay=2800,
        )

        self.assertEqual(
            str(record),
            "PAY-001 - January 1-15, 2027",
        )

class EarningModelTests(TestCase):
    """Test Earning model behavior."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="earning@example.com",
            name="Earning Employee",
            password="TestPass123!",
        )

        self.department = Department.objects.create(
            name="Finance",
            code="FIN",
        )

        self.position = Position.objects.create(
            title="Financial Analyst",
            department=self.department,
        )

        self.employee = EmployeeProfile.objects.create(
            user=self.user,
            employee_id="EMP-EARNING-001",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 1),
        )

        self.pay_period = PayPeriod.objects.create(
            name="Earning Test Period",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 15),
            payment_date=date(2026, 9, 20),
        )

        self.payroll = Payroll.objects.create(
            pay_period=self.pay_period,
        )

        self.payroll_record = PayrollRecord.objects.create(
            payroll=self.payroll,
            employee=self.employee,
            base_salary=3000,
            total_earnings=500,
            gross_pay=3500,
            total_deductions=300,
            net_pay=3200,
        )

    def test_create_valid_earning(self):
        earning = Earning.objects.create(
            payroll_record=self.payroll_record,
            earning_type="OVERTIME",
            description="Overtime hours",
            amount=250,
        )

        self.assertEqual(
            earning.payroll_record,
            self.payroll_record,
        )

        self.assertEqual(
            earning.amount,
            250,
        )

    def test_earning_amount_cannot_be_negative(self):
        earning = Earning(
            payroll_record=self.payroll_record,
            earning_type="BONUS",
            description="Negative bonus",
            amount=-100,
        )

        with self.assertRaises(ValidationError):
            earning.save()

    def test_earning_str(self):
        earning = Earning.objects.create(
            payroll_record=self.payroll_record,
            earning_type="BONUS",
            description="Performance bonus",
            amount=500,
        )

        self.assertEqual(
            str(earning),
            "EMP-EARNING-001 - BONUS - 500",
        )

    def test_multiple_earnings_can_belong_to_same_payroll_record(self):
        Earning.objects.create(
            payroll_record=self.payroll_record,
            earning_type="OVERTIME",
            description="Overtime",
            amount=200,
        )

        Earning.objects.create(
            payroll_record=self.payroll_record,
            earning_type="BONUS",
            description="Bonus",
            amount=300,
        )

        self.assertEqual(
            self.payroll_record.earnings.count(),
            2,
        )

    def test_payroll_record_deletion_is_protected(self):
        Earning.objects.create(
            payroll_record=self.payroll_record,
            earning_type="ALLOWANCE",
            description="Transport allowance",
            amount=100,
        )

        with self.assertRaises(ProtectedError):
            self.payroll_record.delete()

    def test_zero_amount_is_allowed(self):
        earning = Earning.objects.create(
            payroll_record=self.payroll_record,
            earning_type="OTHER",
            description="Zero earning",
            amount=0,
        )

        self.assertEqual(
            earning.amount,
            0,
        )

class DeductionModelTests(TestCase):
    """Test Deduction model behavior."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="deduction@example.com",
            name="Deduction Employee",
            password="TestPass123!",
        )

        self.department = Department.objects.create(
            name="Human Resources",
            code="HR",
        )

        self.position = Position.objects.create(
            title="HR Specialist",
            department=self.department,
        )

        self.employee = EmployeeProfile.objects.create(
            user=self.user,
            employee_id="EMP-DEDUCTION-001",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 1),
        )

        self.pay_period = PayPeriod.objects.create(
            name="Deduction Test Period",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 15),
            payment_date=date(2026, 9, 20),
        )

        self.payroll = Payroll.objects.create(
            pay_period=self.pay_period,
        )

        self.payroll_record = PayrollRecord.objects.create(
            payroll=self.payroll,
            employee=self.employee,
            base_salary=3000,
            total_earnings=500,
            gross_pay=3500,
            total_deductions=300,
            net_pay=3200,
        )

    def test_create_valid_deduction(self):
        deduction = Deduction.objects.create(
            payroll_record=self.payroll_record,
            deduction_type="TAX",
            description="Federal tax",
            amount=250,
        )

        self.assertEqual(
            deduction.payroll_record,
            self.payroll_record,
        )

        self.assertEqual(
            deduction.amount,
            250,
        )

    def test_deduction_amount_cannot_be_negative(self):
        deduction = Deduction(
            payroll_record=self.payroll_record,
            deduction_type="INSURANCE",
            description="Negative insurance",
            amount=-100,
        )

        with self.assertRaises(ValidationError):
            deduction.save()

    def test_deduction_str(self):
        deduction = Deduction.objects.create(
            payroll_record=self.payroll_record,
            deduction_type="RETIREMENT",
            description="Retirement contribution",
            amount=300,
        )

        self.assertEqual(
            str(deduction),
            "EMP-DEDUCTION-001 - RETIREMENT - 300",
        )

    def test_multiple_deductions_can_belong_to_same_payroll_record(self):
        Deduction.objects.create(
            payroll_record=self.payroll_record,
            deduction_type="TAX",
            description="Federal tax",
            amount=200,
        )

        Deduction.objects.create(
            payroll_record=self.payroll_record,
            deduction_type="INSURANCE",
            description="Health insurance",
            amount=100,
        )

        self.assertEqual(
            self.payroll_record.deductions.count(),
            2,
        )

    def test_payroll_record_deletion_is_protected(self):
        Deduction.objects.create(
            payroll_record=self.payroll_record,
            deduction_type="BENEFIT",
            description="Employee benefit",
            amount=100,
        )

        with self.assertRaises(ProtectedError):
            self.payroll_record.delete()

    def test_zero_amount_is_allowed(self):
        deduction = Deduction.objects.create(
            payroll_record=self.payroll_record,
            deduction_type="OTHER",
            description="Zero deduction",
            amount=0,
        )

        self.assertEqual(
            deduction.amount,
            0,
        )

class PaymentModelTests(TestCase):
    """Test Payment model behavior."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="payment@example.com",
            name="Payment Employee",
            password="TestPass123!",
        )

        self.department = Department.objects.create(
            name="Operations",
            code="OPS",
        )

        self.position = Position.objects.create(
            title="Operations Specialist",
            department=self.department,
        )

        self.employee = EmployeeProfile.objects.create(
            user=self.user,
            employee_id="EMP-PAYMENT-001",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 1),
        )

        self.pay_period = PayPeriod.objects.create(
            name="Payment Test Period",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 15),
            payment_date=date(2026, 9, 20),
        )

        self.payroll = Payroll.objects.create(
            pay_period=self.pay_period,
        )

        self.payroll_record = PayrollRecord.objects.create(
            payroll=self.payroll,
            employee=self.employee,
            base_salary=3000,
            total_earnings=500,
            gross_pay=3500,
            total_deductions=300,
            net_pay=3200,
        )

    def test_create_valid_payment(self):
        payment = Payment.objects.create(
            payroll_record=self.payroll_record,
            amount=3200,
            payment_method="DIRECT_DEPOSIT",
            transaction_reference="TXN-001",
        )

        self.assertEqual(
            payment.payroll_record,
            self.payroll_record,
        )

        self.assertEqual(
            payment.amount,
            3200,
        )

        self.assertEqual(
            payment.status,
            "PENDING",
        )

    def test_payment_amount_cannot_be_negative(self):
        payment = Payment(
            payroll_record=self.payroll_record,
            amount=-100,
            payment_method="CHECK",
        )

        with self.assertRaises(ValidationError):
            payment.save()

    def test_completed_payment_requires_payment_date(self):
        payment = Payment(
            payroll_record=self.payroll_record,
            amount=3200,
            payment_method="DIRECT_DEPOSIT",
            status="COMPLETED",
        )

        with self.assertRaises(ValidationError):
            payment.save()

    def test_completed_payment_with_date_is_valid(self):
        payment = Payment.objects.create(
            payroll_record=self.payroll_record,
            amount=3200,
            payment_method="DIRECT_DEPOSIT",
            status="COMPLETED",
            payment_date=timezone.now(),
            transaction_reference="TXN-002",
        )

        self.assertEqual(
            payment.status,
            "COMPLETED",
        )

        self.assertIsNotNone(
            payment.payment_date,
        )

    def test_transaction_reference_must_be_unique(self):
        Payment.objects.create(
            payroll_record=self.payroll_record,
            amount=3200,
            payment_method="DIRECT_DEPOSIT",
            transaction_reference="TXN-003",
        )

        duplicate = Payment(
            payroll_record=self.payroll_record,
            amount=3200,
            payment_method="DIRECT_DEPOSIT",
            transaction_reference="TXN-003",
        )

        with self.assertRaises(ValidationError):
            duplicate.save()

    def test_payroll_record_deletion_is_protected(self):
        Payment.objects.create(
            payroll_record=self.payroll_record,
            amount=3200,
            payment_method="DIRECT_DEPOSIT",
            transaction_reference="TXN-004",
        )

        with self.assertRaises(ProtectedError):
            self.payroll_record.delete()

    def test_multiple_payments_can_belong_to_same_payroll_record(self):
        Payment.objects.create(
            payroll_record=self.payroll_record,
            amount=1600,
            payment_method="CHECK",
            transaction_reference="TXN-005",
        )

        Payment.objects.create(
            payroll_record=self.payroll_record,
            amount=1600,
            payment_method="CHECK",
            transaction_reference="TXN-006",
        )

        self.assertEqual(
            self.payroll_record.payments.count(),
            2,
        )

    def test_zero_amount_is_allowed(self):
        payment = Payment.objects.create(
            payroll_record=self.payroll_record,
            amount=0,
            payment_method="CASH",
            transaction_reference="TXN-007",
        )

        self.assertEqual(
            payment.amount,
            0,
        )

    def test_payment_str(self):
        payment = Payment.objects.create(
            payroll_record=self.payroll_record,
            amount=3200,
            payment_method="DIRECT_DEPOSIT",
            transaction_reference="TXN-008",
        )

        self.assertEqual(
            str(payment),
            "EMP-PAYMENT-001 - 3200 - PENDING",
        )

class BankAccountModelTests(TestCase):
    """Test BankAccount model behavior."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="bank@example.com",
            name="Bank Employee",
            password="TestPass123!",
        )

        self.department = Department.objects.create(
            name="Accounting",
            code="ACC",
        )

        self.position = Position.objects.create(
            title="Accountant",
            department=self.department,
        )

        self.employee = EmployeeProfile.objects.create(
            user=self.user,
            employee_id="EMP-BANK-001",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 1),
        )

    def test_create_valid_bank_account(self):
        account = BankAccount.objects.create(
            employee=self.employee,
            account_type="CHECKING",
            routing_number="123456789",
            account_number="9876543210",
        )

        self.assertEqual(
            account.employee,
            self.employee,
        )

        self.assertEqual(
            account.account_type,
            "CHECKING",
        )

    def test_bank_data_is_encrypted_in_database(self):
        """Ensure sensitive bank data is encrypted at rest."""

        account = BankAccount.objects.create(
            employee=self.employee,
            account_type="CHECKING",
            routing_number="123456789",
            account_number="9876543210",
        )

        account.refresh_from_db()

        self.assertEqual(
            account.routing_number,
            "123456789",
        )

        self.assertEqual(
            account.account_number,
            "9876543210",
        )

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT routing_number, account_number
                FROM employees_bankaccount
                WHERE id = %s
                """,
                [account.id],
            )
            row = cursor.fetchone()

        self.assertNotEqual(
            row[0],
            "123456789",
        )

        self.assertNotEqual(
            row[1],
            "9876543210",
        )

    def test_encryption_fails_when_key_is_missing(self):
        """Encryption must fail when the environment key is missing."""

        with patch.dict(
            "os.environ",
            {"BANK_ENCRYPTION_KEY": ""},
        ):
            with self.assertRaises(RuntimeError):
                encrypt_bank_data("123456789")

    def test_decryption_fails_with_wrong_key(self):
        """Decryption must reject data encrypted with another key."""

        original_key = Fernet.generate_key()
        wrong_key = Fernet.generate_key()

        encrypted_value = Fernet(original_key).encrypt(
            b"123456789",
        ).decode()

        with patch.dict(
            "os.environ",
            {"BANK_ENCRYPTION_KEY": wrong_key.decode()},
        ):
            with self.assertRaises(ValueError):
                decrypt_bank_data(encrypted_value)

    def test_decryption_fails_with_tampered_data(self):
        """Decryption must reject modified encrypted data."""

        key = Fernet.generate_key()

        with patch.dict(
            "os.environ",
            {"BANK_ENCRYPTION_KEY": key.decode()},
        ):
            encrypted_value = encrypt_bank_data("123456789")

            tampered_value = (
                ("A" if encrypted_value[0] != "A" else "B")
                + encrypted_value[1:]
            )

            with self.assertRaises(ValueError):
                decrypt_bank_data(tampered_value)

    def test_decryption_works_with_previous_key(self):
        """Existing data must remain decryptable with a previous key."""

        old_key = Fernet.generate_key()
        new_key = Fernet.generate_key()

        encrypted_value = Fernet(old_key).encrypt(
            b"123456789",
        ).decode()

        with patch.dict(
            "os.environ",
            {
                "BANK_ENCRYPTION_KEY": new_key.decode(),
                "BANK_ENCRYPTION_OLD_KEYS": old_key.decode(),
            },
        ):
            self.assertEqual(
                decrypt_bank_data(encrypted_value),
                "123456789",
            )

    def test_encryption_uses_primary_key(self):
        """New bank data must be encrypted with the primary key."""

        primary_key = Fernet.generate_key()
        old_key = Fernet.generate_key()

        with patch.dict(
            "os.environ",
            {
                "BANK_ENCRYPTION_KEY": primary_key.decode(),
                "BANK_ENCRYPTION_OLD_KEYS": old_key.decode(),
            },
        ):
            encrypted_value = encrypt_bank_data("123456789")

            self.assertEqual(
                Fernet(primary_key).decrypt(
                    encrypted_value.encode(),
                ).decode(),
                "123456789",
            )

    def test_invalid_previous_key_raises_configuration_error(self):
        """Invalid previous keys must be rejected."""

        primary_key = Fernet.generate_key()

        with patch.dict(
            "os.environ",
            {
                "BANK_ENCRYPTION_KEY": primary_key.decode(),
                "BANK_ENCRYPTION_OLD_KEYS": "invalid-fernet-key",
            },
        ):
            with self.assertRaises(RuntimeError):
                encrypt_bank_data("123456789")

    def test_last_four_is_generated_automatically(self):
        account = BankAccount.objects.create(
            employee=self.employee,
            account_type="CHECKING",
            routing_number="123456789",
            account_number="9876543210",
        )

        self.assertEqual(
            account.last_four,
            "3210",
        )

    def test_routing_number_must_have_nine_digits(self):
        account = BankAccount(
            employee=self.employee,
            account_type="CHECKING",
            routing_number="12345678",
            account_number="9876543210",
        )

        with self.assertRaises(ValidationError):
            account.save()

    def test_routing_number_must_contain_only_digits(self):
        account = BankAccount(
            employee=self.employee,
            account_type="CHECKING",
            routing_number="12345ABCD",
            account_number="9876543210",
        )

        with self.assertRaises(ValidationError):
            account.save()

    def test_account_number_must_contain_only_digits(self):
        account = BankAccount(
            employee=self.employee,
            account_type="CHECKING",
            routing_number="123456789",
            account_number="98765ABC",
        )

        with self.assertRaises(ValidationError):
            account.save()

    def test_account_number_must_have_at_least_four_digits(self):
        account = BankAccount(
            employee=self.employee,
            account_type="CHECKING",
            routing_number="123456789",
            account_number="123",
        )

        with self.assertRaises(ValidationError):
            account.save()

    def test_employee_can_have_only_one_primary_account(self):
        BankAccount.objects.create(
            employee=self.employee,
            account_type="CHECKING",
            routing_number="123456789",
            account_number="111122223333",
            is_primary=True,
        )

        duplicate_primary = BankAccount(
            employee=self.employee,
            account_type="SAVINGS",
            routing_number="987654321",
            account_number="444455556666",
            is_primary=True,
        )

        with self.assertRaises(ValidationError):
            duplicate_primary.save()

    def test_employee_can_have_multiple_non_primary_accounts(self):
        BankAccount.objects.create(
            employee=self.employee,
            account_type="CHECKING",
            routing_number="123456789",
            account_number="111122223333",
        )

        BankAccount.objects.create(
            employee=self.employee,
            account_type="SAVINGS",
            routing_number="987654321",
            account_number="444455556666",
        )

        self.assertEqual(
            self.employee.bank_accounts.count(),
            2,
        )

    def test_employee_deletion_is_protected(self):
        BankAccount.objects.create(
            employee=self.employee,
            account_type="CHECKING",
            routing_number="123456789",
            account_number="9876543210",
        )

        with self.assertRaises(ProtectedError):
            self.employee.delete()

    def test_str_masks_account_number(self):
        account = BankAccount.objects.create(
            employee=self.employee,
            account_type="CHECKING",
            routing_number="123456789",
            account_number="9876543210",
        )

        self.assertEqual(
            str(account),
            "EMP-BANK-001 - CHECKING - ****3210",
        )

class PerformanceReviewModelTests(TestCase):
    """Test PerformanceReview model behavior."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="employee@example.com",
            name="John Employee",
            password="TestPass123!",
        )

        self.reviewer = User.objects.create_user(
            email="manager@example.com",
            name="Jane Manager",
            password="TestPass123!",
        )

        self.department = Department.objects.create(
            name="Engineering",
            code="ENG",
        )

        self.position = Position.objects.create(
            title="Software Engineer",
            department=self.department,
        )

        self.employee = EmployeeProfile.objects.create(
            user=self.user,
            employee_id="EMP-001",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 1),
        )

    def test_create_performance_review(self):
        review = PerformanceReview.objects.create(
            employee=self.employee,
            reviewer=self.reviewer,
            review_period_start=date(2026, 1, 1),
            review_period_end=date(2026, 6, 30),
            score=4.50,
            comments="Excellent performance.",
        )

        self.assertEqual(review.employee, self.employee)
        self.assertEqual(review.reviewer, self.reviewer)
        self.assertEqual(review.score, 4.50)
        self.assertEqual(review.status, "DRAFT")

    def test_score_zero_is_valid(self):
        review = PerformanceReview(
            employee=self.employee,
            reviewer=self.reviewer,
            review_period_start=date(2026, 1, 1),
            review_period_end=date(2026, 6, 30),
            score=0,
        )

        review.full_clean()

    def test_score_five_is_valid(self):
        review = PerformanceReview(
            employee=self.employee,
            reviewer=self.reviewer,
            review_period_start=date(2026, 1, 1),
            review_period_end=date(2026, 6, 30),
            score=5,
        )

        review.full_clean()

    def test_negative_score_is_rejected(self):
        review = PerformanceReview(
            employee=self.employee,
            reviewer=self.reviewer,
            review_period_start=date(2026, 1, 1),
            review_period_end=date(2026, 6, 30),
            score=-1,
        )

        with self.assertRaises(ValidationError):
            review.full_clean()

    def test_score_above_five_is_rejected(self):
        review = PerformanceReview(
            employee=self.employee,
            reviewer=self.reviewer,
            review_period_start=date(2026, 1, 1),
            review_period_end=date(2026, 6, 30),
            score=5.01,
        )

        with self.assertRaises(ValidationError):
            review.full_clean()

    def test_invalid_review_period_is_rejected(self):
        review = PerformanceReview(
            employee=self.employee,
            reviewer=self.reviewer,
            review_period_start=date(2026, 7, 1),
            review_period_end=date(2026, 6, 30),
            score=4,
        )

        with self.assertRaises(ValidationError):
            review.full_clean()

    def test_submitted_review_requires_submitted_at(self):
        review = PerformanceReview(
            employee=self.employee,
            reviewer=self.reviewer,
            review_period_start=date(2026, 1, 1),
            review_period_end=date(2026, 6, 30),
            score=4,
            status="SUBMITTED",
        )

        with self.assertRaises(ValidationError):
            review.full_clean()

    def test_acknowledged_review_requires_submitted_at(self):
        review = PerformanceReview(
            employee=self.employee,
            reviewer=self.reviewer,
            review_period_start=date(2026, 1, 1),
            review_period_end=date(2026, 6, 30),
            score=4,
            status="ACKNOWLEDGED",
        )

        with self.assertRaises(ValidationError):
            review.full_clean()

    def test_submitted_review_with_submitted_at_is_valid(self):
        review = PerformanceReview(
            employee=self.employee,
            reviewer=self.reviewer,
            review_period_start=date(2026, 1, 1),
            review_period_end=date(2026, 6, 30),
            score=4,
            status="SUBMITTED",
            submitted_at=timezone.now(),
        )

        review.full_clean()

    def test_acknowledged_review_with_submitted_at_is_valid(self):
        review = PerformanceReview(
            employee=self.employee,
            reviewer=self.reviewer,
            review_period_start=date(2026, 1, 1),
            review_period_end=date(2026, 6, 30),
            score=4,
            status="ACKNOWLEDGED",
            submitted_at=timezone.now(),
        )

        review.full_clean()

class BankAccountSerializerTests(TestCase):
    """Test BankAccountSerializer behavior."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="employee@example.com",
            name="John Employee",
            password="TestPass123!",
        )

        self.department = Department.objects.create(
            name="Engineering",
            code="ENG",
        )

        self.position = Position.objects.create(
            title="Software Engineer",
            department=self.department,
        )

        self.employee = EmployeeProfile.objects.create(
            user=self.user,
            employee_id="EMP-001",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 1),
        )

    def test_account_number_is_write_only(self):
        serializer = BankAccountSerializer(
            data={
                "employee": self.employee.id,
                "account_type": "CHECKING",
                "routing_number": "021000021",
                "account_number": "123456789123",
                "is_primary": True,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

        bank_account = serializer.save()

        self.assertEqual(
            bank_account.account_number,
            "123456789123",
        )

        self.assertNotIn(
            "account_number",
            serializer.data,
        )

    def test_masked_account_number_is_returned(self):
        bank_account = BankAccount.objects.create(
            employee=self.employee,
            account_type="CHECKING",
            routing_number="021000021",
            account_number="123456789123",
        )

        serializer = BankAccountSerializer(
            bank_account,
        )

        self.assertEqual(
            serializer.data["masked_account_number"],
            "****9123",
        )

    def test_last_four_is_read_only(self):
        serializer = BankAccountSerializer(
            data={
                "employee": self.employee.id,
                "account_type": "CHECKING",
                "routing_number": "021000021",
                "account_number": "123456789123",
                "last_four": "9999",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

        bank_account = serializer.save()

        self.assertEqual(
            bank_account.last_four,
            "9123",
        )

    def test_is_verified_is_read_only(self):
        serializer = BankAccountSerializer(
            data={
                "employee": self.employee.id,
                "account_type": "CHECKING",
                "routing_number": "021000021",
                "account_number": "123456789123",
                "is_verified": True,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

        bank_account = serializer.save()

        self.assertFalse(bank_account.is_verified)

    def test_routing_number_is_write_only(self):
        """Ensure the full routing number is never returned."""

        serializer = BankAccountSerializer(
            data={
                "employee": self.employee.id,
                "account_type": "CHECKING",
                "routing_number": "021000021",
                "account_number": "123456789123",
                "is_primary": True,
            }
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

        bank_account = serializer.save()

        self.assertEqual(
            bank_account.routing_number,
            "021000021",
        )

        self.assertNotIn(
            "routing_number",
            serializer.data,
        )

    def test_masked_routing_number_is_returned(self):
        """Ensure only the last four routing digits are returned."""

        bank_account = BankAccount.objects.create(
            employee=self.employee,
            account_type="CHECKING",
            routing_number="021000021",
            account_number="123456789123",
        )

        serializer = BankAccountSerializer(
            bank_account,
        )

        self.assertEqual(
            serializer.data["masked_routing_number"],
            "*****0021",
        )

        self.assertNotIn(
            "routing_number",
            serializer.data,
        )

class PerformanceReviewSerializerTests(TestCase):
    """Test PerformanceReviewSerializer behavior."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="employee@example.com",
            name="John Employee",
            password="TestPass123!",
        )

        self.reviewer = User.objects.create_user(
            email="manager@example.com",
            name="Jane Manager",
            password="TestPass123!",
        )

        self.department = Department.objects.create(
            name="Engineering",
            code="ENG",
        )

        self.position = Position.objects.create(
            title="Software Engineer",
            department=self.department,
        )

        self.employee = EmployeeProfile.objects.create(
            user=self.user,
            employee_id="EMP-001",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 1),
        )

    def test_valid_performance_review(self):
        serializer = PerformanceReviewSerializer(
            data={
                "employee": self.employee.id,
                "review_period_start": "2026-01-01",
                "review_period_end": "2026-06-30",
                "score": "4.50",
                "comments": "Excellent performance.",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_comments_preserves_script_payload_as_data(self):
        payload = "<script>alert(1)</script>"

        serializer = PerformanceReviewSerializer(
            data={
                "employee": self.employee.id,
                "review_period_start": "2026-01-01",
                "review_period_end": "2026-06-30",
                "score": "4.50",
                "comments": payload,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["comments"],
            payload,
        )

    def test_comments_preserves_event_handler_payload_as_data(self):
        payload = '<img src=x onerror=alert(1)>'

        serializer = PerformanceReviewSerializer(
            data={
                "employee": self.employee.id,
                "review_period_start": "2026-01-01",
                "review_period_end": "2026-06-30",
                "score": "4.50",
                "comments": payload,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["comments"],
            payload,
        )

    def test_comments_preserves_html_payload_as_data(self):
        payload = "<b>HR test</b>"

        serializer = PerformanceReviewSerializer(
            data={
                "employee": self.employee.id,
                "review_period_start": "2026-01-01",
                "review_period_end": "2026-06-30",
                "score": "4.50",
                "comments": payload,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["comments"],
            payload,
        )

    def test_invalid_review_period_is_rejected(self):
        serializer = PerformanceReviewSerializer(
            data={
                "employee": self.employee.id,
                "review_period_start": "2026-07-01",
                "review_period_end": "2026-06-30",
                "score": "4.00",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn(
            "review_period_end",
            serializer.errors,
        )

    def test_negative_score_is_rejected(self):
        serializer = PerformanceReviewSerializer(
            data={
                "employee": self.employee.id,
                "review_period_start": "2026-01-01",
                "review_period_end": "2026-06-30",
                "score": "-1.00",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn(
            "score",
            serializer.errors,
        )

    def test_score_above_five_is_rejected(self):
        serializer = PerformanceReviewSerializer(
            data={
                "employee": self.employee.id,
                "review_period_start": "2026-01-01",
                "review_period_end": "2026-06-30",
                "score": "5.01",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn(
            "score",
            serializer.errors,
        )

    def test_reviewer_is_read_only(self):
        serializer = PerformanceReviewSerializer(
            data={
                "employee": self.employee.id,
                "reviewer": self.reviewer.id,
                "review_period_start": "2026-01-01",
                "review_period_end": "2026-06-30",
                "score": "4.00",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

        self.assertNotIn(
            "reviewer",
            serializer.validated_data,
        )

    def test_status_is_read_only(self):
        serializer = PerformanceReviewSerializer(
            data={
                "employee": self.employee.id,
                "review_period_start": "2026-01-01",
                "review_period_end": "2026-06-30",
                "score": "4.00",
                "status": "ACKNOWLEDGED",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

        self.assertNotIn(
            "status",
            serializer.validated_data,
        )

    def test_submitted_at_is_read_only(self):
        serializer = PerformanceReviewSerializer(
            data={
                "employee": self.employee.id,
                "review_period_start": "2026-01-01",
                "review_period_end": "2026-06-30",
                "score": "4.00",
                "submitted_at": "2026-06-30T12:00:00Z",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

        self.assertNotIn(
            "submitted_at",
            serializer.validated_data,
        )

class BankAccountViewSetTests(TestCase):
    """Test BankAccount API access control and behavior."""

    def setUp(self):
        self.client = APIClient()

        self.employee_user = User.objects.create_user(
            email="employee@example.com",
            name="John Employee",
            password="TestPass123!",
            role="EMPLOYEE",
        )

        self.other_employee_user = User.objects.create_user(
            email="other@example.com",
            name="Other Employee",
            password="TestPass123!",
            role="EMPLOYEE",
        )

        self.hr_manager = User.objects.create_user(
            email="manager@example.com",
            name="HR Manager",
            password="TestPass123!",
            role="HR_MANAGER",
        )

        self.hr_admin = User.objects.create_user(
            email="admin@example.com",
            name="HR Admin",
            password="TestPass123!",
            role="HR_ADMIN",
        )

        self.super_admin = User.objects.create_superuser(
            email="superadmin@example.com",
            name="Super Admin",
            password="TestPass123!",
        )

        self.department = Department.objects.create(
            name="Engineering",
            code="ENG",
        )

        self.position = Position.objects.create(
            title="Software Engineer",
            department=self.department,
        )
        self.finance_department = Department.objects.create(
            name="Finance",
            code="FIN",
        )

        self.finance_position = Position.objects.create(
            title="Financial Analyst",
            department=self.finance_department,
        )
        self.employee = EmployeeProfile.objects.create(
            user=self.employee_user,
            employee_id="EMP-001",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 1),
        )

        self.other_employee = EmployeeProfile.objects.create(
            user=self.other_employee_user,
            employee_id="EMP-002",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 1),
        )
        self.manager_profile = EmployeeProfile.objects.create(
            user=self.hr_manager,
            employee_id="EMP-003",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 1),
        )
        self.bank_account = BankAccount.objects.create(
            employee=self.other_employee,
            account_type="CHECKING",
            routing_number="021000021",
            account_number="123456789123",
        )
        self.finance_employee_user = User.objects.create_user(
            email="finance.employee@example.com",
            name="Finance Employee",
            password="TestPass123!",
            role="EMPLOYEE",
        )

        self.finance_employee = EmployeeProfile.objects.create(
            user=self.finance_employee_user,
            employee_id="EMP-004",
            department=self.finance_department,
            position=self.finance_position,
            hire_date=date(2026, 1, 1),
        )

        self.finance_bank_account = BankAccount.objects.create(
            employee=self.finance_employee,
            account_type="CHECKING",
            routing_number="021000021",
            account_number="987654321987",
        )

    def authenticate(self, user):
        """Authenticate the API client as the given user."""

        self.client.force_authenticate(user=user)

    def test_unauthenticated_user_is_rejected(self):
        """Unauthenticated users cannot access bank accounts."""

        response = self.client.get(
            "/api/v1/employees/bank-accounts/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_employee_can_create_own_bank_account(self):
        self.authenticate(self.employee_user)

        response = self.client.post(
            "/api/v1/employees/bank-accounts/",
            {
                "account_type": "CHECKING",
                "routing_number": "021000021",
                "account_number": "987654321123",
                "is_primary": True,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        account = BankAccount.objects.get(
             pk=response.data["id"],
        )

        self.assertEqual(
            account.employee,
            self.employee,
        )

        self.assertNotIn(
            "routing_number",
            response.data,
        )

        self.assertEqual(
            response.data["masked_account_number"],
            "****1123",
        )

    def test_employee_cannot_reassign_own_bank_account(self):
        """Employees cannot transfer their bank account to another employee."""

        own_account = BankAccount.objects.create(
            employee=self.employee,
            account_type="CHECKING",
            routing_number="021000021",
            account_number="555555555555",
        )

        self.authenticate(self.employee_user)

        response = self.client.patch(
            f"/api/v1/employees/bank-accounts/{own_account.id}/",
            {
                "employee": self.other_employee.id,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        own_account.refresh_from_db()

        self.assertEqual(
            own_account.employee,
            self.employee,
        )

    def test_employee_cannot_access_other_employee_account(self):
        self.authenticate(self.employee_user)

        response = self.client.get(
            f"/api/v1/employees/bank-accounts/"
            f"{self.bank_account.id}/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_employee_cannot_update_other_employee_account(self):
        self.authenticate(self.employee_user)

        response = self.client.patch(
            f"/api/v1/employees/bank-accounts/"
            f"{self.bank_account.id}/",
            {
                "is_primary": True,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_hr_manager_can_view_bank_account(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            f"/api/v1/employees/bank-accounts/"
            f"{self.bank_account.id}/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertNotIn(
            "account_number",
            response.data,
        )

        self.assertEqual(
            response.data["masked_account_number"],
            "****9123",
        )

    def test_hr_manager_cannot_list_other_department_bank_accounts(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            "/api/v1/employees/bank-accounts/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        returned_ids = {
            account["id"]
            for account in response.data["results"]
        }

        self.assertIn(
            self.bank_account.id,
            returned_ids,
        )

        self.assertNotIn(
            self.finance_bank_account.id,
            returned_ids,
        )

    def test_hr_manager_cannot_view_other_department_bank_account(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            f"/api/v1/employees/bank-accounts/"
            f"{self.finance_bank_account.id}/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_hr_manager_cannot_create_bank_account(self):
        self.authenticate(self.hr_manager)

        response = self.client.post(
            "/api/v1/employees/bank-accounts/",
            {
                "employee": self.employee.id,
                "account_type": "CHECKING",
                "routing_number": "021000021",
                "account_number": "987654321123",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_hr_manager_without_profile_cannot_list_bank_accounts(self):
        manager_without_profile = User.objects.create_user(
            email="manager-no-profile@example.com",
            name="Manager Without Profile",
            password="TestPass123!",
            role="HR_MANAGER",
        )

        self.authenticate(manager_without_profile)

        response = self.client.get(
            "/api/v1/employees/bank-accounts/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_hr_admin_can_view_other_department_bank_account(self):
        self.authenticate(self.hr_admin)

        response = self.client.get(
            f"/api/v1/employees/bank-accounts/"
            f"{self.finance_bank_account.id}/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )


    def test_super_admin_can_view_other_department_bank_account(self):
        self.authenticate(self.super_admin)

        response = self.client.get(
            f"/api/v1/employees/bank-accounts/"
            f"{self.finance_bank_account.id}/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_hr_admin_can_list_bank_accounts_across_departments(self):
        self.authenticate(self.hr_admin)

        response = self.client.get(
            "/api/v1/employees/bank-accounts/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        returned_ids = {
            account["id"]
            for account in response.data["results"]
        }

        self.assertIn(self.bank_account.id, returned_ids)
        self.assertIn(self.finance_bank_account.id, returned_ids)

    def test_super_admin_can_list_bank_accounts_across_departments(self):
        self.authenticate(self.super_admin)

        response = self.client.get(
            "/api/v1/employees/bank-accounts/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        returned_ids = {
            account["id"]
            for account in response.data["results"]
        }

        self.assertIn(self.bank_account.id, returned_ids)
        self.assertIn(self.finance_bank_account.id, returned_ids)

    def test_hr_admin_can_create_bank_account(self):
        self.authenticate(self.hr_admin)

        response = self.client.post(
            "/api/v1/employees/bank-accounts/",
            {
                "employee": self.employee.id,
                "account_type": "CHECKING",
                "routing_number": "021000021",
                "account_number": "987654321123",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        account = BankAccount.objects.get(
            pk=response.data["id"],
        )

        self.assertEqual(
            account.employee,
            self.employee,
        )

        self.assertNotIn(
            "routing_number",
            response.data,
        )

        self.assertNotIn(
            "account_number",
            response.data,
        )

        self.assertEqual(
            response.data["masked_routing_number"],
            "*****0021",
        )

        self.assertEqual(
            response.data["masked_account_number"],
            "****1123",
        )

    def test_employee_cannot_delete_bank_account(self):
        self.authenticate(self.employee_user)

        own_account = BankAccount.objects.create(
            employee=self.employee,
            account_type="CHECKING",
            routing_number="021000021",
            account_number="555555555555",
        )

        response = self.client.delete(
            f"/api/v1/employees/bank-accounts/"
            f"{own_account.id}/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.assertTrue(
            BankAccount.objects.filter(
                pk=own_account.id,
            ).exists()
        )

    def test_bank_account_creation_creates_security_event(self):
        self.authenticate(self.employee_user)

        response = self.client.post(
            "/api/v1/employees/bank-accounts/",
            {
                "account_type": "CHECKING",
                "routing_number": "021000021",
                "account_number": "777777777777",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        event = SecurityEvent.objects.filter(
            event_type="ACCOUNT_CHANGE",
            user=self.employee_user,
        ).latest("created_at")

        self.assertIn(
            "Bank account created",
            event.details,
        )

        self.assertNotIn(
            "777777777777",
            event.details,
        )
        self.assertNotIn(
            "021000021",
            event.details,
        )
        log_file = settings.BASE_DIR / "logs" / "security-events.jsonl"

        self.assertTrue(log_file.exists())

        log_content = log_file.read_text(
            encoding="utf-8",
        )

        self.assertNotIn(
            "777777777777",
            log_content,
        )

        self.assertNotIn(
            "021000021",
            log_content,
        )

    def test_bank_accounts_can_be_filtered_by_account_type(self):
        self.authenticate(self.hr_manager)

        BankAccount.objects.create(
            employee=self.employee,
            account_type="SAVINGS",
            routing_number="011000015",
            account_number="987654321123",
        )

        response = self.client.get(
            "/api/v1/employees/bank-accounts/",
            {"account_type": "SAVINGS"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            1,
        )

        self.assertEqual(
            response.data["results"][0]["account_type"],
            "SAVINGS",
        )

    def test_bank_accounts_can_be_filtered_by_is_primary(self):
        self.authenticate(self.hr_manager)

        BankAccount.objects.create(
            employee=self.employee,
            account_type="CHECKING",
            routing_number="011000015",
            account_number="987654321123",
            is_primary=True,
        )

        response = self.client.get(
            "/api/v1/employees/bank-accounts/",
            {"is_primary": "true"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            1,
        )

        self.assertTrue(
            response.data["results"][0]["is_primary"],
        )

    def test_bank_accounts_can_be_filtered_by_is_verified(self):
        self.authenticate(self.hr_manager)

        BankAccount.objects.create(
            employee=self.employee,
            account_type="SAVINGS",
            routing_number="011000015",
            account_number="987654321123",
            is_verified=True,
        )

        response = self.client.get(
            "/api/v1/employees/bank-accounts/",
            {"is_verified": "true"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            1,
        )

        self.assertTrue(
            response.data["results"][0]["is_verified"],
        )

    def test_bank_accounts_can_be_filtered_by_employee(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            "/api/v1/employees/bank-accounts/",
            {"employee": self.other_employee.id},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            1,
        )

        self.assertEqual(
            response.data["results"][0]["id"],
            self.bank_account.id,
        )

    def test_bank_accounts_can_be_ordered_by_created_at(self):
        self.authenticate(self.hr_manager)

        second_account = BankAccount.objects.create(
            employee=self.employee,
            account_type="SAVINGS",
            routing_number="011000015",
            account_number="987654321123",
        )

        response = self.client.get(
            "/api/v1/employees/bank-accounts/",
            {"ordering": "created_at"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            2,
        )

        returned_ids = [
            account["id"]
            for account in response.data["results"]
        ]

        self.assertEqual(
            returned_ids,
            [
                self.bank_account.id,
                second_account.id,
            ],
        )

    def test_bank_accounts_can_be_ordered_by_updated_at(self):
        self.authenticate(self.hr_manager)

        second_account = BankAccount.objects.create(
            employee=self.employee,
            account_type="SAVINGS",
            routing_number="011000015",
            account_number="987654321123",
        )

        response = self.client.get(
            "/api/v1/employees/bank-accounts/",
            {"ordering": "updated_at"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            2,
        )

        returned_ids = [
            account["id"]
            for account in response.data["results"]
        ]

        self.assertEqual(
            returned_ids,
            [
                self.bank_account.id,
                second_account.id,
            ],
        )

    def test_bank_accounts_can_be_ordered_by_last_four(self):
        self.authenticate(self.hr_manager)

        second_account = BankAccount.objects.create(
            employee=self.employee,
            account_type="SAVINGS",
            routing_number="011000015",
            account_number="987654321123",
        )

        response = self.client.get(
            "/api/v1/employees/bank-accounts/",
            {"ordering": "last_four"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            2,
        )

        returned_last_four = [
            account["last_four"]
            for account in response.data["results"]
        ]

        self.assertEqual(
            returned_last_four,
            [
                second_account.last_four,
                self.bank_account.last_four,
            ],
        )

    def test_bank_accounts_cannot_be_filtered_by_account_number(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            "/api/v1/employees/bank-accounts/",
            {"account_number": "123456789123"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            1,
        )

        self.assertEqual(
            response.data["results"][0]["id"],
            self.bank_account.id,
        )

class PerformanceReviewViewSetTests(TestCase):
    """Test PerformanceReview API access control and workflow."""

    def setUp(self):
        self.client = APIClient()

        self.url = "/api/v1/employees/performance-reviews/"

        self.employee_user = User.objects.create_user(
            email="employee@example.com",
            name="John Employee",
            password="TestPass123!",
            role="EMPLOYEE",
        )

        self.other_employee_user = User.objects.create_user(
            email="other@example.com",
            name="Other Employee",
            password="TestPass123!",
            role="EMPLOYEE",
        )

        self.hr_manager = User.objects.create_user(
            email="manager@example.com",
            name="HR Manager",
            password="TestPass123!",
            role="HR_MANAGER",
        )

        self.hr_admin = User.objects.create_user(
            email="admin@example.com",
            name="HR Admin",
            password="TestPass123!",
            role="HR_ADMIN",
        )

        self.super_admin = User.objects.create_superuser(
            email="superadmin@example.com",
            name="Super Admin",
            password="TestPass123!",
        )

        self.department = Department.objects.create(
            name="Engineering",
            code="ENG",
        )

        self.position = Position.objects.create(
            title="Software Engineer",
            department=self.department,
        )

        self.employee = EmployeeProfile.objects.create(
            user=self.employee_user,
            employee_id="EMP-001",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 1),
        )

        self.other_employee = EmployeeProfile.objects.create(
            user=self.other_employee_user,
            employee_id="EMP-002",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 1),
        )

        self.review = PerformanceReview.objects.create(
            employee=self.employee,
            reviewer=self.hr_manager,
            review_period_start=date(2026, 1, 1),
            review_period_end=date(2026, 6, 30),
            score="4.50",
            comments="Strong performance.",
        )

        self.other_review = PerformanceReview.objects.create(
            employee=self.other_employee,
            reviewer=self.hr_manager,
            review_period_start=date(2026, 1, 1),
            review_period_end=date(2026, 6, 30),
            score="3.50",
            comments="Good performance.",
        )

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def test_employee_can_view_own_review(self):
        self.authenticate(self.employee_user)

        response = self.client.get(
            f"/api/v1/employees/performance-reviews/"
            f"{self.review.id}/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_api_preserves_xss_payload_as_json_data(self):
        self.authenticate(self.employee_user)

        payload = '<img src=x onerror=alert(1)>'

        response = self.client.post(
            "/api/v1/employees/performance-reviews/",
            {
                "employee": self.employee.id,
                "review_period_start": "2026-07-01",
                "review_period_end": "2026-12-31",
                "score": "4.00",
                "comments": payload,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["comments"],
            payload,
        )

        review = PerformanceReview.objects.get(
            employee=self.employee,
            review_period_start=date(2026, 7, 1),
        )

        self.assertEqual(
            review.comments,
            payload,
        )

    def test_employee_cannot_view_other_employee_review(self):
        self.authenticate(self.employee_user)

        response = self.client.get(
            f"/api/v1/employees/performance-reviews/"
            f"{self.other_review.id}/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_employee_can_create_own_review(self):
        self.authenticate(self.employee_user)

        response = self.client.post(
            "/api/v1/employees/performance-reviews/",
            {
                "employee": self.employee.id,
                "review_period_start": "2026-07-01",
                "review_period_end": "2026-12-31",
                "score": "4.00",
                "comments": "New review.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        review = PerformanceReview.objects.get(
            employee=self.employee,
            review_period_start=date(2026, 7, 1),
        )

        self.assertEqual(
            review.reviewer,
            self.employee_user,
        )

    def test_employee_cannot_create_review_for_other_employee(self):
        self.authenticate(self.employee_user)

        response = self.client.post(
            "/api/v1/employees/performance-reviews/",
            {
                "employee": self.other_employee.id,
                "review_period_start": "2026-07-01",
                "review_period_end": "2026-12-31",
                "score": "4.00",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_hr_manager_can_view_review(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            f"/api/v1/employees/performance-reviews/"
            f"{self.review.id}/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_hr_manager_can_create_review(self):
        self.authenticate(self.hr_manager)

        response = self.client.post(
            "/api/v1/employees/performance-reviews/",
            {
                "employee": self.employee.id,
                "review_period_start": "2026-07-01",
                "review_period_end": "2026-12-31",
                "score": "4.25",
                "comments": "Excellent progress.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

    def test_hr_admin_can_update_review(self):
        self.authenticate(self.hr_admin)

        response = self.client.patch(
            f"/api/v1/employees/performance-reviews/"
            f"{self.review.id}/",
            {
                "score": "4.75",
                "comments": "Updated review.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.review.refresh_from_db()

        self.assertEqual(
            self.review.score,
            Decimal("4.75"),
        )

    def test_employee_cannot_update_submitted_review(self):
        self.review.status = "SUBMITTED"
        self.review.submitted_at = timezone.now()
        self.review.save()

        self.authenticate(self.employee_user)

        response = self.client.patch(
            f"{self.url}{self.review.id}/",
            {
                "score": "4.75",
                "comments": "Unauthorized post-submission change.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.review.refresh_from_db()

        self.assertEqual(
            self.review.score,
            Decimal("4.50"),
        )
        self.assertEqual(
            self.review.comments,
            "Strong performance.",
        )

    def test_employee_cannot_update_acknowledged_review(self):
        self.review.status = "ACKNOWLEDGED"
        self.review.submitted_at = timezone.now()
        self.review.save()

        self.authenticate(self.employee_user)

        response = self.client.patch(
            f"{self.url}{self.review.id}/",
            {
                "score": "4.75",
                "comments": "Unauthorized acknowledged change.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.review.refresh_from_db()

        self.assertEqual(
            self.review.score,
            Decimal("4.50"),
        )
        self.assertEqual(
            self.review.comments,
            "Strong performance.",
        )

    def test_hr_manager_can_correct_submitted_review(self):
        self.review.status = "SUBMITTED"
        self.review.submitted_at = timezone.now()
        self.review.save()

        self.authenticate(self.hr_manager)

        response = self.client.patch(
            f"{self.url}{self.review.id}/",
            {
                "score": "4.75",
                "comments": "Corrected by HR Manager.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.review.refresh_from_db()

        self.assertEqual(
            self.review.score,
            Decimal("4.75"),
        )
        self.assertEqual(
            self.review.comments,
            "Corrected by HR Manager.",
        )

    def test_hr_admin_can_correct_submitted_review(self):
        self.review.status = "SUBMITTED"
        self.review.submitted_at = timezone.now()
        self.review.save()

        self.authenticate(self.hr_admin)

        response = self.client.patch(
            f"{self.url}{self.review.id}/",
            {
                "score": "4.75",
                "comments": "Corrected by HR Admin.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.review.refresh_from_db()

        self.assertEqual(
            self.review.score,
            Decimal("4.75"),
        )
        self.assertEqual(
            self.review.comments,
            "Corrected by HR Admin.",
        )

    def test_employee_cannot_update_other_employee_review(self):
        self.authenticate(self.employee_user)

        response = self.client.patch(
            f"/api/v1/employees/performance-reviews/"
            f"{self.other_review.id}/",
            {
                "comments": "Unauthorized update.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_employee_can_submit_own_review(self):
        self.authenticate(self.employee_user)

        response = self.client.post(
            f"/api/v1/employees/performance-reviews/"
            f"{self.review.id}/submit/",
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.review.refresh_from_db()

        self.assertEqual(
            self.review.status,
            "SUBMITTED",
        )

        self.assertIsNotNone(
            self.review.submitted_at,
        )

    def test_employee_cannot_submit_other_employee_review(self):
        self.authenticate(self.employee_user)

        response = self.client.post(
            f"/api/v1/employees/performance-reviews/"
            f"{self.other_review.id}/submit/",
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        self.other_review.refresh_from_db()

        self.assertEqual(
            self.other_review.status,
            "DRAFT",
        )

    def test_employee_create_review_rejects_sql_injection_string(self):
        self.authenticate(self.employee_user)

        response = self.client.post(
            "/api/v1/employees/performance-reviews/",
            {
                "employee": "1' OR '1'='1",
                "review_period_start": "2026-07-01",
                "review_period_end": "2026-12-31",
                "score": "4.00",
                "comments": "SQL injection test.",
            },
            format="json",
        )

        self.assertIn(
            response.status_code,
            (
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_403_FORBIDDEN,
            ),
        )

        self.assertFalse(
            PerformanceReview.objects.filter(
                comments="SQL injection test.",
            ).exists(),
        )

    def test_employee_create_review_rejects_boolean_sql_injection(self):
        self.authenticate(self.employee_user)

        response = self.client.post(
            "/api/v1/employees/performance-reviews/",
            {
                "employee": "1 OR 1=1",
                "review_period_start": "2026-07-01",
                "review_period_end": "2026-12-31",
                "score": "4.00",
                "comments": "Boolean SQL injection test.",
            },
            format="json",
        )

        self.assertIn(
            response.status_code,
            (
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_403_FORBIDDEN,
            ),
        )

        self.assertFalse(
            PerformanceReview.objects.filter(
                comments="Boolean SQL injection test.",
            ).exists(),
        )

    def test_employee_create_review_rejects_non_numeric_employee_id(self):
        self.authenticate(self.employee_user)

        response = self.client.post(
            "/api/v1/employees/performance-reviews/",
            {
                "employee": "abc",
                "review_period_start": "2026-07-01",
                "review_period_end": "2026-12-31",
                "score": "4.00",
                "comments": "Invalid employee ID test.",
            },
            format="json",
        )

        self.assertIn(
            response.status_code,
            (
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_403_FORBIDDEN,
            ),
        )

        self.assertFalse(
            PerformanceReview.objects.filter(
                comments="Invalid employee ID test.",
            ).exists(),
        )

    def test_employee_can_acknowledge_submitted_review(self):
        self.review.status = "SUBMITTED"
        self.review.submitted_at = timezone.now()
        self.review.save()

        self.authenticate(self.employee_user)

        response = self.client.post(
            f"/api/v1/employees/performance-reviews/"
            f"{self.review.id}/acknowledge/",
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.review.refresh_from_db()

        self.assertEqual(
            self.review.status,
            "ACKNOWLEDGED",
        )

    def test_employee_cannot_acknowledge_other_employee_review(self):
        self.other_review.status = "SUBMITTED"
        self.other_review.submitted_at = timezone.now()
        self.other_review.save()

        self.authenticate(self.employee_user)

        response = self.client.post(
            f"/api/v1/employees/performance-reviews/"
            f"{self.other_review.id}/acknowledge/",
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        self.other_review.refresh_from_db()

        self.assertEqual(
            self.other_review.status,
            "SUBMITTED",
        )

    def test_cannot_submit_already_submitted_review(self):
        self.review.status = "SUBMITTED"
        self.review.submitted_at = timezone.now()
        self.review.save()

        self.authenticate(self.employee_user)

        response = self.client.post(
            f"/api/v1/employees/performance-reviews/"
            f"{self.review.id}/submit/",
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_cannot_acknowledge_draft_review(self):
        self.authenticate(self.employee_user)

        response = self.client.post(
            f"/api/v1/employees/performance-reviews/"
            f"{self.review.id}/acknowledge/",
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_employee_cannot_delete_review(self):
        self.authenticate(self.employee_user)

        response = self.client.delete(
            f"/api/v1/employees/performance-reviews/"
            f"{self.review.id}/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.assertTrue(
            PerformanceReview.objects.filter(
                pk=self.review.id,
            ).exists(),
        )

    def test_review_creation_creates_security_event(self):
        self.authenticate(self.hr_manager)

        response = self.client.post(
            "/api/v1/employees/performance-reviews/",
            {
                "employee": self.employee.id,
                "review_period_start": "2026-07-01",
                "review_period_end": "2026-12-31",
                "score": "4.00",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        event = SecurityEvent.objects.filter(
            event_type="ACCOUNT_CHANGE",
            user=self.hr_manager,
        ).latest("created_at")

        self.assertIn(
            "Performance review created",
            event.details,
        )

    def test_review_submission_creates_security_event(self):
        self.authenticate(self.employee_user)

        response = self.client.post(
            f"/api/v1/employees/performance-reviews/"
            f"{self.review.id}/submit/",
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        event = SecurityEvent.objects.filter(
            event_type="ACCOUNT_CHANGE",
            user=self.employee_user,
        ).latest("created_at")

        self.assertIn(
            "Performance review submitted",
            event.details,
        )


    def test_performance_reviews_can_be_filtered_by_employee(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"employee": self.employee.id},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            len(response.data["results"]),
            1,
        )
        self.assertEqual(
            response.data["results"][0]["id"],
            self.review.id,
        )

    def test_performance_reviews_can_be_filtered_by_reviewer(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"reviewer": self.hr_manager.id},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            len(response.data["results"]),
            2,
        )

    def test_performance_reviews_can_be_filtered_by_status(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"status": "DRAFT"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            len(response.data["results"]),
            2,
        )

    def test_performance_reviews_can_be_filtered_by_review_period_start(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"review_period_start": "2026-01-01"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            len(response.data["results"]),
            2,
        )

    def test_performance_reviews_can_be_filtered_by_review_period_end(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"review_period_end": "2026-06-30"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            len(response.data["results"]),
            2,
        )

    def test_performance_reviews_can_be_ordered_by_review_period_start(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"ordering": "review_period_start"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            len(response.data["results"]),
            2,
        )
        self.assertEqual(
            response.data["results"][0]["id"],
            self.review.id,
        )
        self.assertEqual(
            response.data["results"][1]["id"],
            self.other_review.id,
        )

    def test_performance_reviews_can_be_ordered_by_review_period_end_descending(
        self,
    ):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"ordering": "-review_period_end"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            len(response.data["results"]),
            2,
        )

    def test_performance_reviews_can_be_ordered_by_score(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"ordering": "score"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            len(response.data["results"]),
            2,
        )
        self.assertEqual(
            response.data["results"][0]["id"],
            self.other_review.id,
        )
        self.assertEqual(
            response.data["results"][1]["id"],
            self.review.id,
        )

    def test_performance_reviews_can_be_ordered_by_created_at(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"ordering": "created_at"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            len(response.data["results"]),
            2,
        )
        self.assertEqual(
            response.data["results"][0]["id"],
            self.review.id,
        )
        self.assertEqual(
            response.data["results"][1]["id"],
            self.other_review.id,
        )

    def test_performance_reviews_can_be_ordered_by_updated_at(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"ordering": "updated_at"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            len(response.data["results"]),
            2,
        )
        self.assertEqual(
            response.data["results"][0]["id"],
            self.review.id,
        )
        self.assertEqual(
            response.data["results"][1]["id"],
            self.other_review.id,
        )

    def test_performance_reviews_cannot_be_filtered_by_comments(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {"comments": "Strong performance."},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            len(response.data["results"]),
            2,
        )

    def test_performance_reviews_can_combine_filters(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {
                "employee": self.employee.id,
                "status": "DRAFT",
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            len(response.data["results"]),
            1,
        )
        self.assertEqual(
            response.data["results"][0]["id"],
            self.review.id,
        )

    def test_performance_review_employee_filter_rejects_sql_injection_payload(
        self,
    ):
        """Employee filter must reject SQL-like input."""
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {
                "employee": "1 OR 1=1",
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_performance_review_reviewer_filter_rejects_sql_injection_payload(
        self,
    ):
        """Reviewer filter must reject SQL-like input."""
        self.authenticate(self.hr_manager)

        response = self.client.get(
            self.url,
            {
                "reviewer": "1 OR 1=1",
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

class HRDocumentModelTests(TestCase):
    """Tests for the HRDocument model."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="document-owner@example.com",
            name="Document Owner",
            password="TestPass123!",
        )

        self.department = Department.objects.create(
            name="Document Department",
            code="DOC",
        )

        self.position = Position.objects.create(
            title="Document Employee",
            department=self.department,
        )

        self.profile = EmployeeProfile.objects.create(
            user=self.user,
            employee_id="DOC-001",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 15),
        )

        self.document = HRDocument.objects.create(
            employee=self.profile,
            title="Employment Contract",
            document_type=HRDocument.DocumentType.EMPLOYMENT_CONTRACT,
            original_filename="contract.pdf",
            storage_key="hr-documents/test/contract.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            uploaded_by=self.user,
        )

    def test_document_is_created_with_uuid(self):
        self.assertIsNotNone(self.document.id)
        self.assertEqual(self.document.employee, self.profile)
        self.assertEqual(self.document.uploaded_by, self.user)

    def test_document_defaults_to_pending_scan(self):
        self.assertEqual(
            self.document.status,
            HRDocument.Status.PENDING_SCAN,
        )

    def test_document_metadata_defaults_to_empty_dictionary(self):
        self.assertEqual(self.document.metadata, {})

    def test_document_string_representation(self):
        self.assertEqual(
            str(self.document),
            "Employment Contract (DOC-001)",
        )

    def test_storage_key_must_be_unique(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                HRDocument.objects.create(
                    employee=self.profile,
                    title="Duplicate Storage Key",
                    document_type=HRDocument.DocumentType.OTHER,
                    original_filename="other.pdf",
                    storage_key="hr-documents/test/contract.pdf",
                    mime_type="application/pdf",
                    size_bytes=512,
                    uploaded_by=self.user,
                )

    def test_employee_cannot_be_deleted_while_document_exists(self):
        with self.assertRaises(ProtectedError):
            self.profile.delete()

    def test_uploader_cannot_be_deleted_while_document_exists(self):
        with self.assertRaises(ProtectedError):
            self.user.delete()

    def test_document_type_choices_are_defined(self):
        expected_types = {
            "IDENTITY_DOCUMENT",
            "EMPLOYMENT_CONTRACT",
            "TAX_FORM",
            "CERTIFICATION",
            "POLICY_ACKNOWLEDGMENT",
            "ONBOARDING_FORM",
            "OTHER",
        }

        actual_types = {
            value
            for value, label in HRDocument.DocumentType.choices
        }

        self.assertSetEqual(actual_types, expected_types)

    def test_document_status_choices_are_defined(self):
        expected_statuses = {
            "PENDING_SCAN",
            "PENDING_REVIEW",
            "VERIFIED",
            "QUARANTINED",
            "REJECTED",
            "ARCHIVED",
        }

        actual_statuses = {
            value
            for value, label in HRDocument.Status.choices
        }

        self.assertSetEqual(actual_statuses, expected_statuses)

class DocumentVersionModelTests(TestCase):
    """Tests for immutable HR document version records."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="version-owner@example.com",
            name="Version Owner",
            password="TestPass123!",
        )

        self.department = Department.objects.create(
            name="Version Department",
            code="VER",
        )

        self.position = Position.objects.create(
            title="Version Employee",
            department=self.department,
        )

        self.profile = EmployeeProfile.objects.create(
            user=self.user,
            employee_id="VER-001",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 15),
        )

        self.document = HRDocument.objects.create(
            employee=self.profile,
            title="Employment Contract",
            document_type=HRDocument.DocumentType.EMPLOYMENT_CONTRACT,
            original_filename="contract.pdf",
            storage_key="hr-documents/version/contract.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            uploaded_by=self.user,
        )

    def create_version(self, document=None, version_number=1):
        return DocumentVersion.objects.create(
            document=document or self.document,
            version_number=version_number,
            storage_key=(
                f"hr-document-versions/{self.document.pk}/"
                f"version-{version_number}-{document.pk if document else self.document.pk}.pdf"
            ),
            original_filename=f"contract-v{version_number}.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            checksum_sha256="a" * 64,
            created_by=self.user,
        )

    def test_version_is_created_with_expected_fields(self):
        version = self.create_version()

        self.assertIsNotNone(version.id)
        self.assertEqual(version.document, self.document)
        self.assertEqual(version.version_number, 1)
        self.assertEqual(version.created_by, self.user)
        self.assertEqual(len(version.checksum_sha256), 64)
        self.assertIsNotNone(version.created_at)

    def test_version_number_must_be_unique_per_document(self):
        self.create_version(version_number=1)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_version(version_number=1)

    def test_different_documents_can_have_the_same_version_number(self):
        self.create_version(version_number=1)

        other_document = HRDocument.objects.create(
            employee=self.profile,
            title="Tax Form",
            document_type=HRDocument.DocumentType.TAX_FORM,
            original_filename="tax.pdf",
            storage_key="hr-documents/version/tax.pdf",
            mime_type="application/pdf",
            size_bytes=512,
            uploaded_by=self.user,
        )

        version = self.create_version(
            document=other_document,
            version_number=1,
        )

        self.assertEqual(version.version_number, 1)
        self.assertEqual(version.document, other_document)

    def test_document_cannot_be_deleted_while_versions_exist(self):
        self.create_version()

        with self.assertRaises(ProtectedError):
            self.document.delete()

    def test_versions_are_ordered_by_version_number(self):
        version_two = self.create_version(version_number=2)
        version_one = self.create_version(version_number=1)

        versions = list(self.document.versions.all())

        self.assertEqual(
            [version.version_number for version in versions],
            [1, 2],
        )
        self.assertEqual(versions[0].pk, version_one.pk)
        self.assertEqual(versions[1].pk, version_two.pk)

    def test_version_storage_key_must_be_unique(self):
        self.create_version(version_number=1)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DocumentVersion.objects.create(
                    document=self.document,
                    version_number=2,
                    storage_key=(
                        f"hr-document-versions/{self.document.pk}/"
                        f"version-1-{self.document.pk}.pdf"
                    ),
                    original_filename="duplicate.pdf",
                    mime_type="application/pdf",
                    size_bytes=1024,
                    checksum_sha256="b" * 64,
                    created_by=self.user,
                )

class DocumentVersionServiceTests(TestCase):
    """Security and lifecycle tests for DocumentVersionService."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="version-service@example.com",
            name="Version Service Employee",
            password="TestPass123!",
        )

        self.department = Department.objects.create(
            name="Version Service Department",
            code="VSD",
        )

        self.position = Position.objects.create(
            title="Version Service Employee",
            department=self.department,
        )

        self.profile = EmployeeProfile.objects.create(
            user=self.user,
            employee_id="VSD-001",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 15),
        )

        self.document = HRDocument.objects.create(
            employee=self.profile,
            title="Employment Contract",
            document_type=HRDocument.DocumentType.EMPLOYMENT_CONTRACT,
            original_filename="contract.pdf",
            storage_key="hr-documents/version-service/contract.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            uploaded_by=self.user,
            status=HRDocument.Status.PENDING_REVIEW,
        )

    def make_pdf(self, name="contract-v2.pdf", content=b"%PDF-1.7 test"):
        return SimpleUploadedFile(
            name,
            content,
            content_type="application/pdf",
        )

    @patch("employees.services.document_version.scan_uploaded_file")
    @patch("employees.services.document_version.hr_document_storage.save")
    @patch("employees.services.document_version.hr_document_storage.exists")
    def test_create_version_after_clean_antivirus_scan(
        self,
        mock_exists,
        mock_storage_save,
        mock_scan,
    ):
        from employees.services.document_version import DocumentVersionService

        mock_exists.return_value = False
        mock_storage_save.return_value = (
            f"hr-document-versions/{self.document.pk}/version.pdf"
        )

        version = DocumentVersionService.create_version(
            document_id=self.document.pk,
            uploaded_file=self.make_pdf(),
            actor=self.user,
        )

        self.assertEqual(version.document, self.document)
        self.assertEqual(version.version_number, 1)
        self.assertEqual(version.created_by, self.user)
        self.assertEqual(version.mime_type, "application/pdf")
        self.assertEqual(len(version.checksum_sha256), 64)
        mock_scan.assert_called_once()

    @patch("employees.services.document_version.scan_uploaded_file")
    def test_reject_version_when_antivirus_detects_malware(
        self,
        mock_scan,
    ):
        from employees.services.document_version import DocumentVersionService

        mock_scan.side_effect = MalwareDetected("malware")

        with self.assertRaises(ValidationError):
            DocumentVersionService.create_version(
                document_id=self.document.pk,
                uploaded_file=self.make_pdf(),
                actor=self.user,
            )

        self.assertFalse(
            DocumentVersion.objects.filter(
                document=self.document
            ).exists()
        )

    @patch("employees.services.document_version.scan_uploaded_file")
    def test_reject_version_when_antivirus_is_unavailable(
        self,
        mock_scan,
    ):
        from employees.services.document_version import DocumentVersionService

        mock_scan.side_effect = AntivirusUnavailable("unavailable")

        with self.assertRaises(ValidationError):
            DocumentVersionService.create_version(
                document_id=self.document.pk,
                uploaded_file=self.make_pdf(),
                actor=self.user,
            )

        self.assertFalse(
            DocumentVersion.objects.filter(
                document=self.document
            ).exists()
        )

    def test_reject_empty_file(self):
        from employees.services.document_version import DocumentVersionService

        with self.assertRaises(ValidationError):
            DocumentVersionService.create_version(
                document_id=self.document.pk,
                uploaded_file=self.make_pdf(content=b""),
                actor=self.user,
            )

    def test_reject_file_with_invalid_signature(self):
        from employees.services.document_version import DocumentVersionService

        with self.assertRaises(ValidationError):
            DocumentVersionService.create_version(
                document_id=self.document.pk,
                uploaded_file=self.make_pdf(content=b"not a PDF"),
                actor=self.user,
            )

    def test_reject_unsupported_extension(self):
        from employees.services.document_version import DocumentVersionService

        uploaded_file = SimpleUploadedFile(
            "contract.exe",
            b"MZ executable",
            content_type="application/octet-stream",
        )

        with self.assertRaises(ValidationError):
            DocumentVersionService.create_version(
                document_id=self.document.pk,
                uploaded_file=uploaded_file,
                actor=self.user,
            )

    @patch("employees.services.document_version.scan_uploaded_file")
    def test_employee_cannot_version_another_employees_document(
        self,
        mock_scan,
    ):
        from employees.services.document_version import DocumentVersionService

        other_user = User.objects.create_user(
            email="another-version-owner@example.com",
            name="Another Employee",
            password="TestPass123!",
        )

        with self.assertRaises(PermissionDenied):
            DocumentVersionService.create_version(
                document_id=self.document.pk,
                uploaded_file=self.make_pdf(),
                actor=other_user,
            )

        mock_scan.assert_not_called()


    @patch("employees.services.document_version.scan_uploaded_file")
    @patch(
        "employees.services.document_version."
        "DocumentVersionService._validate_file"
    )
    def test_hr_manager_cannot_version_document(
        self,
        mock_validate_file,
        mock_scan,
    ):
        from employees.services.document_version import (
            DocumentVersionService,
        )

        manager = User.objects.create_user(
            email="version-manager@example.com",
            name="Version HR Manager",
            password="StrongPassword123!",
            role="HR_MANAGER",
        )

        with self.assertRaises(PermissionDenied):
            DocumentVersionService.create_version(
                document_id=self.document.pk,
                uploaded_file=self.make_pdf(),
                actor=manager,
            )

        mock_validate_file.assert_not_called()
        mock_scan.assert_not_called()

        self.assertFalse(
            DocumentVersion.objects.filter(
                document=self.document,
            ).exists()
        )


    @patch("employees.services.document_version.scan_uploaded_file")
    def test_archived_document_cannot_be_versioned(self, mock_scan):
        from employees.services.document_version import DocumentVersionService

        self.document.status = HRDocument.Status.ARCHIVED
        self.document.save(update_fields=["status"])

        with self.assertRaises(ValidationError):
            DocumentVersionService.create_version(
                document_id=self.document.pk,
                uploaded_file=self.make_pdf(),
                actor=self.user,
            )

        mock_scan.assert_not_called()

    @patch("employees.services.document_version.scan_uploaded_file")
    def test_quarantined_document_cannot_be_versioned(self, mock_scan):
        from employees.services.document_version import DocumentVersionService

        self.document.status = HRDocument.Status.QUARANTINED
        self.document.save(update_fields=["status"])

        with self.assertRaises(ValidationError):
            DocumentVersionService.create_version(
                document_id=self.document.pk,
                uploaded_file=self.make_pdf(),
                actor=self.user,
            )

        mock_scan.assert_not_called()

class PrivateHRDocumentStorageTests(TestCase):
    """Tests ensuring local HR document storage has no public URLs."""

    def test_local_storage_does_not_generate_public_urls(self):
        from employees.storage import (
            PrivateHRDocumentFileSystemStorage,
        )

        storage = hr_document_storage

        if not isinstance(storage, PrivateHRDocumentFileSystemStorage):
            self.skipTest(
                "The active storage backend is not local filesystem storage."
            )

        with self.assertRaisesMessage(
            ValueError,
            "Private HR documents do not have public URLs.",
        ):
            storage.url("hr-documents/test.pdf")

class HRDocumentSerializerTests(TestCase):
    """Tests for secure HR document serialization."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="serializer-owner@example.com",
            name="Serializer Owner",
            password="TestPass123!",
        )

        self.department = Department.objects.create(
            name="Serializer Department",
            code="SER",
        )

        self.position = Position.objects.create(
            title="Serializer Employee",
            department=self.department,
        )

        self.profile = EmployeeProfile.objects.create(
            user=self.user,
            employee_id="SER-001",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 15),
        )

        self.document = HRDocument.objects.create(
            employee=self.profile,
            title="Employment Contract",
            document_type=HRDocument.DocumentType.EMPLOYMENT_CONTRACT,
            original_filename="contract.pdf",
            storage_key="hr-documents/serializer/contract.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            uploaded_by=self.user,
        )

    def test_storage_key_is_not_exposed(self):
        serializer = HRDocumentSerializer(self.document)

        self.assertNotIn("storage_key", serializer.data)

    def test_server_managed_fields_are_read_only(self):
        serializer = HRDocumentSerializer()

        expected_fields = {
            "id",
            "employee",
            "original_filename",
            "mime_type",
            "size_bytes",
            "checksum_sha256",
            "status",
            "uploaded_by",
            "verified_by",
            "uploaded_at",
            "updated_at",
            "verified_at",
            "rejection_reason",
        }

        for field_name in expected_fields:
            with self.subTest(field=field_name):
                self.assertTrue(
                    serializer.fields[field_name].read_only
                )

    def test_document_metadata_is_serialized(self):
        serializer = HRDocumentSerializer(self.document)

        self.assertEqual(
            serializer.data["title"],
            "Employment Contract",
        )
        self.assertEqual(
            serializer.data["status"],
            HRDocument.Status.PENDING_SCAN,
        )

    def test_server_managed_fields_cannot_be_overridden(self):
        payload = {
            "employee": self.profile.pk,
            "status": "VERIFIED",
            "uploaded_by": self.user.pk,
            "verified_by": self.user.pk,
            "original_filename": "fake.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 1,
            "checksum_sha256": "fake-checksum",
        }

        serializer = HRDocumentSerializer(
            self.document,
            data=payload,
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

        forbidden_fields = {
            "employee",
            "status",
            "uploaded_by",
            "verified_by",
            "original_filename",
            "mime_type",
            "size_bytes",
            "checksum_sha256",
        }

        self.assertTrue(
            forbidden_fields.isdisjoint(serializer.validated_data.keys()),
            f"Des champs protégés ont été acceptés : "
            f"{forbidden_fields.intersection(serializer.validated_data.keys())}",
        )

    def test_valid_pdf_file_is_accepted(self):
        uploaded_file = SimpleUploadedFile(
            "contract.pdf",
            b"%PDF-1.7 test document content",
            content_type="application/pdf",
        )

        serializer = HRDocumentSerializer(
            instance=self.document,
            data={"document_file": uploaded_file},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)


    @patch(
       "employees.services.document_upload.scan_uploaded_file",
        side_effect=MalwareDetected("Test malware"),
    )
    def test_malicious_file_is_quarantined(self, mock_scan):
        from unittest.mock import patch
        from employees.storage import (
            hr_document_storage,
            quarantine_hr_document,
        )

        uploaded_file = SimpleUploadedFile(
            "infected-contract.pdf",
            b"%PDF-1.7 test document content",
            content_type="application/pdf",
        )

        serializer = HRDocumentSerializer(
            data={
                "title": "Infected Contract",
                "document_type": (
                    HRDocument.DocumentType.EMPLOYMENT_CONTRACT
                ),
                "document_file": uploaded_file,
            },
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

        with patch(
             "employees.services.document_upload.quarantine_hr_document",
            wraps=quarantine_hr_document,
        ) as mock_quarantine:
            document = serializer.save(
                employee=self.profile,
                uploaded_by=self.user,
            )

        self.assertEqual(
            document.status,
            HRDocument.Status.QUARANTINED,
        )
        mock_scan.assert_called_once()
        mock_quarantine.assert_called_once()

        original_key = mock_quarantine.call_args.args[0]
        quarantined_key = document.storage_key

        try:
            self.assertTrue(
                quarantined_key.startswith("hr-document-quarantine/"),
                quarantined_key,
            )
            self.assertTrue(
                hr_document_storage.exists(quarantined_key)
            )
            self.assertFalse(
                hr_document_storage.exists(original_key)
            )
        finally:
            hr_document_storage.delete(quarantined_key)

    @patch(
       "employees.services.document_upload.scan_uploaded_file",
        side_effect=MalwareDetected("Test malware"),
    )
    @patch(
         "employees.services.document_upload.quarantine_hr_document",
        return_value=None,
    )
    def test_malicious_file_remains_quarantined_if_move_fails(
        self,
        mock_quarantine,
        mock_scan,
    ):
        uploaded_file = SimpleUploadedFile(
            "infected-contract.pdf",
            b"%PDF-1.7 test document content",
            content_type="application/pdf",
        )

        serializer = HRDocumentSerializer(
            data={
                "title": "Infected Contract Move Failure",
                "document_type": (
                    HRDocument.DocumentType.EMPLOYMENT_CONTRACT
                ),
                "document_file": uploaded_file,
            },
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

        document = serializer.save(
            employee=self.profile,
            uploaded_by=self.user,
        )

        self.assertEqual(
            document.status,
            HRDocument.Status.QUARANTINED,
        )
        self.assertTrue(
            document.storage_key.startswith(
                "hr-document-quarantine/blocked/"
            )
        )
        self.assertFalse(
            hr_document_storage.exists(document.storage_key)
        )
        mock_scan.assert_called_once()
        mock_quarantine.assert_called_once()

    @patch(
         "employees.services.document_upload.hr_document_storage.delete",
        side_effect=OSError("Storage deletion failed"),
    )
    @patch(
         "employees.services.document_upload.quarantine_hr_document",
        return_value=None,
    )
    @patch(
       "employees.services.document_upload.scan_uploaded_file",
        side_effect=MalwareDetected("Malware detected"),
    )
    def test_infected_document_is_blocked_if_quarantine_and_delete_fail(
        self,
        mock_scan,
        mock_quarantine,
        mock_delete,
    ):
        uploaded_file = SimpleUploadedFile(
            "infected-contract.pdf",
            b"%PDF-1.7 test document content",
            content_type="application/pdf",
        )

        serializer = HRDocumentSerializer(
            data={
                "title": "Infected Contract Delete Failure",
                "document_type": (
                    HRDocument.DocumentType.EMPLOYMENT_CONTRACT
                ),
                "document_file": uploaded_file,
            },
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

        document = serializer.save(
            employee=self.profile,
            uploaded_by=self.user,
        )

        document.refresh_from_db()

        self.assertEqual(
            document.status,
            HRDocument.Status.QUARANTINED,
        )
        self.assertTrue(
            document.storage_key.startswith(
                "hr-document-quarantine/blocked/"
            )
        )
        mock_scan.assert_called_once()
        mock_quarantine.assert_called_once()
        mock_delete.assert_called_once()


    @patch(
       "employees.services.document_upload.scan_uploaded_file",
        side_effect=AntivirusUnavailable("Scanner unavailable"),
    )
    def test_document_remains_pending_scan_when_antivirus_is_unavailable(
        self,
        mock_scan,
    ):
        uploaded_file = SimpleUploadedFile(
            "contract-unscanned.pdf",
            b"%PDF-1.7 test document content",
            content_type="application/pdf",
        )

        serializer = HRDocumentSerializer(
            data={
                "title": "Unscanned Contract",
                "document_type": (
                    HRDocument.DocumentType.EMPLOYMENT_CONTRACT
                ),
                "document_file": uploaded_file,
            },
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

        document = serializer.save(
            employee=self.profile,
            uploaded_by=self.user,
        )

        self.assertEqual(
            document.status,
            HRDocument.Status.PENDING_SCAN,
        )
        mock_scan.assert_called_once()


    @patch("employees.services.document_upload.scan_uploaded_file")
    def test_create_stores_file_and_calculates_sha256(
        self,
        mock_scan,
    ):
        import hashlib
        from employees.storage import hr_document_storage

        content = b"%PDF-1.7 test document content"
        uploaded_file = SimpleUploadedFile(
            "new-contract.pdf",
            content,
            content_type="application/pdf",
        )

        serializer = HRDocumentSerializer(
            data={
                "title": "New Employment Contract",
                "document_type": (
                    HRDocument.DocumentType.EMPLOYMENT_CONTRACT
                ),
                "document_file": uploaded_file,
                "metadata": {"source": "test"},
            },
            context={"request": type(
                "Request", (), {"user": self.user}
            )()},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

        document = serializer.save(
            employee=self.profile,
            uploaded_by=self.user,
        )

        try:
            self.assertEqual(
                document.checksum_sha256,
                hashlib.sha256(content).hexdigest(),
            )
            self.assertTrue(hr_document_storage.exists(document.storage_key))
            self.assertEqual(document.original_filename, "new-contract.pdf")
            self.assertEqual(document.size_bytes, len(content))
            self.assertNotIn("storage_key", serializer.data)
        finally:
            hr_document_storage.delete(document.storage_key)

    @patch("employees.services.document_upload.scan_uploaded_file")
    def test_create_removes_stored_file_if_database_creation_fails(
        self,
        mock_scan,
    ):
        from unittest.mock import patch
        from employees.storage import hr_document_storage

        uploaded_file = SimpleUploadedFile(
            "failed-contract.pdf",
            b"%PDF-1.7 test document content",
            content_type="application/pdf",
        )

        serializer = HRDocumentSerializer(
            data={
                "title": "Failed Contract",
                "document_type": (
                    HRDocument.DocumentType.EMPLOYMENT_CONTRACT
                ),
                "document_file": uploaded_file,
            },
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)


        with patch(
            "employees.serializers.hr_document_storage.save",
            wraps=hr_document_storage.save,
        ) as storage_save:
            with patch(
                 "employees.services.document_upload.hr_document_storage.delete",
                wraps=hr_document_storage.delete,
            ) as storage_delete:
                with patch(
                    "employees.serializers.HRDocument.objects.create",
                    side_effect=RuntimeError(
                        "Simulated database failure"
                    ),
                ):
                    with self.assertRaises(RuntimeError):
                        serializer.save(
                            employee=self.profile,
                            uploaded_by=self.user,
                        )


        self.assertTrue(storage_save.called)
        self.assertTrue(storage_delete.called)

        saved_key = storage_delete.call_args.args[0]
        self.assertIsInstance(saved_key, str)
        self.assertFalse(hr_document_storage.exists(saved_key))


    def test_empty_file_is_rejected(self):
        uploaded_file = SimpleUploadedFile(
            "empty.pdf",
            b"",
            content_type="application/pdf",
        )

        serializer = HRDocumentSerializer(
            instance=self.document,
            data={"document_file": uploaded_file},
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("document_file", serializer.errors)

    def test_unsupported_extension_is_rejected(self):
        uploaded_file = SimpleUploadedFile(
            "malware.exe",
            b"%PDF-1.7 test content",
            content_type="application/octet-stream",
        )

        serializer = HRDocumentSerializer(
            instance=self.document,
            data={"document_file": uploaded_file},
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("document_file", serializer.errors)

    def test_file_signature_must_match_extension(self):
        uploaded_file = SimpleUploadedFile(
            "contract.pdf",
            b"This is not a PDF file",
            content_type="application/pdf",
        )

        serializer = HRDocumentSerializer(
            instance=self.document,
            data={"document_file": uploaded_file},
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("document_file", serializer.errors)

    def test_file_over_10_mb_is_rejected(self):
        uploaded_file = SimpleUploadedFile(
            "large.pdf",
            b"%PDF-" + b"A" * (10 * 1024 * 1024),
            content_type="application/pdf",
        )

        serializer = HRDocumentSerializer(
            instance=self.document,
            data={"document_file": uploaded_file},
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("document_file", serializer.errors)

class HRDocumentRBACAPITests(TestCase):
    """Tests for HR document API access control."""

    def setUp(self):
        self.client = APIClient()

        self.super_admin = User.objects.create_user(
            email="hrdoc-admin@example.com",
            name="HR Document Super Admin",
            password="StrongPassword123!",
            role="SUPER_ADMIN",
            is_staff=True,
            is_superuser=True,
        )

        self.hr_admin = User.objects.create_user(
            email="hrdoc-hradmin@example.com",
            name="HR Document HR Admin",
            password="StrongPassword123!",
            role="HR_ADMIN",
        )

        self.hr_manager = User.objects.create_user(
            email="hrdoc-manager@example.com",
            name="HR Document HR Manager",
            password="StrongPassword123!",
            role="HR_MANAGER",
        )

        self.employee = User.objects.create_user(
            email="hrdoc-employee@example.com",
            name="HR Document Employee",
            password="StrongPassword123!",
            role="EMPLOYEE",
        )

        self.other_employee = User.objects.create_user(
            email="hrdoc-other@example.com",
            name="Other HR Document Employee",
            password="StrongPassword123!",
            role="EMPLOYEE",
        )

        self.department = Department.objects.create(
            name="HR Document Department",
            code="HRD",
        )

        self.position = Position.objects.create(
            title="HR Document Employee",
            department=self.department,
        )

        self.profile = EmployeeProfile.objects.create(
            user=self.employee,
            employee_id="HRDOC-001",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 15),
        )

        self.other_profile = EmployeeProfile.objects.create(
            user=self.other_employee,
            employee_id="HRDOC-002",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 2, 1),
        )

        self.manager_profile = EmployeeProfile.objects.create(
            user=self.hr_manager,
            employee_id="HRDOC-MGR-001",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 10),
        )

        self.foreign_department = Department.objects.create(
            name="HR Document Foreign Department",
            code="HRDF",
        )
        self.foreign_position = Position.objects.create(
            title="Foreign Department Employee",
            department=self.foreign_department,
        )

        self.foreign_employee = User.objects.create_user(
            email="hrdoc-foreign@example.com",
            name="HR Document Foreign Employee",
            password="StrongPassword123!",
            role="EMPLOYEE",
        )
        self.foreign_profile = EmployeeProfile.objects.create(
            user=self.foreign_employee,
            employee_id="HRDOC-003",
            department=self.foreign_department,
            position=self.foreign_position,
            hire_date=date(2026, 3, 1),
        )
        self.document = HRDocument.objects.create(
            employee=self.profile,
            title="Employment Contract",
            document_type=HRDocument.DocumentType.EMPLOYMENT_CONTRACT,
            original_filename="contract.pdf",
            storage_key="hr-documents/rbac/contract.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            uploaded_by=self.hr_admin,
        )

        self.foreign_document = HRDocument.objects.create(
            employee=self.foreign_profile,
            title="Foreign Department Contract",
            document_type=HRDocument.DocumentType.EMPLOYMENT_CONTRACT,
            original_filename="foreign-contract.pdf",
            storage_key="hr-documents/rbac/foreign-contract.pdf",
            mime_type="application/pdf",
            size_bytes=3072,
            uploaded_by=self.hr_admin,
        )
        self.other_document = HRDocument.objects.create(
            employee=self.other_profile,
            title="Other Employee Contract",
            document_type=HRDocument.DocumentType.EMPLOYMENT_CONTRACT,
            original_filename="other-contract.pdf",
            storage_key="hr-documents/rbac/other-contract.pdf",
            mime_type="application/pdf",
            size_bytes=2048,
            uploaded_by=self.hr_admin,
        )

        self.url = "/api/v1/employees/hr-documents/"

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def test_unauthenticated_user_cannot_list_documents(self):
        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_employee_can_list_only_own_documents(self):
        self.authenticate(self.employee)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            str(self.document.pk),
        )

    def test_employee_cannot_retrieve_another_employees_document(self):
        self.authenticate(self.employee)

        response = self.client.get(
            f"{self.url}{self.other_document.pk}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_employee_can_retrieve_own_document(self):
        self.authenticate(self.employee)

        response = self.client.get(
            f"{self.url}{self.document.pk}/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["id"],
            str(self.document.pk),
        )

        audit_entry = DocumentAccessLog.objects.get(
            document=self.document,
            user=self.employee,
            action=DocumentAccessLog.Action.VIEW,
        )
        self.assertEqual(
            audit_entry.details,
            "HR document metadata viewed.",
        )

    def test_hr_manager_can_view_document_review_history(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            f"{self.url}{self.document.pk}/reviews/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_employee_cannot_view_another_employees_review_history(self):
        self.authenticate(self.employee)

        response = self.client.get(
            f"{self.url}{self.other_document.pk}/reviews/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_employee_can_view_own_document_review_history(self):
        self.authenticate(self.employee)

        response = self.client.get(
            f"{self.url}{self.document.pk}/reviews/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_hr_admin_can_list_documents(self):
        self.authenticate(self.hr_admin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)

    def test_hr_manager_can_list_documents(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_super_admin_can_list_documents(self):
        self.authenticate(self.super_admin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)

    def test_employee_cannot_delete_document(self):
        self.authenticate(self.employee)

        response = self.client.delete(
            f"{self.url}{self.document.pk}/"
        )

        # La suppression n'est pas exposée par le ViewSet.
        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    @patch("employees.services.document_upload.scan_uploaded_file")
    def test_employee_can_upload_document_to_own_profile(self,mock_scan,):
        self.authenticate(self.employee)

        uploaded_file = SimpleUploadedFile(
            "my-contract.pdf",
            b"%PDF-1.7 test contract",
            content_type="application/pdf",
        )

        response = self.client.post(
            self.url,
            {
                "title": "My Contract",
                "document_type": (
                    HRDocument.DocumentType.EMPLOYMENT_CONTRACT
                ),
                "document_file": uploaded_file,
            },
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.data,
        )

        document = HRDocument.objects.get(pk=response.data["id"])
        self.assertEqual(document.employee, self.profile)
        self.assertEqual(document.uploaded_by, self.employee)

    @patch("employees.services.document_upload.scan_uploaded_file")
    def test_employee_cannot_upload_document_for_another_profile(self, mock_scan,):
        self.authenticate(self.employee)

        uploaded_file = SimpleUploadedFile(
            "other-contract.pdf",
            b"%PDF-1.7 test contract",
            content_type="application/pdf",
        )

        response = self.client.post(
            self.url,
            {
                "employee": self.other_profile.pk,
                "title": "Other Contract",
                "document_type": (
                    HRDocument.DocumentType.EMPLOYMENT_CONTRACT
                ),
                "document_file": uploaded_file,
            },
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.data,
        )

        document = HRDocument.objects.get(pk=response.data["id"])
        self.assertEqual(document.employee, self.profile)
        self.assertNotEqual(document.employee, self.other_profile)

    def test_hr_manager_list_excludes_foreign_department_documents(self):
        self.client.force_authenticate(user=self.hr_manager)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)

        document_ids = {
            item["id"] for item in response.data["results"]
        }
        self.assertNotIn(self.foreign_document.pk, document_ids)

    def test_hr_manager_cannot_retrieve_foreign_department_document(self):
        self.client.force_authenticate(user=self.hr_manager)

        response = self.client.get(
            f"{self.url}{self.foreign_document.pk}/"
        )

        self.assertEqual(response.status_code, 404)

    def test_hr_manager_cannot_verify_foreign_department_document(self):
        self.foreign_document.status = "PENDING_REVIEW"
        self.foreign_document.save(update_fields=["status"])

        self.client.force_authenticate(user=self.hr_manager)

        response = self.client.post(
            f"{self.url}{self.foreign_document.pk}/verify/"
        )

        self.assertEqual(response.status_code, 404)

        self.foreign_document.refresh_from_db()
        self.assertEqual(
            self.foreign_document.status,
            "PENDING_REVIEW",
        )
        self.assertFalse(
            DocumentReview.objects.filter(
                document=self.foreign_document,
            ).exists()
        )

    def test_hr_manager_cannot_reject_foreign_department_document(self):
        self.foreign_document.status = "PENDING_REVIEW"
        self.foreign_document.save(update_fields=["status"])

        self.client.force_authenticate(user=self.hr_manager)

        response = self.client.post(
            f"{self.url}{self.foreign_document.pk}/reject/",
            {"reason": "Unauthorized rejection."},
            format="json",
        )

        self.assertEqual(response.status_code, 404)

        self.foreign_document.refresh_from_db()
        self.assertEqual(
            self.foreign_document.status,
            "PENDING_REVIEW",
        )
        self.assertEqual(
            self.foreign_document.rejection_reason,
            "",
        )
        self.assertFalse(
            DocumentReview.objects.filter(
                document=self.foreign_document,
            ).exists()
        )

    def test_hr_manager_cannot_archive_foreign_department_document(self):
        self.foreign_document.status = "VERIFIED"
        self.foreign_document.save(update_fields=["status"])

        self.client.force_authenticate(user=self.hr_manager)

        response = self.client.post(
            f"{self.url}{self.foreign_document.pk}/archive/"
        )

        self.assertEqual(response.status_code, 404)

        self.foreign_document.refresh_from_db()
        self.assertEqual(
            self.foreign_document.status,
            "VERIFIED",
        )

    def test_hr_manager_can_verify_document_pending_review(self):
        self.document.status = "PENDING_REVIEW"
        self.document.save(update_fields=["status"])

        self.authenticate(self.hr_manager)

        response = self.client.post(
            f"{self.url}{self.document.pk}/verify/"
        )

        self.assertEqual(response.status_code, 200)

        self.document.refresh_from_db()
        self.assertEqual(self.document.status, "VERIFIED")
        self.assertEqual(
            self.document.verified_by,
            self.hr_manager,
        )
        self.assertIsNotNone(self.document.verified_at)
        review = DocumentReview.objects.get(
            document=self.document,
        )
        self.assertEqual(
            review.reviewer,
            self.hr_manager,
        )
        self.assertEqual(
            review.decision,
            DocumentReview.Decision.APPROVED,
        )
        self.assertEqual(review.comment, "")
        audit = AuditLog.objects.get(
            action="HR_DOCUMENT_VERIFIED",
        )
        self.assertEqual(audit.user, self.hr_manager)

        event = SecurityEvent.objects.get(
            event_type="HR_DOCUMENT_VERIFIED",
        )
        self.assertEqual(event.user, self.hr_manager)
        self.assertEqual(
            event.request_path,
            f"{self.url}{self.document.pk}/verify/",
        )

    def test_verify_rejects_document_not_pending_review(self):
        self.authenticate(self.hr_manager)

        response = self.client.post(
            f"{self.url}{self.document.pk}/verify/"
        )

        self.assertEqual(response.status_code, 400)

        self.document.refresh_from_db()
        self.assertEqual(self.document.status, "PENDING_SCAN")
        self.assertIsNone(self.document.verified_by)
        self.assertIsNone(self.document.verified_at)

    def test_employee_cannot_verify_document(self):
        self.document.status = "PENDING_REVIEW"
        self.document.save(update_fields=["status"])

        self.authenticate(self.employee)

        response = self.client.post(
            f"{self.url}{self.document.pk}/verify/"
        )

        self.assertEqual(response.status_code, 403)

        self.document.refresh_from_db()
        self.assertEqual(self.document.status, "PENDING_REVIEW")

    def test_hr_manager_can_reject_document_pending_review(self):
        self.document.status = "PENDING_REVIEW"
        self.document.save(update_fields=["status"])
        self.authenticate(self.hr_manager)

        response = self.client.post(
            f"{self.url}{self.document.pk}/reject/",
            {"reason": "The document is incomplete."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.document.refresh_from_db()
        self.assertEqual(self.document.status, "REJECTED")
        self.assertEqual(
            self.document.rejection_reason,
            "The document is incomplete.",
        )
        review = DocumentReview.objects.get(
            document=self.document,
        )
        self.assertEqual(
            review.reviewer,
            self.hr_manager,
        )
        self.assertEqual(
            review.decision,
            DocumentReview.Decision.REJECTED,
        )
        self.assertEqual(
            review.comment,
            "The document is incomplete.",
        )
        audit = AuditLog.objects.get(
            action="HR_DOCUMENT_REJECTED",
        )
        self.assertEqual(audit.user, self.hr_manager)
        self.assertNotIn(
            "The document is incomplete.",
            audit.details,
        )

        event = SecurityEvent.objects.get(
            event_type="HR_DOCUMENT_REJECTED",
        )
        self.assertEqual(event.user, self.hr_manager)
        self.assertEqual(
            event.request_path,
            f"{self.url}{self.document.pk}/reject/",
        )
        self.assertNotIn(
            "The document is incomplete.",
            event.details,
        )

    def test_reject_requires_reason(self):
        self.document.status = "PENDING_REVIEW"
        self.document.save(update_fields=["status"])
        self.authenticate(self.hr_manager)

        response = self.client.post(
            f"{self.url}{self.document.pk}/reject/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, "PENDING_REVIEW")
        self.assertEqual(self.document.rejection_reason, "")

    def test_reject_requires_non_blank_reason(self):
        self.document.status = "PENDING_REVIEW"
        self.document.save(update_fields=["status"])
        self.authenticate(self.hr_manager)

        response = self.client.post(
            f"{self.url}{self.document.pk}/reject/",
            {"reason": "   "},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, "PENDING_REVIEW")
        self.assertEqual(self.document.rejection_reason, "")

    def test_reject_rejects_document_not_pending_review(self):
        self.authenticate(self.hr_manager)

        response = self.client.post(
            f"{self.url}{self.document.pk}/reject/",
            {"reason": "The document is incomplete."},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, "PENDING_SCAN")
        self.assertEqual(self.document.rejection_reason, "")

    def test_employee_cannot_reject_document(self):
        self.document.status = "PENDING_REVIEW"
        self.document.save(update_fields=["status"])
        self.authenticate(self.employee)

        response = self.client.post(
            f"{self.url}{self.document.pk}/reject/",
            {"reason": "The document is incomplete."},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, "PENDING_REVIEW")
        self.assertEqual(self.document.rejection_reason, "")

    def test_hr_manager_can_archive_verified_document(self):
        self.document.status = "VERIFIED"
        self.document.save(update_fields=["status"])
        self.authenticate(self.hr_manager)

        response = self.client.post(
            f"{self.url}{self.document.pk}/archive/"
        )

        self.assertEqual(response.status_code, 200)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, "ARCHIVED")

        audit = AuditLog.objects.get(
            action="HR_DOCUMENT_ARCHIVED",
        )
        self.assertEqual(audit.user, self.hr_manager)

        event = SecurityEvent.objects.get(
            event_type="HR_DOCUMENT_ARCHIVED",
        )
        self.assertEqual(event.user, self.hr_manager)
        self.assertEqual(
            event.request_path,
            f"{self.url}{self.document.pk}/archive/",
        )

    def test_hr_manager_can_archive_rejected_document(self):
        self.document.status = "REJECTED"
        self.document.rejection_reason = "Incomplete document."
        self.document.save(
            update_fields=["status", "rejection_reason"]
        )
        self.authenticate(self.hr_manager)

        response = self.client.post(
            f"{self.url}{self.document.pk}/archive/"
        )

        self.assertEqual(response.status_code, 200)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, "ARCHIVED")
        self.assertEqual(
            self.document.rejection_reason,
            "Incomplete document.",
        )

    def test_archive_rejects_document_with_invalid_status(self):
        self.authenticate(self.hr_manager)

        response = self.client.post(
            f"{self.url}{self.document.pk}/archive/"
        )

        self.assertEqual(response.status_code, 400)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, "PENDING_SCAN")
        self.assertFalse(
            AuditLog.objects.filter(
                action="HR_DOCUMENT_ARCHIVED",
            ).exists()
        )
        self.assertFalse(
            SecurityEvent.objects.filter(
                event_type="HR_DOCUMENT_ARCHIVED",
            ).exists()
        )

    def test_employee_cannot_archive_document(self):
        self.document.status = "VERIFIED"
        self.document.save(update_fields=["status"])
        self.authenticate(self.employee)

        response = self.client.post(
            f"{self.url}{self.document.pk}/archive/"
        )

        self.assertEqual(response.status_code, 403)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, "VERIFIED")

    def test_employee_can_download_own_verified_document(self):
        from io import BytesIO
        from unittest.mock import patch

        self.document.status = HRDocument.Status.VERIFIED
        self.document.save(update_fields=["status"])

        self.authenticate(self.employee)

        with patch(
            "employees.views.hr_document_storage.open",
            return_value=BytesIO(b"%PDF-1.7 verified test document"),
        ):
            response = self.client.get(
                f"{self.url}{self.document.pk}/download/"
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(
            "attachment",
            response["Content-Disposition"],
        )
        self.assertIn(
            "contract.pdf",
            response["Content-Disposition"],
        )

    def test_quarantined_document_cannot_be_downloaded(self):
        from unittest.mock import patch

        self.document.status = HRDocument.Status.QUARANTINED
        self.document.save(update_fields=["status"])

        self.authenticate(self.super_admin)

        with patch(
            "employees.views.hr_document_storage.open"
        ) as mock_open:
            response = self.client.get(
                f"{self.url}{self.document.pk}/download/"
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )
        mock_open.assert_not_called()

    def test_employee_cannot_download_another_employees_document(self):
        self.other_document.status = HRDocument.Status.VERIFIED
        self.other_document.save(update_fields=["status"])

        self.authenticate(self.employee)

        response = self.client.get(
            f"{self.url}{self.other_document.pk}/download/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_unauthenticated_user_cannot_download_document(self):
        self.document.status = HRDocument.Status.VERIFIED
        self.document.save(update_fields=["status"])

        response = self.client.get(
            f"{self.url}{self.document.pk}/download/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_hr_manager_cannot_retrieve_restricted_document(self):
        self.document.confidentiality = "RESTRICTED"
        self.document.save(update_fields=["confidentiality"])

        self.client.force_authenticate(user=self.hr_manager)

        response = self.client.get(
            f"{self.url}{self.document.pk}/"
        )

        self.assertEqual(response.status_code, 404)

    def test_employee_cannot_retrieve_another_employees_document(self):
        self.client.force_authenticate(user=self.employee)

        response = self.client.get(
            f"{self.url}{self.other_document.pk}/"
        )

        self.assertEqual(response.status_code, 404)

    def test_inactive_employee_cannot_list_documents(self):
        self.employee.is_active = False
        self.employee.save(update_fields=["is_active"])

        self.client.force_authenticate(user=self.employee)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_employee_cannot_update_another_employees_document(self):
        self.client.force_authenticate(user=self.employee)

        response = self.client.patch(
            f"{self.url}{self.other_document.pk}/",
            {"title": "Unauthorized change"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)

    def test_employee_cannot_update_verified_document(self):
        self.document.status = HRDocument.Status.VERIFIED
        self.document.save(update_fields=["status"])

        self.client.force_authenticate(user=self.employee)

        response = self.client.patch(
            f"{self.url}{self.document.pk}/",
            {"title": "Unauthorized change"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_hr_manager_cannot_update_document(self):
        self.client.force_authenticate(user=self.hr_manager)

        response = self.client.patch(
            f"{self.url}{self.document.pk}/",
            {"title": "Unauthorized change"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_employee_cannot_update_document_metadata(self):
        original_metadata = {"source": "original"}
        self.document.metadata = original_metadata
        self.document.save(update_fields=["metadata"])

        self.client.force_authenticate(user=self.employee)

        response = self.client.patch(
            f"{self.url}{self.document.pk}/",
            {"metadata": {"source": "tampered"}},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.document.refresh_from_db()
        self.assertEqual(self.document.metadata, original_metadata)

    def test_employee_cannot_update_document_expiration(self):
        from datetime import date

        original_expiration = date(2027, 12, 31)
        self.document.expires_at = original_expiration
        self.document.save(update_fields=["expires_at"])

        self.client.force_authenticate(user=self.employee)

        response = self.client.patch(
            f"{self.url}{self.document.pk}/",
            {"expires_at": "2028-12-31"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.document.refresh_from_db()
        self.assertEqual(self.document.expires_at, original_expiration)

    def test_document_cannot_be_deleted_directly(self):
        self.client.force_authenticate(user=self.hr_admin)

        response = self.client.delete(
            f"{self.url}{self.document.pk}/"
        )

        self.assertIn(response.status_code, (403, 405))
        self.assertTrue(
            HRDocument.objects.filter(pk=self.document.pk).exists()
        )


    def test_hr_manager_without_profile_cannot_list_documents(self):
        self.manager_profile.delete()
        self.hr_manager.refresh_from_db()

        self.client.force_authenticate(user=self.hr_manager)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

    def test_hr_manager_without_profile_cannot_retrieve_document(self):
        self.manager_profile.delete()
        self.hr_manager.refresh_from_db()

        self.client.force_authenticate(user=self.hr_manager)

        response = self.client.get(
            f"{self.url}{self.document.pk}/"
        )

        self.assertEqual(response.status_code, 404)

    def test_hr_admin_can_retrieve_foreign_department_document(self):
        self.client.force_authenticate(user=self.hr_admin)

        response = self.client.get(
            f"{self.url}{self.foreign_document.pk}/"
        )

        self.assertEqual(response.status_code, 200)

    def test_super_admin_can_retrieve_foreign_department_document(self):
        self.client.force_authenticate(user=self.super_admin)

        response = self.client.get(
            f"{self.url}{self.foreign_document.pk}/"
        )

        self.assertEqual(response.status_code, 200)

    def test_hr_manager_cannot_download_document(self):
        self.document.status = HRDocument.Status.VERIFIED
        self.document.save(update_fields=["status"])

        self.client.force_authenticate(user=self.hr_manager)

        response = self.client.get(
            f"{self.url}{self.document.pk}/download/"
        )

        self.assertEqual(response.status_code, 403)

    def test_hr_manager_cannot_create_document_version(self):
        self.client.force_authenticate(user=self.hr_manager)

        response = self.client.post(
            f"{self.url}{self.document.pk}/create-version/",
            {
                "file": SimpleUploadedFile(
                    "contract-v2.pdf",
                    b"%PDF-1.7 test content",
                    content_type="application/pdf",
                )
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 403)

        self.assertFalse(
            DocumentVersion.objects.filter(
                document=self.document,
            ).exists()
        )

    def test_hr_manager_cannot_view_foreign_department_review_history(self):
        self.foreign_document.status = "PENDING_REVIEW"
        self.foreign_document.save(update_fields=["status"])

        self.client.force_authenticate(user=self.hr_manager)

        response = self.client.get(
            f"{self.url}{self.foreign_document.pk}/reviews/"
        )

        self.assertEqual(response.status_code, 404)

class DocumentAccessServiceTests(TestCase):
    """Unit tests for HR document access rules."""

    def setUp(self):
        from employees.services.document_access import (
            DocumentAccessService,
        )

        self.access = DocumentAccessService

        self.super_admin = User.objects.create_user(
            email="access-admin@example.com",
            name="Access Super Admin",
            password="StrongPassword123!",
            role="SUPER_ADMIN",
        )
        self.hr_admin = User.objects.create_user(
            email="access-hradmin@example.com",
            name="Access HR Admin",
            password="StrongPassword123!",
            role="HR_ADMIN",
        )
        self.hr_manager = User.objects.create_user(
            email="access-manager@example.com",
            name="Access HR Manager",
            password="StrongPassword123!",
            role="HR_MANAGER",
        )
        self.employee = User.objects.create_user(
            email="access-employee@example.com",
            name="Access Employee",
            password="StrongPassword123!",
            role="EMPLOYEE",
        )
        self.other_employee = User.objects.create_user(
            email="access-other@example.com",
            name="Other Access Employee",
            password="StrongPassword123!",
            role="EMPLOYEE",
        )

        self.department = Department.objects.create(
            name="Access Test Department",
            code="ATD",
        )
        position = Position.objects.create(
            title="Access Test Position",
            department=self.department,
        )

        self.profile = EmployeeProfile.objects.create(
            user=self.employee,
            employee_id="ACCESS-001",
            department=self.department,
            position=position,
            hire_date=date(2026, 1, 15),
        )
        self.other_profile = EmployeeProfile.objects.create(
            user=self.other_employee,
            employee_id="ACCESS-002",
            department=self.department,
            position=position,
            hire_date=date(2026, 2, 1),
        )
        self.manager_profile = EmployeeProfile.objects.create(
            user=self.hr_manager,
            employee_id="ACCESS-MANAGER",
            department=self.department,
            position=position,
            hire_date=date(2026, 1, 10),
        )

        self.other_department = Department.objects.create(
            name="Other Access Department",
            code="OAD",
        )

        self.other_position = Position.objects.create(
            title="Other Access Position",
            department=self.other_department,
        )

        self.foreign_employee = User.objects.create_user(
            email="access-foreign@example.com",
            name="Foreign Department Employee",
            password="StrongPassword123!",
            role="EMPLOYEE",
        )

        self.foreign_profile = EmployeeProfile.objects.create(
            user=self.foreign_employee,
            employee_id="ACCESS-003",
            department=self.other_department,
            position=self.other_position,
            hire_date=date(2026, 3, 1),
        )
        self.document = HRDocument.objects.create(
            employee=self.profile,
            title="Access Test Contract",
            document_type=HRDocument.DocumentType.EMPLOYMENT_CONTRACT,
            original_filename="access-contract.pdf",
            storage_key="hr-documents/access/contract.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            uploaded_by=self.hr_admin,
        )

        self.other_document = HRDocument.objects.create(
            employee=self.other_profile,
            title="Other Access Contract",
            document_type=HRDocument.DocumentType.EMPLOYMENT_CONTRACT,
            original_filename="other-contract.pdf",
            storage_key="hr-documents/access/other-contract.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            uploaded_by=self.hr_admin,
        )
        self.foreign_document = HRDocument.objects.create(
            employee=self.foreign_profile,
            title="Foreign Department Contract",
            document_type=HRDocument.DocumentType.EMPLOYMENT_CONTRACT,
            original_filename="foreign-contract.pdf",
            storage_key="hr-documents/access/foreign-contract.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            uploaded_by=self.hr_admin,
        )


    def test_privileged_roles_can_view_restricted_document(self):
        self.document.confidentiality = "RESTRICTED"

        self.assertTrue(
            self.access.can_view_document(
                self.super_admin, self.document
            )
        )
        self.assertTrue(
            self.access.can_view_document(
                self.hr_admin, self.document
            )
        )

    def test_hr_manager_cannot_view_restricted_document(self):
        self.document.confidentiality = "RESTRICTED"

        self.assertFalse(
            self.access.can_view_document(
                self.hr_manager, self.document
            )
        )

    def test_employee_can_view_own_confidential_document(self):
        self.document.confidentiality = "CONFIDENTIAL"

        self.assertTrue(
            self.access.can_view_document(
                self.employee, self.document
            )
        )

    def test_employee_cannot_view_another_employees_document(self):
        self.assertFalse(
            self.access.can_view_document(
                self.employee, self.other_document
            )
        )

    def test_employee_cannot_view_restricted_document(self):
        self.document.confidentiality = "RESTRICTED"

        self.assertFalse(
            self.access.can_view_document(
                self.employee, self.document
            )
        )

    def test_hr_manager_can_view_document_in_own_department(self):
        self.assertTrue(
            self.access.can_view_document(
                self.hr_manager,
                self.document,
            )
        )

    def test_hr_manager_cannot_view_other_department_document(self):
        self.assertFalse(
            self.access.can_view_document(
                self.hr_manager,
                self.foreign_document,
            )
        )

    def test_hr_admin_can_view_other_department_document(self):
        self.assertTrue(
            self.access.can_view_document(
                self.hr_admin,
                self.foreign_document,
            )
        )

    def test_super_admin_can_view_other_department_document(self):
        self.assertTrue(
            self.access.can_view_document(
                self.super_admin,
                self.foreign_document,
            )
        )

    def test_hr_manager_accessible_queryset_is_department_scoped(self):
        accessible = self.access.get_accessible_documents(
            self.hr_manager
        )

        self.assertTrue(
            accessible.filter(pk=self.document.pk).exists()
        )
        self.assertTrue(
            accessible.filter(pk=self.other_document.pk).exists()
        )
        self.assertFalse(
            accessible.filter(pk=self.foreign_document.pk).exists()
        )

    def test_download_requires_verified_status(self):
        self.document.status = HRDocument.Status.PENDING_REVIEW

        self.assertFalse(
            self.access.can_download_document(
                self.super_admin, self.document
            )
        )

    def test_employee_can_download_own_verified_document(self):
        self.document.status = HRDocument.Status.VERIFIED

        self.assertTrue(
            self.access.can_download_document(
                self.employee, self.document
            )
        )

    def test_employee_cannot_download_another_employees_document(self):
        self.other_document.status = HRDocument.Status.VERIFIED

        self.assertFalse(
            self.access.can_download_document(
                self.employee, self.other_document
            )
        )

    def test_hr_manager_cannot_download_document(self):
        self.document.status = HRDocument.Status.VERIFIED

        self.assertFalse(
            self.access.can_download_document(
                self.hr_manager, self.document
            )
        )

    def test_inactive_user_cannot_view_document(self):
        self.employee.is_active = False

        self.assertFalse(
            self.access.can_view_document(
                self.employee, self.document
            )
        )

    def test_inactive_user_cannot_download_document(self):
        self.employee.is_active = False
        self.document.status = HRDocument.Status.VERIFIED

        self.assertFalse(
            self.access.can_download_document(
                self.employee, self.document
            )
        )

    def test_employee_cannot_manage_verified_document(self):
        self.document.status = HRDocument.Status.VERIFIED

        self.assertFalse(
            self.access.can_manage_document(
                self.employee, self.document
            )
        )

    def test_employee_can_manage_own_pending_document(self):
        self.document.status = HRDocument.Status.PENDING_REVIEW

        self.assertTrue(
            self.access.can_manage_document(
                self.employee, self.document
            )
        )

    def test_accessible_queryset_excludes_restricted_documents(self):
        self.document.confidentiality = "RESTRICTED"
        self.document.save(update_fields=["confidentiality"])

        accessible = self.access.get_accessible_documents(
            self.employee
        )

        self.assertFalse(
            accessible.filter(pk=self.document.pk).exists()
        )
        self.assertTrue(
            accessible.filter(pk=self.other_document.pk).exists()
            is False
        )

class OnboardingServiceTests(TestCase):
    """Tests for onboarding template publication and journey creation."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from employees.models import (
            EmployeeProfile,
            OnboardingActivityTemplate,
            OnboardingPhase,
            OnboardingTemplate,
        )

        User = get_user_model()
        self.admin = User.objects.create_user(
            email="onboarding-admin@example.com",
            name="Onboarding Admin",
            password="TestPassword123!",
            is_active=True,
        )

        self.employee_user = User.objects.create_user(
            email="onboarding-employee@example.com",
            name="Onboarding Employee",
            password="TestPassword123!",
            is_active=True,
        )

        from datetime import date

        self.employee = EmployeeProfile.objects.create(
            user=self.employee_user,
            hire_date=date.today(),
        )

        self.template = OnboardingTemplate.objects.create(
            name="Standard onboarding",
            description="Standard employee onboarding",
            version=1,
            created_by=self.admin,
        )

        self.phase = OnboardingPhase.objects.create(
            template=self.template,
            name="First day",
            description="First-day activities",
            order=1,
        )

        self.activity = OnboardingActivityTemplate.objects.create(
            phase=self.phase,
            name="Complete HR paperwork",
            description="Complete the required HR forms",
            order=1,
            is_required=True,
            default_due_days=3,
        )

    def test_publish_complete_template(self):
        published = OnboardingService.publish_template(self.template.pk)

        self.assertEqual(
            published.status,
            self.template.Status.PUBLISHED,
        )
        self.assertIsNotNone(published.published_at)

    def test_cannot_publish_template_without_phases(self):
        self.activity.delete()
        self.phase.delete()

        with self.assertRaises(ValidationError):
            OnboardingService.publish_template(self.template.pk)


    def test_cannot_publish_phase_without_activities(self):
        self.activity.delete()

        with self.assertRaises(ValidationError):
            OnboardingService.publish_template(self.template.pk)

    def test_cannot_publish_template_twice(self):
        OnboardingService.publish_template(self.template.pk)

        with self.assertRaises(ValidationError):
            OnboardingService.publish_template(self.template.pk)

    def test_cannot_create_journey_from_draft_template(self):
        with self.assertRaises(ValidationError):
            OnboardingService.create_journey(
                employee_id=self.employee.pk,
                template_id=self.template.pk,
                created_by=self.admin,
            )

    def test_create_journey_preserves_template_version(self):
        OnboardingService.publish_template(self.template.pk)

        journey = OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=self.template.pk,
            created_by=self.admin,
        )

        self.assertEqual(journey.employee_id, self.employee.pk)
        self.assertEqual(journey.template_id, self.template.pk)
        self.assertEqual(journey.template_version, self.template.version)

    def test_create_journey_creates_tasks_from_template_activities(self):
        OnboardingService.publish_template(self.template.pk)

        journey = OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=self.template.pk,
            created_by=self.admin,
        )

        tasks = journey.tasks.all()

        self.assertEqual(tasks.count(), 1)
        self.assertEqual(tasks.first().title, self.activity.name)
        self.assertEqual(
            tasks.first().description,
            self.activity.description,
        )

    def test_cannot_create_journey_for_inactive_employee(self):
        self.employee_user.is_active = False
        self.employee_user.save(update_fields=["is_active"])

        OnboardingService.publish_template(self.template.pk)

        with self.assertRaises(ValidationError):
            OnboardingService.create_journey(
                employee_id=self.employee.pk,
                template_id=self.template.pk,
                created_by=self.admin,
            )

    def test_cannot_create_journey_for_nonexistent_employee(self):
        from uuid import uuid4

        OnboardingService.publish_template(self.template.pk)

        with self.assertRaises(ValidationError):
            OnboardingService.create_journey(
                employee_id=uuid4(),
                template_id=self.template.pk,
                created_by=self.admin,
            )

    def test_cannot_create_journey_from_nonexistent_template(self):
        from uuid import uuid4

        with self.assertRaises(ValidationError):
            OnboardingService.create_journey(
                employee_id=self.employee.pk,
                template_id=uuid4(),
                created_by=self.admin,
            )

    def test_cannot_create_duplicate_active_journey(self):
        OnboardingService.publish_template(self.template.pk)

        OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=self.template.pk,
            created_by=self.admin,
        )

        with self.assertRaises(ValidationError):
            OnboardingService.create_journey(
                employee_id=self.employee.pk,
                template_id=self.template.pk,
                created_by=self.admin,
            )

    def test_can_create_new_journey_after_previous_journey_is_cancelled(self):
        OnboardingService.publish_template(self.template.pk)

        first_journey = OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=self.template.pk,
            created_by=self.admin,
        )

        first_journey.status = first_journey.Status.CANCELLED
        first_journey.save(update_fields=["status", "updated_at"])

        second_journey = OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=self.template.pk,
            created_by=self.admin,
        )

        self.assertNotEqual(first_journey.pk, second_journey.pk)
        self.assertEqual(
            second_journey.status,
            second_journey.Status.PENDING,
        )

    def test_can_create_new_journey_after_previous_journey_is_completed(self):
        OnboardingService.publish_template(self.template.pk)

        first_journey = OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=self.template.pk,
            created_by=self.admin,
        )

        first_journey.status = first_journey.Status.COMPLETED
        first_journey.save(update_fields=["status", "updated_at"])

        second_journey = OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=self.template.pk,
            created_by=self.admin,
        )

        self.assertNotEqual(first_journey.pk, second_journey.pk)
        self.assertEqual(
            second_journey.status,
            second_journey.Status.PENDING,
        )

    def test_cannot_create_journey_with_inactive_creator(self):
        self.admin.is_active = False
        self.admin.save(update_fields=["is_active"])

        OnboardingService.publish_template(self.template.pk)

        with self.assertRaises(ValidationError):
            OnboardingService.create_journey(
                employee_id=self.employee.pk,
                template_id=self.template.pk,
                created_by=self.admin,
            )

    def test_cannot_create_journey_with_unauthenticated_creator(self):
        from django.contrib.auth.models import AnonymousUser

        OnboardingService.publish_template(self.template.pk)

        with self.assertRaises(ValidationError):
            OnboardingService.create_journey(
                employee_id=self.employee.pk,
                template_id=self.template.pk,
                created_by=AnonymousUser(),
            )

    def test_create_journey_preserves_target_completion_date(self):
        from datetime import timedelta

        target_date = timezone.now().date() + timedelta(days=30)
        OnboardingService.publish_template(self.template.pk)

        journey = OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=self.template.pk,
            created_by=self.admin,
            target_completion_date=target_date,
        )

        self.assertEqual(journey.target_completion_date, target_date)

    def test_create_journey_creates_task_for_each_activity(self):
        OnboardingService.publish_template(self.template.pk)

        journey = OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=self.template.pk,
            created_by=self.admin,
        )

        self.assertEqual(journey.tasks.count(), 1)

    def test_create_journey_creates_tasks_for_multiple_activities(self):
        from employees.models import OnboardingActivityTemplate

        OnboardingActivityTemplate.objects.create(
            phase=self.phase,
            name="Set up workstation",
            order=2,
            is_required=True,
            default_due_days=5,
        )

        OnboardingService.publish_template(self.template.pk)

        journey = OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=self.template.pk,
            created_by=self.admin,
        )

        self.assertEqual(journey.tasks.count(), 2)

    def test_cannot_create_journey_from_unpublished_template(self):
        from employees.models import OnboardingTemplate, OnboardingJourney

        self.assertEqual(
            self.template.status,
            OnboardingTemplate.Status.DRAFT,
        )

        with self.assertRaises(ValidationError):
            OnboardingService.create_journey(
                employee_id=self.employee.pk,
                template_id=self.template.pk,
                created_by=self.admin,
            )

        self.assertEqual(
            OnboardingJourney.objects.filter(
                employee=self.employee,
                template=self.template,
            ).count(),
            0,
        )

    def test_cannot_publish_already_published_template(self):
        from employees.models import OnboardingTemplate

        OnboardingService.publish_template(self.template.pk)

        self.template.refresh_from_db()
        original_published_at = self.template.published_at

        with self.assertRaises(ValidationError):
            OnboardingService.publish_template(self.template.pk)

        self.template.refresh_from_db()

        self.assertEqual(
            self.template.status,
            OnboardingTemplate.Status.PUBLISHED,
        )
        self.assertEqual(
            self.template.published_at,
            original_published_at,
        )

    def test_cannot_publish_template_with_phase_without_activities(self):
        from employees.models import OnboardingActivityTemplate

        self.activity.delete()

        with self.assertRaises(ValidationError):
            OnboardingService.publish_template(self.template.pk)

        self.template.refresh_from_db()

        self.assertEqual(
            self.template.status,
            self.template.Status.DRAFT,
        )

    def test_create_journey_preserves_template_version(self):
        OnboardingService.publish_template(self.template.pk)

        journey = OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=self.template.pk,
            created_by=self.admin,
        )

        self.assertEqual(
            journey.template_version,
            self.template.version,
        )

    def test_create_journey_does_not_modify_published_template(self):
        from employees.models import OnboardingTemplate

        OnboardingService.publish_template(self.template.pk)

        self.template.refresh_from_db()
        original_published_at = self.template.published_at
        original_version = self.template.version

        OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=self.template.pk,
            created_by=self.admin,
        )

        self.template.refresh_from_db()

        self.assertEqual(
            self.template.status,
            OnboardingTemplate.Status.PUBLISHED,
        )
        self.assertEqual(
            self.template.published_at,
            original_published_at,
        )
        self.assertEqual(self.template.version, original_version)

    def test_failed_task_creation_rolls_back_journey(self):
        from unittest.mock import patch
        from employees.models import OnboardingJourney

        OnboardingService.publish_template(self.template.pk)

        initial_count = OnboardingJourney.objects.filter(
            employee=self.employee,
            template=self.template,
        ).count()

        with patch(
            "employees.services.onboarding.OnboardingTask.objects.bulk_create",
            side_effect=RuntimeError("Simulated task creation failure"),
        ):
            with self.assertRaises(RuntimeError):
                OnboardingService.create_journey(
                    employee_id=self.employee.pk,
                    template_id=self.template.pk,
                    created_by=self.admin,
                )

        final_count = OnboardingJourney.objects.filter(
            employee=self.employee,
            template=self.template,
        ).count()

        self.assertEqual(final_count, initial_count)

    def test_create_journey_creates_one_task_per_activity(self):
        from employees.models import OnboardingActivityTemplate

        OnboardingActivityTemplate.objects.create(
            phase=self.phase,
            name="Set up workstation",
            order=2,
            is_required=True,
            default_due_days=5,
        )

        OnboardingService.publish_template(self.template.pk)

        journey = OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=self.template.pk,
            created_by=self.admin,
        )

        task_activity_ids = list(
            journey.tasks.values_list(
                "activity_template_id",
                flat=True,
            )
        )

        self.assertEqual(len(task_activity_ids), 2)
        self.assertEqual(len(set(task_activity_ids)), 2)

    def test_create_journey_calculates_task_due_dates(self):
        from datetime import timedelta
        from django.utils import timezone
        from employees.models import OnboardingActivityTemplate

        activity_without_deadline = OnboardingActivityTemplate.objects.create(
            phase=self.phase,
            name="Optional orientation",
            order=2,
            is_required=False,
            default_due_days=None,
        )

        today = timezone.localdate()

        OnboardingService.publish_template(self.template.pk)

        journey = OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=self.template.pk,
            created_by=self.admin,
        )

        task_with_deadline = journey.tasks.get(
            activity_template=self.activity,
        )
        task_without_deadline = journey.tasks.get(
            activity_template=activity_without_deadline,
        )

        self.assertEqual(
            task_with_deadline.due_date,
            today + timedelta(days=self.activity.default_due_days),
        )
        self.assertIsNone(task_without_deadline.due_date)

    def test_create_journey_orders_tasks_by_phase_and_activity(self):
        from employees.models import (
            OnboardingActivityTemplate,
            OnboardingPhase,
        )

        second_phase = OnboardingPhase.objects.create(
            template=self.template,
            name="Second day",
            order=2,
        )

        later_activity = OnboardingActivityTemplate.objects.create(
            phase=second_phase,
            name="Meet the team",
            order=1,
            is_required=True,
        )

        earlier_activity = OnboardingActivityTemplate.objects.create(
            phase=self.phase,
            name="Complete HR paperwork - second",
            order=2,
            is_required=True,
        )

        OnboardingService.publish_template(self.template.pk)

        journey = OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=self.template.pk,
            created_by=self.admin,
        )

        task_activity_ids = list(
            journey.tasks.order_by(
                "activity_template__phase__order",
                "activity_template__order",
            ).values_list(
                "activity_template_id",
                flat=True,
            )
        )

        self.assertEqual(
            task_activity_ids,
            [
                self.activity.pk,
                earlier_activity.pk,
                later_activity.pk,
            ],
        )

    def test_cannot_create_journey_with_inactive_employee(self):
        self.employee.user.is_active = False
        self.employee.user.save(update_fields=["is_active"])
        OnboardingService.publish_template(self.template.pk)

        with self.assertRaises(ValidationError):
            OnboardingService.create_journey(
                employee_id=self.employee.pk,
                template_id=self.template.pk,
                created_by=self.admin,
            )


    def test_cannot_modify_activity_of_published_template(self):
        OnboardingService.publish_template(self.template.pk)

        with self.assertRaises(ValidationError):
            self.activity.delete()

        self.activity.refresh_from_db()
        self.assertEqual(self.activity.phase, self.phase)

    def test_cannot_create_journey_with_inactive_creator_does_not_create_journey(self):
        from employees.models import OnboardingJourney

        self.admin.is_active = False
        self.admin.save(update_fields=["is_active"])
        OnboardingService.publish_template(self.template.pk)

        with self.assertRaises(ValidationError):
            OnboardingService.create_journey(
                employee_id=self.employee.pk,
                template_id=self.template.pk,
                created_by=self.admin,
            )

        self.assertFalse(
            OnboardingJourney.objects.filter(
                employee=self.employee,
                template=self.template,
            ).exists()
        )

    def test_created_journey_starts_with_pending_status(self):
        from employees.models import OnboardingJourney

        OnboardingService.publish_template(self.template.pk)

        journey = OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=self.template.pk,
            created_by=self.admin,
        )

        self.assertEqual(
            journey.status,
            OnboardingJourney.Status.PENDING,
        )

    def test_created_tasks_reference_their_activity_templates(self):
        OnboardingService.publish_template(self.template.pk)

        journey = OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=self.template.pk,
            created_by=self.admin,
        )

        task = journey.tasks.get()

        self.assertEqual(task.activity_template, self.activity)
        self.assertEqual(task.title, self.activity.name)
        self.assertEqual(task.description, self.activity.description)

    def test_create_journey_preserves_creator(self):
        OnboardingService.publish_template(self.template.pk)

        journey = OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=self.template.pk,
            created_by=self.admin,
        )

        self.assertEqual(journey.created_by, self.admin)

    def test_create_journey_without_target_completion_date(self):
        OnboardingService.publish_template(self.template.pk)

        journey = OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=self.template.pk,
            created_by=self.admin,
        )

        self.assertIsNone(journey.target_completion_date)

    def test_created_tasks_preserve_activity_titles(self):
        OnboardingService.publish_template(self.template.pk)

        journey = OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=self.template.pk,
            created_by=self.admin,
        )

        task = journey.tasks.get()
        self.assertEqual(task.title, self.activity.name)

    def test_created_tasks_preserve_activity_descriptions(self):
        OnboardingService.publish_template(self.template.pk)

        journey = OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=self.template.pk,
            created_by=self.admin,
        )

        task = journey.tasks.get()
        self.assertEqual(task.description, self.activity.description)

    def test_created_tasks_reference_correct_activity_template(self):
        OnboardingService.publish_template(self.template.pk)

        journey = OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=self.template.pk,
            created_by=self.admin,
        )

        task = journey.tasks.get()
        self.assertEqual(task.activity_template_id, self.activity.pk)

    def test_create_journey_preserves_creator(self):
        OnboardingService.publish_template(self.template.pk)

        journey = OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=self.template.pk,
            created_by=self.admin,
        )

        self.assertEqual(journey.created_by, self.admin)

    def test_created_journey_starts_with_pending_status(self):
        from employees.models import OnboardingJourney

        OnboardingService.publish_template(self.template.pk)

        journey = OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=self.template.pk,
            created_by=self.admin,
        )

        self.assertEqual(
            journey.status,
            OnboardingJourney.Status.PENDING,
        )

class TaskAssignmentServiceTests(TestCase):
    """Tests for onboarding task assignment business logic."""

    def setUp(self):
        from datetime import date
        from django.contrib.auth import get_user_model
        from employees.models import (
            EmployeeProfile,
            OnboardingActivityTemplate,
            OnboardingPhase,
            OnboardingTemplate,
            Department,
            Position,
        )
        from employees.services.onboarding import OnboardingService

        User = get_user_model()

        self.admin = User.objects.create_user(
            email="assignment-admin@example.com",
            name="Assignment Admin",
            password="TestPassword123!",
            role="HR_ADMIN",
            is_active=True,
        )

        self.employee_user = User.objects.create_user(
            email="assignment-employee@example.com",
            name="Assignment Employee",
            password="TestPassword123!",
            is_active=True,
        )

        self.assignee = User.objects.create_user(
            email="assignment-assignee@example.com",
            name="Assignment Assignee",
            password="TestPassword123!",
            is_active=True,
        )
        department = Department.objects.create(
            name="Assignment Engineering",
            code="ASSIGN",
        )

        position = Position.objects.create(
            title="Assignment Specialist",
            department=department,
        )
        EmployeeProfile.objects.create(
            user=self.assignee,
            employee_id="ASSIGN-001",
            department=department,
            position=position,
            hire_date=date.today(),
        )
        employee = EmployeeProfile.objects.create(
            user=self.employee_user,
            employee_id="ASSIGN-002",
            department=department,
            position=position,
            hire_date=date.today(),
        )

        template = OnboardingTemplate.objects.create(
            name="Assignment test template",
            description="Template for assignment tests",
            version=1,
            created_by=self.admin,
        )

        phase = OnboardingPhase.objects.create(
            template=template,
            name="First day",
            description="First-day activities",
            order=1,
        )

        OnboardingActivityTemplate.objects.create(
            phase=phase,
            name="Complete HR paperwork",
            description="Complete required HR forms",
            order=1,
            is_required=True,
            default_due_days=3,
        )

        OnboardingService.publish_template(template.pk)

        journey = OnboardingService.create_journey(
            employee_id=employee.pk,
            template_id=template.pk,
            created_by=self.admin,
        )

        self.task = journey.tasks.get()

    def test_assign_task_to_active_user(self):
        from employees.services.task_assignment import TaskAssignmentService

        assigned_task = TaskAssignmentService.assign_task(
            task_id=self.task.pk,
            assigned_to_id=self.assignee.pk,
            actor=self.admin,
        )

        self.assertEqual(assigned_task.assigned_to_id, self.assignee.pk)

        self.task.refresh_from_db()
        self.assertEqual(self.task.assigned_to_id, self.assignee.pk)

    def test_cannot_assign_task_to_nonexistent_user(self):
        from uuid import uuid4
        from django.core.exceptions import ValidationError
        from employees.services.task_assignment import TaskAssignmentService

        with self.assertRaises(ValidationError):
            TaskAssignmentService.assign_task(
                task_id=self.task.pk,
                assigned_to_id=uuid4(),
                actor=self.admin,
            )

        self.task.refresh_from_db()
        self.assertIsNone(self.task.assigned_to_id)

    def test_cannot_assign_task_to_inactive_user(self):
        from django.core.exceptions import ValidationError
        from employees.services.task_assignment import TaskAssignmentService

        self.assignee.is_active = False
        self.assignee.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError):
            TaskAssignmentService.assign_task(
                task_id=self.task.pk,
                assigned_to_id=self.assignee.pk,
                actor=self.admin,
            )

        self.task.refresh_from_db()
        self.assertIsNone(self.task.assigned_to_id)

    def test_cannot_assign_nonexistent_task(self):
        from uuid import uuid4
        from django.core.exceptions import ValidationError
        from employees.services.task_assignment import TaskAssignmentService

        with self.assertRaises(ValidationError):
            TaskAssignmentService.assign_task(
                task_id=uuid4(),
                assigned_to_id=self.assignee.pk,
                actor=self.admin,
            )

    def test_cannot_assign_completed_task(self):
        from django.core.exceptions import ValidationError
        from employees.models import OnboardingTask
        from employees.services.task_assignment import TaskAssignmentService

        self.task.status = OnboardingTask.Status.COMPLETED
        self.task.save(update_fields=["status", "updated_at"])

        with self.assertRaises(ValidationError):
            TaskAssignmentService.assign_task(
                task_id=self.task.pk,
                assigned_to_id=self.assignee.pk,
                actor=self.admin,
            )

    def test_cannot_assign_cancelled_task(self):
        from django.core.exceptions import ValidationError
        from employees.models import OnboardingTask
        from employees.services.task_assignment import TaskAssignmentService

        self.task.status = OnboardingTask.Status.CANCELLED
        self.task.save(update_fields=["status", "updated_at"])

        with self.assertRaises(ValidationError):
            TaskAssignmentService.assign_task(
                task_id=self.task.pk,
                assigned_to_id=self.assignee.pk,
                actor=self.admin,
            )

    def test_cannot_assign_task_without_assignee(self):
        from django.core.exceptions import ValidationError
        from employees.services.task_assignment import TaskAssignmentService

        with self.assertRaises(ValidationError):
            TaskAssignmentService.assign_task(
                task_id=self.task.pk,
                assigned_to_id=None,
                actor=self.admin,
            )

    def test_cannot_assign_task_to_user_without_employee_profile(self):
        from django.core.exceptions import ValidationError
        from employees.services.task_assignment import TaskAssignmentService

        # The admin account is active but has no EmployeeProfile.
        with self.assertRaises(ValidationError):
            TaskAssignmentService.assign_task(
                task_id=self.task.pk,
                assigned_to_id=self.admin.pk,
                actor=self.admin,
            )

        self.task.refresh_from_db()
        self.assertIsNone(self.task.assigned_to_id)

    def test_reassignment_records_previous_and_new_assignee(self):
        from employees.models import WorkflowExecutionLog
        from employees.services.task_assignment import TaskAssignmentService

        # First assignment.
        TaskAssignmentService.assign_task(
            task_id=self.task.pk,
            assigned_to_id=self.assignee.pk,
            actor=self.admin,
        )

        new_assignee = type(self.assignee).objects.create_user(
            email="assignment-new-assignee@example.com",
            name="New Assignment Assignee",
            password="TestPassword123!",
            is_active=True,
        )

        from datetime import date
        from employees.models import EmployeeProfile, Department, Position

        department = Department.objects.get(code="ASSIGN")
        position = Position.objects.get(
            title="Assignment Specialist",
            department=department,
        )
        EmployeeProfile.objects.create(
            user=new_assignee,
            employee_id="ASSIGN-003",
            department=department,
            position=position,
            hire_date=date.today(),
        )

        TaskAssignmentService.assign_task(
            task_id=self.task.pk,
            assigned_to_id=new_assignee.pk,
            actor=self.admin,
        )

        self.task.refresh_from_db()
        self.assertEqual(self.task.assigned_to_id, new_assignee.pk)

        log = WorkflowExecutionLog.objects.get(
            task=self.task,
            event_type="TASK_REASSIGNED",
        )
        self.assertEqual(log.actor_id, self.admin.pk)
        self.assertEqual(
            log.details["previous_assignee_id"],
            str(self.assignee.pk),
        )
        self.assertEqual(
            log.details["new_assignee_id"],
            str(new_assignee.pk),
        )

    def test_employee_cannot_assign_task(self):
        from django.core.exceptions import ValidationError
        from employees.services.task_assignment import TaskAssignmentService

        with self.assertRaises(ValidationError):
            TaskAssignmentService.assign_task(
                task_id=self.task.pk,
                assigned_to_id=self.assignee.pk,
                actor=self.employee_user,
            )

        self.task.refresh_from_db()
        self.assertIsNone(self.task.assigned_to_id)

    def test_assigning_same_user_does_not_create_reassignment_log(self):
        from employees.models import WorkflowExecutionLog
        from employees.services.task_assignment import TaskAssignmentService

        TaskAssignmentService.assign_task(
            task_id=self.task.pk,
            assigned_to_id=self.assignee.pk,
            actor=self.admin,
        )

        logs_before = WorkflowExecutionLog.objects.filter(
            task=self.task,
        ).count()

        TaskAssignmentService.assign_task(
            task_id=self.task.pk,
            assigned_to_id=self.assignee.pk,
            actor=self.admin,
        )

        logs_after = WorkflowExecutionLog.objects.filter(
            task=self.task,
        ).count()

        self.assertEqual(logs_after, logs_before)

class WorkflowEngineTests(TestCase):
    """Tests for onboarding workflow task transitions."""

    def setUp(self):
        from datetime import date

        from django.contrib.auth import get_user_model

        from employees.models import (
            EmployeeProfile,
            Department,
            Position,
            OnboardingActivityTemplate,
            OnboardingPhase,
            OnboardingTemplate,
            OnboardingJourney,
            OnboardingTask,
        )
        from employees.services.onboarding import OnboardingService

        User = get_user_model()

        self.admin = User.objects.create_user(
            email="workflow-admin@example.com",
            name="Workflow Admin",
            password="TestPassword123!",
            role="HR_ADMIN",
            is_active=True,
        )

        self.employee_user = User.objects.create_user(
            email="workflow-employee@example.com",
            name="Workflow Employee",
            password="TestPassword123!",
            role="EMPLOYEE",
            is_active=True,
        )

        self.department = Department.objects.create(
            name="Workflow Department",
            code="WFLOW",
        )

        self.position = Position.objects.create(
            title="Workflow Specialist",
            department=self.department,
        )

        self.employee = EmployeeProfile.objects.create(
            user=self.employee_user,
            employee_id="WFLOW-001",
            department=self.department,
            position=self.position,
            hire_date=date.today(),
        )

        self.template = OnboardingTemplate.objects.create(
            name="Workflow test template",
            description="Template for workflow engine tests",
            version=1,
            created_by=self.admin,
        )

        self.phase = OnboardingPhase.objects.create(
            template=self.template,
            name="Workflow phase",
            description="Phase for workflow tests",
            order=1,
        )

        self.activity = OnboardingActivityTemplate.objects.create(
            phase=self.phase,
            name="Workflow task",
            description="Task used to test transitions",
            order=1,
            is_required=True,
            default_due_days=3,
        )

        OnboardingService.publish_template(self.template.pk)

        self.journey = OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=self.template.pk,
            created_by=self.admin,
        )

        self.task = self.journey.tasks.get()

    def test_pending_task_can_start(self):
        from employees.models import OnboardingTask
        from employees.services.workflow_engine import WorkflowEngine

        task = WorkflowEngine.transition_task(
            task_id=self.task.pk,
            target_status=OnboardingTask.Status.IN_PROGRESS,
            actor=self.admin,
        )

        self.assertEqual(task.status, OnboardingTask.Status.IN_PROGRESS)
        self.assertIsNotNone(task.started_at)

    def test_in_progress_task_can_be_completed(self):
        from employees.models import OnboardingTask
        from employees.services.workflow_engine import WorkflowEngine

        WorkflowEngine.transition_task(
            task_id=self.task.pk,
            target_status=OnboardingTask.Status.IN_PROGRESS,
            actor=self.admin,
        )

        task = WorkflowEngine.transition_task(
            task_id=self.task.pk,
            target_status=OnboardingTask.Status.COMPLETED,
            actor=self.admin,
        )

        self.assertEqual(task.status, OnboardingTask.Status.COMPLETED)
        self.assertIsNotNone(task.completed_at)

    def test_cannot_complete_pending_task_directly(self):
        from django.core.exceptions import ValidationError
        from employees.models import OnboardingTask
        from employees.services.workflow_engine import WorkflowEngine

        with self.assertRaises(ValidationError):
            WorkflowEngine.transition_task(
                task_id=self.task.pk,
                target_status=OnboardingTask.Status.COMPLETED,
                actor=self.admin,
            )

        self.task.refresh_from_db()
        self.assertEqual(
            self.task.status,
            OnboardingTask.Status.PENDING,
        )

    def test_employee_cannot_transition_task(self):
        from django.core.exceptions import ValidationError
        from employees.models import OnboardingTask
        from employees.services.workflow_engine import WorkflowEngine

        with self.assertRaises(ValidationError):
            WorkflowEngine.transition_task(
                task_id=self.task.pk,
                target_status=OnboardingTask.Status.IN_PROGRESS,
                actor=self.employee_user,
            )

        self.task.refresh_from_db()
        self.assertEqual(
            self.task.status,
            OnboardingTask.Status.PENDING,
        )

    def test_cannot_start_task_with_incomplete_prerequisite(self):
        from django.core.exceptions import ValidationError
        from employees.models import (
            OnboardingActivityTemplate,
            OnboardingPhase,
            OnboardingTemplate,
            OnboardingTask,
            TaskDependency,
        )
        from employees.services.onboarding import OnboardingService
        from employees.services.workflow_engine import WorkflowEngine

        # Create a separate template for the prerequisite task.
        prerequisite_template = OnboardingTemplate.objects.create(
            name="Prerequisite workflow template",
            description="Template for prerequisite test",
            version=1,
            created_by=self.admin,
        )

        prerequisite_phase = OnboardingPhase.objects.create(
            template=prerequisite_template,
            name="Prerequisite phase",
            description="Phase for prerequisite test",
            order=1,
        )

        prerequisite_activity = OnboardingActivityTemplate.objects.create(
            phase=prerequisite_phase,
            name="Prerequisite task",
            description="Must be completed first",
            order=1,
            is_required=True,
            default_due_days=3,
        )

        OnboardingService.publish_template(prerequisite_template.pk)

        prerequisite_journey = OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=prerequisite_template.pk,
            created_by=self.admin,
        )

        prerequisite_task = prerequisite_journey.tasks.get()

        # Link the prerequisite task to the task being tested.
        TaskDependency.objects.create(
            prerequisite_task=prerequisite_task,
            dependent_task=self.task,
        )

        with self.assertRaises(ValidationError):
            WorkflowEngine.transition_task(
                task_id=self.task.pk,
                target_status=OnboardingTask.Status.IN_PROGRESS,
                actor=self.admin,
            )

        self.task.refresh_from_db()
        self.assertEqual(
            self.task.status,
            OnboardingTask.Status.PENDING,
        )

    def test_successful_transition_creates_audit_log(self):
        from employees.models import (
            OnboardingTask,
            WorkflowExecutionLog,
        )
        from employees.services.workflow_engine import WorkflowEngine

        WorkflowEngine.transition_task(
            task_id=self.task.pk,
            target_status=OnboardingTask.Status.IN_PROGRESS,
            actor=self.admin,
        )

        log = WorkflowExecutionLog.objects.get(
            task=self.task,
            event_type="TASK_STATUS_CHANGED",
        )

        self.assertEqual(log.actor_id, self.admin.pk)
        self.assertEqual(
            log.outcome,
            WorkflowExecutionLog.Outcome.SUCCESS,
        )
        self.assertEqual(
            log.details["previous_status"],
            OnboardingTask.Status.PENDING,
        )
        self.assertEqual(
            log.details["new_status"],
            OnboardingTask.Status.IN_PROGRESS,
        )

    def test_completed_task_cannot_transition_again(self):
        from django.core.exceptions import ValidationError
        from employees.models import OnboardingTask
        from employees.services.workflow_engine import WorkflowEngine

        WorkflowEngine.transition_task(
            task_id=self.task.pk,
            target_status=OnboardingTask.Status.IN_PROGRESS,
            actor=self.admin,
        )

        WorkflowEngine.transition_task(
            task_id=self.task.pk,
            target_status=OnboardingTask.Status.COMPLETED,
            actor=self.admin,
        )

        with self.assertRaises(ValidationError):
            WorkflowEngine.transition_task(
                task_id=self.task.pk,
                target_status=OnboardingTask.Status.IN_PROGRESS,
                actor=self.admin,
            )

        self.task.refresh_from_db()
        self.assertEqual(
            self.task.status,
            OnboardingTask.Status.COMPLETED,
        )

    def test_inactive_admin_cannot_transition_task(self):
        from django.core.exceptions import ValidationError
        from employees.models import OnboardingTask
        from employees.services.workflow_engine import WorkflowEngine

        self.admin.is_active = False
        self.admin.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError):
            WorkflowEngine.transition_task(
                task_id=self.task.pk,
                target_status=OnboardingTask.Status.IN_PROGRESS,
                actor=self.admin,
            )

        self.task.refresh_from_db()
        self.assertEqual(
            self.task.status,
            OnboardingTask.Status.PENDING,
        )

    def test_transition_of_nonexistent_task_fails(self):
        from django.core.exceptions import ValidationError
        from uuid import uuid4
        from employees.models import OnboardingTask
        from employees.services.workflow_engine import WorkflowEngine

        with self.assertRaises(ValidationError):
            WorkflowEngine.transition_task(
                task_id=uuid4(),
                target_status=OnboardingTask.Status.IN_PROGRESS,
                actor=self.admin,
            )

class OnboardingNotificationServiceTests(TestCase):
    """Tests for onboarding task email notifications."""

    def setUp(self):
        from datetime import date

        from django.contrib.auth import get_user_model
        from employees.models import (
            Department,
            EmployeeProfile,
            OnboardingActivityTemplate,
            OnboardingPhase,
            OnboardingTemplate,
            Position,
        )
        from employees.services.onboarding import OnboardingService

        User = get_user_model()

        self.admin = User.objects.create_user(
            email="notification-admin@example.com",
            name="Notification Admin",
            password="TestPassword123!",
            role="HR_ADMIN",
            is_active=True,
        )

        self.employee_user = User.objects.create_user(
            email="notification-employee@example.com",
            name="Notification Employee",
            password="TestPassword123!",
            role="EMPLOYEE",
            is_active=True,
        )

        department = Department.objects.create(
            name="Notification Department",
            code="NOTIF",
        )
        position = Position.objects.create(
            title="Notification Specialist",
            department=department,
        )
        employee = EmployeeProfile.objects.create(
            user=self.employee_user,
            employee_id="NOTIF-001",
            department=department,
            position=position,
            hire_date=date.today(),
        )

        template = OnboardingTemplate.objects.create(
            name="Notification test template",
            description="Template for notification tests",
            version=1,
            created_by=self.admin,
        )
        phase = OnboardingPhase.objects.create(
            template=template,
            name="Notification phase",
            description="Phase for notification tests",
            order=1,
        )
        OnboardingActivityTemplate.objects.create(
            phase=phase,
            name="Confidential task title",
            description="Confidential task description",
            order=1,
            is_required=True,
            default_due_days=3,
        )

        OnboardingService.publish_template(template.pk)
        self.journey = OnboardingService.create_journey(
            employee_id=employee.pk,
            template_id=template.pk,
            created_by=self.admin,
        )
        self.task = self.journey.tasks.get()

    def test_task_assignment_notification_creates_job(self):
        from employees.models import NotificationJob
        from employees.services.onboarding_notifications import (
            OnboardingNotificationService,
        )

        self.task.assigned_to = self.employee_user
        self.task.save(update_fields=["assigned_to"])

        result = OnboardingNotificationService.notify_task_assigned(
            task_id=self.task.pk,
        )

        self.assertTrue(result)

        job = NotificationJob.objects.get(
            notification_type=NotificationJob.NotificationType.TASK_ASSIGNED,
        )

        self.assertEqual(job.status, NotificationJob.Status.PENDING)
        self.assertEqual(
            job.payload["task_id"],
            str(self.task.pk),
        )
        self.assertEqual(
            job.payload["recipient_user_id"],
            str(self.employee_user.pk),
        )
        self.assertNotIn(self.employee_user.email, str(job.payload))
        self.assertNotIn("Confidential task title", str(job.payload))
        self.assertNotIn(
            "Confidential task description",
            str(job.payload),
        )

    def test_unassigned_task_does_not_create_job(self):
        from employees.models import NotificationJob
        from employees.services.onboarding_notifications import (
            OnboardingNotificationService,
        )

        result = OnboardingNotificationService.notify_task_assigned(
            task_id=self.task.pk,
        )

        self.assertFalse(result)
        self.assertEqual(NotificationJob.objects.count(), 0)

    def test_incomplete_task_does_not_create_completion_job(self):
        from employees.models import NotificationJob
        from employees.services.onboarding_notifications import (
            OnboardingNotificationService,
        )

        result = OnboardingNotificationService.notify_task_completed(
            task_id=self.task.pk,
        )

        self.assertFalse(result)
        self.assertEqual(NotificationJob.objects.count(), 0)

    def test_duplicate_assignment_notification_is_idempotent(self):
        from employees.models import NotificationJob
        from employees.services.onboarding_notifications import (
            OnboardingNotificationService,
        )

        self.task.assigned_to = self.employee_user
        self.task.save(update_fields=["assigned_to"])

        first_result = OnboardingNotificationService.notify_task_assigned(
            task_id=self.task.pk,
        )
        second_result = OnboardingNotificationService.notify_task_assigned(
            task_id=self.task.pk,
        )

        self.assertTrue(first_result)
        self.assertTrue(second_result)
        self.assertEqual(
            NotificationJob.objects.filter(
                notification_type=NotificationJob.NotificationType.TASK_ASSIGNED,
            ).count(),
            1,
        )

    def test_assignment_service_creates_notification_job(self):
        from employees.models import NotificationJob
        from employees.services.task_assignment import TaskAssignmentService

        TaskAssignmentService.assign_task(
            task_id=self.task.pk,
            assigned_to_id=self.employee_user.pk,
            actor=self.admin,
        )

        job = NotificationJob.objects.get(
            notification_type=NotificationJob.NotificationType.TASK_ASSIGNED,
        )

        self.assertEqual(
            job.payload["recipient_user_id"],
            str(self.employee_user.pk),
        )

    def test_workflow_engine_creates_completion_notification_job(self):
        from employees.models import NotificationJob, OnboardingTask
        from employees.services.workflow_engine import WorkflowEngine

        WorkflowEngine.transition_task(
            task_id=self.task.pk,
            target_status=OnboardingTask.Status.IN_PROGRESS,
            actor=self.admin,
        )
        WorkflowEngine.transition_task(
            task_id=self.task.pk,
            target_status=OnboardingTask.Status.COMPLETED,
            actor=self.admin,
        )

        job = NotificationJob.objects.get(
            notification_type=NotificationJob.NotificationType.TASK_COMPLETED,
        )

        self.assertEqual(
            job.payload["recipient_user_id"],
            str(self.admin.pk),
        )
        self.assertEqual(job.status, NotificationJob.Status.PENDING)

    def _create_notification_document(
        self,
        *,
        status,
        expires_at,
        storage_suffix,
    ):
        from employees.models import HRDocument

        return HRDocument.objects.create(
            employee=self.task.journey.employee,
            title=f"Notification document {storage_suffix}",
            document_type=HRDocument.DocumentType.EMPLOYMENT_CONTRACT,
            original_filename=f"{storage_suffix}.pdf",
            storage_key=f"hr-documents/notification/{storage_suffix}.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            uploaded_by=self.admin,
            status=status,
            expires_at=expires_at,
        )

    def test_overdue_task_notification_is_created_idempotently(self):
        from datetime import timedelta

        from django.utils import timezone
        from employees.models import NotificationJob
        from employees.services.onboarding_notifications import (
            OnboardingNotificationService,
        )

        self.task.assigned_to = self.employee_user
        self.task.due_date = timezone.localdate() - timedelta(days=1)
        self.task.save(update_fields=["assigned_to", "due_date"])

        first_count = (
            OnboardingNotificationService
            .enqueue_overdue_task_notifications()
        )
        second_count = (
            OnboardingNotificationService
            .enqueue_overdue_task_notifications()
        )

        self.assertEqual(first_count, 1)
        self.assertEqual(second_count, 0)

        job = NotificationJob.objects.get(
            notification_type=NotificationJob.NotificationType.TASK_OVERDUE,
        )
        self.assertEqual(job.status, NotificationJob.Status.PENDING)
        self.assertEqual(job.payload["task_id"], str(self.task.pk))
        self.assertEqual(
            job.payload["recipient_user_id"],
            str(self.employee_user.pk),
        )
        self.assertNotIn(self.employee_user.email, str(job.payload))


    def test_reassigned_overdue_task_creates_notification_for_new_assignee(self):
        from datetime import timedelta

        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from employees.models import NotificationJob
        from employees.services.onboarding_notifications import (
            OnboardingNotificationService,
        )

        User = get_user_model()

        new_assignee = User.objects.create_user(
            email="notification-new-assignee@example.com",
            name="New Notification Assignee",
            password="TestPassword123!",
            role="EMPLOYEE",
            is_active=True,
        )

        self.task.assigned_to = self.employee_user
        self.task.due_date = timezone.localdate() - timedelta(days=1)
        self.task.save(update_fields=["assigned_to", "due_date"])

        first_count = (
            OnboardingNotificationService
            .enqueue_overdue_task_notifications()
        )

        self.task.assigned_to = new_assignee
        self.task.save(update_fields=["assigned_to"])

        second_count = (
            OnboardingNotificationService
            .enqueue_overdue_task_notifications()
        )

        self.assertEqual(first_count, 1)
        self.assertEqual(second_count, 1)

        jobs = NotificationJob.objects.filter(
            notification_type=NotificationJob.NotificationType.TASK_OVERDUE,
        ).order_by("created_at")

        self.assertEqual(jobs.count(), 2)

        recipients = set(
            jobs.values_list("payload__recipient_user_id", flat=True)
        )

        self.assertEqual(
            recipients,
            {
                str(self.employee_user.pk),
                str(new_assignee.pk),
            },
        )


    def test_completed_task_does_not_receive_overdue_notification(self):
        from datetime import timedelta

        from django.utils import timezone
        from employees.models import NotificationJob, OnboardingTask
        from employees.services.onboarding_notifications import (
            OnboardingNotificationService,
        )

        self.task.assigned_to = self.employee_user
        self.task.due_date = timezone.localdate() - timedelta(days=1)
        self.task.status = OnboardingTask.Status.COMPLETED
        self.task.save(
            update_fields=["assigned_to", "due_date", "status"]
        )

        count = (
            OnboardingNotificationService
            .enqueue_overdue_task_notifications()
        )

        self.assertEqual(count, 0)
        self.assertFalse(
            NotificationJob.objects.filter(
                notification_type=NotificationJob.NotificationType.TASK_OVERDUE,
            ).exists()
        )

    def test_unassigned_overdue_task_does_not_create_notification(self):
        from datetime import timedelta

        from django.utils import timezone
        from employees.models import NotificationJob
        from employees.services.onboarding_notifications import (
            OnboardingNotificationService,
        )

        self.task.due_date = timezone.localdate() - timedelta(days=1)
        self.task.save(update_fields=["due_date"])

        count = (
            OnboardingNotificationService
            .enqueue_overdue_task_notifications()
        )

        self.assertEqual(count, 0)
        self.assertFalse(
            NotificationJob.objects.filter(
                notification_type=NotificationJob.NotificationType.TASK_OVERDUE,
            ).exists()
        )

    def test_expiring_verified_document_notification_is_idempotent(self):
        from datetime import timedelta

        from django.utils import timezone
        from employees.models import HRDocument, NotificationJob
        from employees.services.onboarding_notifications import (
            OnboardingNotificationService,
        )

        document = self._create_notification_document(
            status=HRDocument.Status.VERIFIED,
            expires_at=timezone.localdate() + timedelta(days=10),
            storage_suffix="verified-expiring",
        )

        first_count = (
            OnboardingNotificationService
            .enqueue_expiring_document_notifications()
        )
        second_count = (
            OnboardingNotificationService
            .enqueue_expiring_document_notifications()
        )

        self.assertEqual(first_count, 1)
        self.assertEqual(second_count, 0)

        job = NotificationJob.objects.get(
            notification_type=(
                NotificationJob.NotificationType.DOCUMENT_EXPIRING
            ),
        )
        self.assertEqual(job.status, NotificationJob.Status.PENDING)
        self.assertEqual(job.payload["document_id"], str(document.pk))
        self.assertEqual(
            job.payload["recipient_user_id"],
            str(self.employee_user.pk),
        )
        self.assertNotIn(self.employee_user.email, str(job.payload))

    def test_ineligible_documents_do_not_create_expiration_notifications(self):
        from datetime import timedelta

        from django.utils import timezone
        from employees.models import HRDocument, NotificationJob
        from employees.services.onboarding_notifications import (
            OnboardingNotificationService,
        )

        today = timezone.localdate()

        self._create_notification_document(
            status=HRDocument.Status.PENDING_REVIEW,
            expires_at=today + timedelta(days=10),
            storage_suffix="pending-review",
        )
        self._create_notification_document(
            status=HRDocument.Status.VERIFIED,
            expires_at=today + timedelta(days=31),
            storage_suffix="outside-window",
        )
        self._create_notification_document(
            status=HRDocument.Status.VERIFIED,
            expires_at=today,
            storage_suffix="expires-today",
        )

        count = (
            OnboardingNotificationService
            .enqueue_expiring_document_notifications()
        )

        self.assertEqual(count, 0)
        self.assertFalse(
            NotificationJob.objects.filter(
                notification_type=(
                    NotificationJob.NotificationType.DOCUMENT_EXPIRING
                ),
            ).exists()
        )

    def test_cancelled_task_does_not_receive_overdue_notification(self):
        from datetime import timedelta

        from django.utils import timezone
        from employees.models import NotificationJob, OnboardingTask
        from employees.services.onboarding_notifications import (
            OnboardingNotificationService,
        )

        self.task.assigned_to = self.employee_user
        self.task.due_date = timezone.localdate() - timedelta(days=1)
        self.task.status = OnboardingTask.Status.CANCELLED
        self.task.save(
            update_fields=["assigned_to", "due_date", "status"]
        )

        count = (
            OnboardingNotificationService
            .enqueue_overdue_task_notifications()
        )

        self.assertEqual(count, 0)
        self.assertFalse(
            NotificationJob.objects.filter(
                notification_type=NotificationJob.NotificationType.TASK_OVERDUE,
            ).exists()
        )

    def test_inactive_assignee_does_not_receive_overdue_notification(self):
        from datetime import timedelta

        from django.utils import timezone
        from employees.models import NotificationJob
        from employees.services.onboarding_notifications import (
            OnboardingNotificationService,
        )

        self.employee_user.is_active = False
        self.employee_user.save(update_fields=["is_active"])

        self.task.assigned_to = self.employee_user
        self.task.due_date = timezone.localdate() - timedelta(days=1)
        self.task.save(update_fields=["assigned_to", "due_date"])

        count = (
            OnboardingNotificationService
            .enqueue_overdue_task_notifications()
        )

        self.assertEqual(count, 0)
        self.assertFalse(
            NotificationJob.objects.filter(
                notification_type=NotificationJob.NotificationType.TASK_OVERDUE,
            ).exists()
        )

class OnboardingPermissionServiceTests(TestCase):
    """Tests for centralized onboarding authorization rules."""

    def setUp(self):
        from datetime import date

        from django.contrib.auth import get_user_model
        from employees.models import (
            Department,
            EmployeeProfile,
            OnboardingActivityTemplate,
            OnboardingPhase,
            OnboardingTemplate,
            Position,
        )
        from employees.services.onboarding import OnboardingService

        User = get_user_model()

        self.admin = User.objects.create_user(
            email="permission-admin@example.com",
            name="Permission Admin",
            password="TestPassword123!",
            role="HR_ADMIN",
            is_active=True,
        )
        self.manager = User.objects.create_user(
            email="permission-manager@example.com",
            name="Permission Manager",
            password="TestPassword123!",
            role="HR_MANAGER",
            is_active=True,
        )
        self.employee_user = User.objects.create_user(
            email="permission-employee@example.com",
            name="Permission Employee",
            password="TestPassword123!",
            role="EMPLOYEE",
            is_active=True,
        )
        self.other_employee_user = User.objects.create_user(
            email="permission-other@example.com",
            name="Other Employee",
            password="TestPassword123!",
            role="EMPLOYEE",
            is_active=True,
        )

        department = Department.objects.create(
            name="Permission Department",
            code="PERM",
        )
        position = Position.objects.create(
            title="Permission Specialist",
            department=department,
        )

        self.employee = EmployeeProfile.objects.create(
            user=self.employee_user,
            employee_id="PERM-001",
            department=department,
            position=position,
            hire_date=date.today(),
        )
        self.other_employee = EmployeeProfile.objects.create(
            user=self.other_employee_user,
            employee_id="PERM-002",
            department=department,
            position=position,
            hire_date=date.today(),
        )

        template = OnboardingTemplate.objects.create(
            name="Permission test template",
            description="Template for permission tests",
            version=1,
            created_by=self.admin,
        )
        phase = OnboardingPhase.objects.create(
            template=template,
            name="First day",
            description="Permission test phase",
            order=1,
        )
        OnboardingActivityTemplate.objects.create(
            phase=phase,
            name="Complete paperwork",
            description="Permission test activity",
            order=1,
            is_required=True,
            default_due_days=3,
        )

        OnboardingService.publish_template(template.pk)

        self.journey = OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=template.pk,
            created_by=self.admin,
        )
        self.other_journey = OnboardingService.create_journey(
            employee_id=self.other_employee.pk,
            template_id=template.pk,
            created_by=self.admin,
        )
        self.task = self.journey.tasks.get()
        self.other_task = self.other_journey.tasks.get()

    def test_hr_roles_can_manage_templates(self):
        from employees.services.onboarding_permissions import (
            OnboardingPermissionService as Permissions,
        )

        self.assertTrue(Permissions.can_manage_templates(self.admin))

        super_admin = type(self.admin).objects.create_user(
            email="permission-superadmin@example.com",
            name="Permission Super Admin",
            password="TestPassword123!",
            role="SUPER_ADMIN",
        )
        self.assertTrue(Permissions.can_manage_templates(super_admin))
        self.assertFalse(Permissions.can_manage_templates(self.manager))
        self.assertFalse(
            Permissions.can_manage_templates(self.employee_user)
        )

    def test_only_operational_roles_can_assign_and_transition_tasks(self):
        from employees.services.onboarding_permissions import (
            OnboardingPermissionService as Permissions,
        )

        for user in (self.admin, self.manager):
            with self.subTest(role=user.role):
                self.assertTrue(Permissions.can_assign_tasks(user))
                self.assertTrue(Permissions.can_transition_tasks(user))

        self.assertFalse(
            Permissions.can_assign_tasks(self.employee_user)
        )
        self.assertFalse(
            Permissions.can_transition_tasks(self.employee_user)
        )

    def test_employee_can_view_own_journey_but_not_another_journey(self):
        from employees.services.onboarding_permissions import (
            OnboardingPermissionService as Permissions,
        )

        self.assertTrue(
            Permissions.can_view_journey(
                self.employee_user,
                self.journey,
            )
        )
        self.assertFalse(
            Permissions.can_view_journey(
                self.employee_user,
                self.other_journey,
            )
        )
        self.assertTrue(
            Permissions.can_view_journey(self.manager, self.other_journey)
        )

    def test_employee_can_view_own_task_but_not_another_employee_task(self):
        from employees.services.onboarding_permissions import (
            OnboardingPermissionService as Permissions,
        )

        self.assertTrue(
            Permissions.can_view_task(self.employee_user, self.task)
        )
        self.assertFalse(
            Permissions.can_view_task(self.employee_user, self.other_task)
        )
        self.assertTrue(
            Permissions.can_view_task(self.manager, self.other_task)
        )

    def test_assigned_employee_can_view_task_outside_own_journey(self):
        from employees.services.onboarding_permissions import (
            OnboardingPermissionService as Permissions,
        )

        self.other_task.assigned_to = self.employee_user
        self.other_task.save(update_fields=["assigned_to"])

        self.assertTrue(
            Permissions.can_view_task(self.employee_user, self.other_task)
        )

    def test_inactive_user_cannot_access_onboarding_permissions(self):
        from employees.services.onboarding_permissions import (
            OnboardingPermissionService as Permissions,
        )

        self.employee_user.is_active = False
        self.employee_user.save(update_fields=["is_active"])

        self.assertFalse(
            Permissions.can_view_journey(self.employee_user, self.journey)
        )
        self.assertFalse(
            Permissions.can_view_task(self.employee_user, self.task)
        )
        self.assertFalse(
            Permissions.can_manage_templates(self.employee_user)
        )
        self.assertFalse(
            Permissions.can_assign_tasks(self.employee_user)
        )
        self.assertFalse(
            Permissions.can_transition_tasks(self.employee_user)
        )

    def test_missing_objects_are_denied(self):
        from employees.services.onboarding_permissions import (
            OnboardingPermissionService as Permissions,
        )

        self.assertFalse(Permissions.can_view_journey(self.admin, None))
        self.assertFalse(Permissions.can_view_task(self.admin, None))

    def test_anonymous_user_is_denied(self):
        from django.contrib.auth.models import AnonymousUser

        from employees.services.onboarding_permissions import (
            OnboardingPermissionService as Permissions,
        )

        anonymous = AnonymousUser()

        self.assertFalse(Permissions.can_view_journey(anonymous, self.journey))
        self.assertFalse(Permissions.can_view_task(anonymous, self.task))
        self.assertFalse(Permissions.can_manage_templates(anonymous))
        self.assertFalse(Permissions.can_assign_tasks(anonymous))
        self.assertFalse(Permissions.can_transition_tasks(anonymous))

class OnboardingRBACAPITests(TestCase):
    """Test role-based access control for onboarding APIs."""

    def setUp(self):
        from django.urls import reverse

        from employees.services.onboarding import OnboardingService
        from employees.models import (
            OnboardingTemplate,
            OnboardingPhase,
            OnboardingActivityTemplate,
        )

        self.client = APIClient()
        self.reverse = reverse

        self.super_admin = User.objects.create_user(
            email="onboarding-api-admin@example.com",
            name="Onboarding API Admin",
            password="StrongPassword123!",
            role="SUPER_ADMIN",
            is_staff=True,
            is_superuser=True,
        )
        self.hr_admin = User.objects.create_user(
            email="onboarding-api-hr@example.com",
            name="Onboarding API HR Admin",
            password="StrongPassword123!",
            role="HR_ADMIN",
        )
        self.hr_manager = User.objects.create_user(
            email="onboarding-api-manager@example.com",
            name="Onboarding API HR Manager",
            password="StrongPassword123!",
            role="HR_MANAGER",
        )
        self.employee_user = User.objects.create_user(
            email="onboarding-api-employee@example.com",
            name="Onboarding API Employee",
            password="StrongPassword123!",
            role="EMPLOYEE",
        )
        self.other_employee_user = User.objects.create_user(
            email="onboarding-api-other@example.com",
            name="Onboarding API Other Employee",
            password="StrongPassword123!",
            role="EMPLOYEE",
        )

        self.employee = EmployeeProfile.objects.create(
            user=self.employee_user,
            employee_id="ONBAPI-002",
            hire_date=date.today(),
        )
        self.other_employee = EmployeeProfile.objects.create(
            user=self.other_employee_user,
            employee_id="ONBAPI-001",
            hire_date=date.today(),
        )

        template = OnboardingTemplate.objects.create(
            name="Onboarding API test template",
            description="Template used by API RBAC tests",
            version=1,
            created_by=self.hr_admin,
        )
        phase = OnboardingPhase.objects.create(
            template=template,
            name="First day",
            description="First-day activities",
            order=1,
        )
        OnboardingActivityTemplate.objects.create(
            phase=phase,
            name="Complete paperwork",
            description="Complete the required paperwork",
            order=1,
            is_required=True,
            default_due_days=3,
        )

        OnboardingService.publish_template(template.pk)

        self.journey = OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=template.pk,
            created_by=self.hr_admin,
        )
        self.other_journey = OnboardingService.create_journey(
            employee_id=self.other_employee.pk,
            template_id=template.pk,
            created_by=self.hr_admin,
        )

        self.task = self.journey.tasks.get()
        self.other_task = self.other_journey.tasks.get()

        self.journeys_url = reverse("onboarding-journey-list")
        self.tasks_url = reverse("onboarding-task-list")

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def test_hr_roles_can_list_all_journeys(self):
        for user in (
            self.super_admin,
            self.hr_admin,
            self.hr_manager,
        ):
            with self.subTest(role=user.role):
                self.authenticate(user)
                response = self.client.get(self.journeys_url)

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data["count"], 2)

    def test_employee_only_sees_own_journey(self):
        self.authenticate(self.employee_user)

        response = self.client.get(self.journeys_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            str(response.data["results"][0]["id"]),
            str(self.journey.pk),
        )

    def test_employee_cannot_retrieve_another_journey(self):
        self.authenticate(self.employee_user)
        url = self.reverse(
            "onboarding-journey-detail",
            kwargs={"pk": self.other_journey.pk},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_hr_roles_can_list_all_tasks(self):
        for user in (
            self.super_admin,
            self.hr_admin,
            self.hr_manager,
        ):
            with self.subTest(role=user.role):
                self.authenticate(user)
                response = self.client.get(self.tasks_url)

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data["count"], 2)

    def test_employee_only_sees_tasks_from_own_journey(self):
        self.authenticate(self.employee_user)

        response = self.client.get(self.tasks_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            str(response.data["results"][0]["id"]),
            str(self.task.pk),
        )

    def test_employee_cannot_retrieve_another_employees_task(self):
        self.authenticate(self.employee_user)
        url = self.reverse(
            "onboarding-task-detail",
            kwargs={"pk": self.other_task.pk},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_employee_cannot_assign_a_task(self):
        self.authenticate(self.employee_user)
        url = self.reverse(
            "onboarding-task-assign",
            kwargs={"pk": self.task.pk},
        )

        response = self.client.post(
            url,
            {"assigned_to_id": self.other_employee_user.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_employee_cannot_transition_a_task(self):
        self.authenticate(self.employee_user)
        url = self.reverse(
            "onboarding-task-transition",
            kwargs={"pk": self.task.pk},
        )

        response = self.client.post(
            url,
            {"target_status": self.task.status},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_employee_cannot_create_a_journey_directly(self):
        self.authenticate(self.employee_user)

        response = self.client.post(
            self.journeys_url,
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_employee_cannot_create_a_task_directly(self):
        self.authenticate(self.employee_user)

        response = self.client.post(
            self.tasks_url,
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

class DocumentReviewServiceTests(TestCase):
    """Security and lifecycle tests for DocumentReviewService."""

    def setUp(self):
        from employees.services.document_review import DocumentReviewService

        self.service = DocumentReviewService

        self.owner = User.objects.create_user(
            email="review-owner@example.com",
            name="Document Owner",
            password="TestPass123!",
        )

        self.reviewer = User.objects.create_user(
            email="review-manager@example.com",
            name="HR Reviewer",
            password="TestPass123!",
            role="HR_MANAGER",
        )

        self.department = Department.objects.create(
            name="Review Department",
            code="REV",
        )

        self.position = Position.objects.create(
            title="Review Employee",
            department=self.department,
        )

        self.profile = EmployeeProfile.objects.create(
            user=self.owner,
            employee_id="REV-001",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 15),
        )
        self.reviewer_profile = EmployeeProfile.objects.create(
            user=self.reviewer,
            employee_id="REV-MGR-001",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 15),
        )

        self.other_department = Department.objects.create(
            name="Other Review Department",
            code="OREV",
        )

        self.other_position = Position.objects.create(
            title="Other Review Employee",
            department=self.other_department,
        )

        self.other_owner = User.objects.create_user(
            email="review-other-owner@example.com",
            name="Other Document Owner",
            password="TestPass123!",
        )

        self.other_profile = EmployeeProfile.objects.create(
            user=self.other_owner,
            employee_id="OREV-001",
            department=self.other_department,
            position=self.other_position,
            hire_date=date(2026, 1, 15),
        )

        self.other_document = HRDocument.objects.create(
            employee=self.other_profile,
            title="Other Department Contract",
            document_type=HRDocument.DocumentType.EMPLOYMENT_CONTRACT,
            original_filename="other-contract.pdf",
            storage_key="hr-documents/review/other-contract.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            uploaded_by=self.other_owner,
            status=HRDocument.Status.PENDING_REVIEW,
        )
        self.document = HRDocument.objects.create(
            employee=self.profile,
            title="Employment Contract",
            document_type=HRDocument.DocumentType.EMPLOYMENT_CONTRACT,
            original_filename="contract.pdf",
            storage_key="hr-documents/review/contract.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            uploaded_by=self.owner,
            status=HRDocument.Status.PENDING_REVIEW,
        )

    def review(self, **kwargs):
        defaults = {
            "document_id": self.document.pk,
            "actor": self.reviewer,
            "decision": DocumentReview.Decision.APPROVED,
        }
        defaults.update(kwargs)
        return self.service.review_document(**defaults)

    def test_hr_manager_can_review_document_in_own_department(self):
        review = self.review()

        self.assertEqual(review.document, self.document)
        self.assertEqual(review.reviewer, self.reviewer)

    def test_hr_manager_cannot_review_other_department_document(self):
        with self.assertRaises(PermissionDenied):
            self.service.review_document(
                document_id=self.other_document.pk,
                actor=self.reviewer,
                decision=DocumentReview.Decision.APPROVED,
            )

        self.assertFalse(
            DocumentReview.objects.filter(
                document=self.other_document
            ).exists()
        )

        self.other_document.refresh_from_db()

        self.assertEqual(
            self.other_document.status,
            HRDocument.Status.PENDING_REVIEW,
        )

    def test_hr_manager_without_profile_cannot_review_document(self):
        self.reviewer_profile.delete()
        self.reviewer.refresh_from_db()

        with self.assertRaises(PermissionDenied):
            self.review()

        self.assertFalse(
            DocumentReview.objects.filter(
                document=self.document
            ).exists()
        )

    def test_hr_admin_can_review_other_department_document(self):
        admin = User.objects.create_user(
            email="review-admin@example.com",
            name="HR Administrator",
            password="TestPass123!",
            role="HR_ADMIN",
        )

        review = self.service.review_document(
            document_id=self.other_document.pk,
            actor=admin,
            decision=DocumentReview.Decision.APPROVED,
        )

        self.assertEqual(review.reviewer, admin)

    def test_super_admin_can_review_other_department_document(self):
        admin = User.objects.create_superuser(
            email="review-superadmin@example.com",
            name="Super Administrator",
            password="TestPass123!",
        )

        review = self.service.review_document(
            document_id=self.other_document.pk,
            actor=admin,
            decision=DocumentReview.Decision.APPROVED,
        )

        self.assertEqual(review.reviewer, admin)

    def test_approval_verifies_document_and_records_reviewer(self):
        review = self.review()

        self.document.refresh_from_db()

        self.assertEqual(
            review.decision,
            DocumentReview.Decision.APPROVED,
        )
        self.assertEqual(review.document, self.document)
        self.assertEqual(review.reviewer, self.reviewer)
        self.assertEqual(
            self.document.status,
            HRDocument.Status.VERIFIED,
        )
        self.assertEqual(self.document.verified_by, self.reviewer)
        self.assertIsNotNone(self.document.verified_at)
        self.assertEqual(
            DocumentReview.objects.filter(document=self.document).count(),
            1,
        )

    def test_rejection_requires_reason(self):
        with self.assertRaises(ValidationError):
            self.review(
                decision=DocumentReview.Decision.REJECTED,
                comment="   ",
            )

        self.document.refresh_from_db()

        self.assertEqual(
            self.document.status,
            HRDocument.Status.PENDING_REVIEW,
        )
        self.assertFalse(
            DocumentReview.objects.filter(document=self.document).exists()
        )

    def test_rejection_records_reason_and_updates_document(self):
        reason = "The contract is incomplete."

        review = self.review(
            decision=DocumentReview.Decision.REJECTED,
            comment=reason,
        )

        self.document.refresh_from_db()

        self.assertEqual(review.comment, reason)
        self.assertEqual(
            self.document.status,
            HRDocument.Status.REJECTED,
        )
        self.assertEqual(self.document.rejection_reason, reason)
        self.assertIsNone(self.document.verified_by)
        self.assertIsNone(self.document.verified_at)

    def test_employee_cannot_review_document(self):
        with self.assertRaises(PermissionDenied):
            self.service.review_document(
                document_id=self.document.pk,
                actor=self.owner,
                decision=DocumentReview.Decision.APPROVED,
            )

        self.assertFalse(
            DocumentReview.objects.filter(document=self.document).exists()
        )

    def test_document_owner_cannot_review_even_with_hr_role(self):
        self.owner.role = "HR_MANAGER"
        self.owner.save(update_fields=["role"])

        with self.assertRaises(PermissionDenied):
            self.service.review_document(
                document_id=self.document.pk,
                actor=self.owner,
                decision=DocumentReview.Decision.APPROVED,
            )

        self.assertFalse(
            DocumentReview.objects.filter(document=self.document).exists()
        )

    def test_inactive_reviewer_is_denied(self):
        self.reviewer.is_active = False
        self.reviewer.save(update_fields=["is_active"])

        with self.assertRaises(PermissionDenied):
            self.review()

        self.assertFalse(
            DocumentReview.objects.filter(document=self.document).exists()
        )

    def test_invalid_decision_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.review(decision="PENDING")

        self.document.refresh_from_db()

        self.assertEqual(
            self.document.status,
            HRDocument.Status.PENDING_REVIEW,
        )
        self.assertFalse(
            DocumentReview.objects.filter(document=self.document).exists()
        )

    def test_document_not_pending_review_cannot_be_reviewed(self):
        self.document.status = HRDocument.Status.ARCHIVED
        self.document.save(update_fields=["status"])

        with self.assertRaises(ValidationError):
            self.review()

        self.assertFalse(
            DocumentReview.objects.filter(document=self.document).exists()
        )

    def test_version_from_another_document_is_rejected(self):
        version = DocumentVersion.objects.create(
            document=self.document,
            version_number=1,
            storage_key=(
                f"hr-document-versions/{self.document.pk}/review-v1.pdf"
            ),
            original_filename="review-v1.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            checksum_sha256="a" * 64,
            created_by=self.owner,
        )

        other_document = HRDocument.objects.create(
            employee=self.profile,
            title="Tax Form",
            document_type=HRDocument.DocumentType.TAX_FORM,
            original_filename="tax.pdf",
            storage_key="hr-documents/review/tax.pdf",
            mime_type="application/pdf",
            size_bytes=512,
            uploaded_by=self.owner,
            status=HRDocument.Status.PENDING_REVIEW,
        )

        with self.assertRaises(ValidationError):
            self.service.review_document(
                document_id=other_document.pk,
                actor=self.reviewer,
                decision=DocumentReview.Decision.APPROVED,
                version_id=version.pk,
            )

        self.assertFalse(
            DocumentReview.objects.filter(
                document=other_document
            ).exists()
        )

    def test_version_review_does_not_change_parent_status(self):
        version = DocumentVersion.objects.create(
            document=self.document,
            version_number=1,
            storage_key=(
                f"hr-document-versions/{self.document.pk}/review-version.pdf"
            ),
            original_filename="review-version.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            checksum_sha256="b" * 64,
            created_by=self.owner,
        )

        review = self.service.review_document(
            document_id=self.document.pk,
            actor=self.reviewer,
            decision=DocumentReview.Decision.APPROVED,
            version_id=version.pk,
        )

        self.document.refresh_from_db()

        self.assertEqual(review.version, version)
        self.assertEqual(
            self.document.status,
            HRDocument.Status.PENDING_REVIEW,
        )

    def test_failed_document_update_rolls_back_review(self):
        with patch.object(
            HRDocument,
            "save",
            side_effect=RuntimeError("Simulated database failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.review()

        self.assertFalse(
            DocumentReview.objects.filter(document=self.document).exists()
        )

        self.document.refresh_from_db()
        self.assertEqual(
            self.document.status,
            HRDocument.Status.PENDING_REVIEW,
        )

    def test_review_record_cannot_be_updated_or_deleted(self):
        review = self.review()

        review.comment = "Changed after the decision."

        with self.assertRaises(ValidationError):
            review.save()

        with self.assertRaises(ValidationError):
            review.delete()

class DocumentRetentionPolicyTests(TestCase):
    """Tests for HR document retention policies."""

    def test_create_archive_policy(self):
        policy = DocumentRetentionPolicy.objects.create(
            name="Identity document retention",
            document_type=HRDocument.DocumentType.IDENTITY_DOCUMENT,
            retention_days=365,
            action=DocumentRetentionPolicy.Action.ARCHIVE,
        )

        self.assertEqual(policy.retention_days, 365)
        self.assertEqual(
            policy.action,
            DocumentRetentionPolicy.Action.ARCHIVE,
        )
        self.assertTrue(policy.is_active)

    def test_create_delete_policy(self):
        policy = DocumentRetentionPolicy.objects.create(
            name="Expired tax form retention",
            document_type=HRDocument.DocumentType.TAX_FORM,
            retention_days=730,
            action=DocumentRetentionPolicy.Action.DELETE,
        )

        self.assertEqual(
            policy.action,
            DocumentRetentionPolicy.Action.DELETE,
        )

    def test_default_values(self):
        policy = DocumentRetentionPolicy.objects.create(
            name="Employment contract retention",
            document_type=HRDocument.DocumentType.EMPLOYMENT_CONTRACT,
            retention_days=365,
        )

        self.assertEqual(
            policy.retention_basis,
            DocumentRetentionPolicy.RetentionBasis.UPLOAD_DATE,
        )
        self.assertEqual(
            policy.action,
            DocumentRetentionPolicy.Action.ARCHIVE,
        )
        self.assertTrue(policy.is_active)

    def test_zero_retention_days_is_invalid(self):
        policy = DocumentRetentionPolicy(
            name="Invalid zero retention",
            document_type=HRDocument.DocumentType.OTHER,
            retention_days=0,
        )

        with self.assertRaises(ValidationError):
            policy.full_clean()

    def test_negative_retention_days_is_invalid(self):
        policy = DocumentRetentionPolicy(
            name="Invalid negative retention",
            document_type=HRDocument.DocumentType.OTHER,
            retention_days=-1,
        )

        with self.assertRaises(ValidationError):
            policy.full_clean()

    def test_policy_can_be_deactivated(self):
        policy = DocumentRetentionPolicy.objects.create(
            name="Inactive policy",
            document_type=HRDocument.DocumentType.CERTIFICATION,
            retention_days=365,
        )

        policy.is_active = False
        policy.save(update_fields=["is_active"])

        policy.refresh_from_db()
        self.assertFalse(policy.is_active)

    def test_policy_name_must_be_unique(self):
        DocumentRetentionPolicy.objects.create(
            name="Unique retention policy",
            document_type=HRDocument.DocumentType.OTHER,
            retention_days=365,
        )

        duplicate = DocumentRetentionPolicy(
            name="Unique retention policy",
            document_type=HRDocument.DocumentType.TAX_FORM,
            retention_days=730,
        )

        with self.assertRaises(ValidationError):
            duplicate.full_clean()
    def test_database_rejects_duplicate_active_policy(self):
        from django.db import IntegrityError, transaction

        DocumentRetentionPolicy.objects.create(
            name="Database identity retention",
            document_type=HRDocument.DocumentType.IDENTITY_DOCUMENT,
            retention_days=365,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DocumentRetentionPolicy.objects.bulk_create([
                    DocumentRetentionPolicy(
                        name="Database duplicate identity retention",
                        document_type=HRDocument.DocumentType.IDENTITY_DOCUMENT,
                        retention_days=730,
                    )
                ])

class DocumentExpirationServiceTests(TestCase):
    """Tests for document retention and expiration processing."""

    def setUp(self):
        from datetime import date, datetime, timedelta

        from django.utils import timezone

        from employees.services.document_expiration import (
            DocumentExpirationService,
        )
        self.timezone = timezone
        self.service = DocumentExpirationService
        self.date = date
        self.datetime = datetime
        self.timedelta = timedelta
        self.today = timezone.localdate()

        self.user = User.objects.create_user(
            email="expiration-owner@example.com",
            name="Expiration Owner",
            password="TestPass123!",
        )

        self.department = Department.objects.create(
            name="Expiration Department",
            code="EXP",
        )

        self.position = Position.objects.create(
            title="Expiration Employee",
            department=self.department,
        )

        self.profile = EmployeeProfile.objects.create(
            user=self.user,
            employee_id="EXP-001",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 15),
        )

        self.document = HRDocument.objects.create(
            employee=self.profile,
            title="Expiration Contract",
            document_type=HRDocument.DocumentType.EMPLOYMENT_CONTRACT,
            original_filename="expiration-contract.pdf",
            storage_key="hr-documents/test/expiration-contract.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            uploaded_by=self.user,
        )

        self.policy = DocumentRetentionPolicy.objects.create(
            name="Expiration test policy",
            document_type=HRDocument.DocumentType.EMPLOYMENT_CONTRACT,
            retention_days=30,
            retention_basis=(
                DocumentRetentionPolicy.RetentionBasis.UPLOAD_DATE
            ),
            action=DocumentRetentionPolicy.Action.ARCHIVE,
        )

    def test_calculates_upload_date_deadline(self):
        self.document.uploaded_at = self.timezone.make_aware(
            self.datetime.combine(
                self.today - self.timedelta(days=40),
                self.datetime.min.time(),
            )
        )
        self.document.save(update_fields=["uploaded_at"])

        deadline = self.service.get_retention_deadline(
            self.document,
            self.policy,
        )

        self.assertEqual(
            deadline,
            self.today - self.timedelta(days=10),
        )


    def test_document_is_eligible_after_deadline(self):

        self.document.uploaded_at = self.timezone.make_aware(
            self.datetime.combine(
                self.today - self.timedelta(days=31),
                self.datetime.min.time(),
            )
        )

        self.document.save(update_fields=["uploaded_at"])

        self.assertTrue(
            self.service.is_eligible(
                self.document,
                self.policy,
                today=self.today,
            )
        )

    def test_document_is_not_eligible_before_deadline(self):
        self.document.uploaded_at = self.timezone.make_aware(
            self.datetime.combine(
                self.today - self.timedelta(days=29),
                self.datetime.min.time(),
            )
        )

        self.document.save(update_fields=["uploaded_at"])

        self.assertFalse(
            self.service.is_eligible(
                self.document,
                self.policy,
                today=self.today,
            )
        )

    def test_inactive_policy_is_not_eligible(self):
        self.document.uploaded_at = self.timezone.make_aware(
            self.datetime.combine(
                self.today - self.timedelta(days=60),
                self.datetime.min.time(),
            )
        )
        self.document.save(update_fields=["uploaded_at"])
        self.policy.is_active = False
        self.policy.save(update_fields=["is_active"])

        self.assertFalse(
            self.service.is_eligible(
                self.document,
                self.policy,
                today=self.today,
            )
        )


    def test_missing_reference_date_is_not_eligible(self):
        self.policy.retention_basis = (
            DocumentRetentionPolicy.RetentionBasis.VERIFICATION_DATE
        )
        self.policy.save(update_fields=["retention_basis"])

        self.document.verified_at = None
        self.document.save(update_fields=["verified_at"])

        self.assertIsNone(
            self.service.get_retention_deadline(
                self.document,
                self.policy,
            )
        )
        self.assertFalse(
            self.service.is_eligible(
                self.document,
                self.policy,
                today=self.today,
            )
        )


    def test_processes_eligible_document_by_archiving_it(self):
        self.document.uploaded_at = self.timezone.make_aware(
            self.datetime.combine(
                self.today - self.timedelta(days=31),
                self.datetime.min.time(),
            )
        )
        self.document.save(update_fields=["uploaded_at"])

        result = self.service.process_document(
            self.document,
            self.policy,
            today=self.today,
        )

        self.document.refresh_from_db()

        self.assertEqual(result["action"], "ARCHIVED")
        self.assertEqual(
            self.document.status,
            HRDocument.Status.ARCHIVED,
        )

    def test_dry_run_would_archive_without_modifying_document(self):
        self.document.uploaded_at = self.timezone.make_aware(
            self.datetime.combine(
                self.today - self.timedelta(days=31),
                self.datetime.min.time(),
            )
        )
        self.document.save(update_fields=["uploaded_at"])

        original_status = self.document.status

        result = self.service.process_document(
            self.document,
            self.policy,
            today=self.today,
            dry_run=True,
        )

        self.document.refresh_from_db()

        self.assertEqual(result["action"], "WOULD_ARCHIVE")
        self.assertEqual(
            self.document.status,
            original_status,
        )
        self.assertTrue(
            HRDocument.objects.filter(pk=self.document.pk).exists()
        )

    def test_dry_run_delete_policy_does_not_delete_document(self):
        self.document.uploaded_at = self.timezone.make_aware(
            self.datetime.combine(
                self.today - self.timedelta(days=31),
                self.datetime.min.time(),
            )
        )
        self.document.save(update_fields=["uploaded_at"])

        self.policy.action = DocumentRetentionPolicy.Action.DELETE
        self.policy.save(update_fields=["action"])

        original_status = self.document.status

        result = self.service.process_document(
            self.document,
            self.policy,
            today=self.today,
            dry_run=True,
        )

        self.document.refresh_from_db()

        self.assertEqual(result["action"], "SKIPPED")
        self.assertEqual(
            self.document.status,
            original_status,
        )
        self.assertTrue(
            HRDocument.objects.filter(pk=self.document.pk).exists()
        )

    def test_delete_policy_does_not_physically_delete_document(self):
        self.document.uploaded_at = self.timezone.make_aware(
            self.datetime.combine(
                self.today - self.timedelta(days=31),
                self.datetime.min.time(),
            )
        )
        self.document.save(update_fields=["uploaded_at"])

        self.policy.action = DocumentRetentionPolicy.Action.DELETE
        self.policy.save(update_fields=["action"])

        result = self.service.process_document(
            self.document,
            self.policy,
            today=self.today,
        )

        self.document.refresh_from_db()

        self.assertEqual(result["action"], "SKIPPED")
        self.assertEqual(
            self.document.status,
            HRDocument.Status.PENDING_SCAN,
        )
        self.assertTrue(
            HRDocument.objects.filter(pk=self.document.pk).exists()
        )

    def test_archived_document_is_not_processed_again(self):
        self.document.uploaded_at = self.timezone.make_aware(
            self.datetime.combine(
                self.today - self.timedelta(days=31),
                self.datetime.min.time(),
            )
        )
        self.document.status = HRDocument.Status.ARCHIVED
        self.document.save(update_fields=["uploaded_at", "status"])

        self.assertFalse(
            self.service.is_eligible(
                self.document,
                self.policy,
                today=self.today,
            )
        )

    def test_expiration_date_policy_uses_document_expiration(self):
        self.policy.retention_basis = (
            DocumentRetentionPolicy.RetentionBasis.EXPIRATION_DATE
        )
        self.policy.save(update_fields=["retention_basis"])

        self.document.expires_at = self.today - self.timedelta(days=10)
        self.document.save(update_fields=["expires_at"])

        self.assertEqual(
            self.service.get_retention_deadline(
                self.document,
                self.policy,
            ),
            self.today + self.timedelta(days=20),
        )

    def test_verification_date_policy_uses_verification_timestamp(self):
        self.policy.retention_basis = (
            DocumentRetentionPolicy.RetentionBasis.VERIFICATION_DATE
        )
        self.policy.save(update_fields=["retention_basis"])

        self.document.verified_at = self.timezone.now() - self.timedelta(days=40)
        self.document.save(update_fields=["verified_at"])

        self.assertEqual(
            self.service.get_retention_deadline(
                self.document,
                self.policy,
            ),
            self.today - self.timedelta(days=10),
        )
    def test_document_is_eligible_on_exact_deadline(self):
        self.document.uploaded_at = self.timezone.make_aware(
            self.datetime.combine(
                self.today - self.timedelta(days=30),
                self.datetime.min.time(),
            )
        )
        self.document.save(update_fields=["uploaded_at"])

        deadline = self.service.get_retention_deadline(
            self.document,
            self.policy,
        )

        self.assertEqual(deadline, self.today)
        self.assertTrue(
            self.service.is_eligible(
                self.document,
                self.policy,
                today=self.today,
            )
        )
    def test_process_expired_documents_handles_multiple_documents(self):
        self.document.uploaded_at = self.timezone.make_aware(
            self.datetime.combine(
                self.today - self.timedelta(days=30),
                self.datetime.min.time(),
            )
        )
        self.document.save(update_fields=["uploaded_at"])

        future_document = HRDocument.objects.create(
            employee=self.profile,
            title="Future Retention Contract",
            document_type=HRDocument.DocumentType.EMPLOYMENT_CONTRACT,
            original_filename="future-contract.pdf",
            storage_key="hr-documents/test/future-contract.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            uploaded_by=self.user,
        )
        future_document.uploaded_at = self.timezone.make_aware(
            self.datetime.combine(
                self.today - self.timedelta(days=10),
                self.datetime.min.time(),
            )
        )
        future_document.save(update_fields=["uploaded_at"])

        summary = self.service.process_expired_documents(
            today=self.today,
        )

        self.document.refresh_from_db()
        future_document.refresh_from_db()

        self.assertEqual(summary["processed"], 2)
        self.assertEqual(summary["archived"], 1)
        self.assertEqual(summary["skipped"], 1)
        self.assertEqual(
            self.document.status,
            HRDocument.Status.ARCHIVED,
        )
        self.assertNotEqual(
            future_document.status,
            HRDocument.Status.ARCHIVED,
        )

    def test_inactive_policy_does_not_conflict_with_active_policy(self):
        self.document.uploaded_at = self.timezone.make_aware(
            self.datetime.combine(
                self.today - self.timedelta(days=31),
                self.datetime.min.time(),
            )
        )
        self.document.save(update_fields=["uploaded_at"])

        self.policy.is_active = False
        self.policy.save(update_fields=["is_active"])

        DocumentRetentionPolicy.objects.create(
            name="Active archive employment contract",
            document_type=HRDocument.DocumentType.EMPLOYMENT_CONTRACT,
            retention_days=30,
            retention_basis=(
                DocumentRetentionPolicy.RetentionBasis.UPLOAD_DATE
            ),
            action=DocumentRetentionPolicy.Action.ARCHIVE,
        )

        summary = self.service.process_expired_documents(
            today=self.today,
        )

        self.document.refresh_from_db()

        self.assertEqual(
            self.document.status,
            HRDocument.Status.ARCHIVED,
        )
        self.assertEqual(summary["processed"], 1)
        self.assertEqual(summary["archived"], 1)
        self.assertEqual(summary["skipped"], 0)

    def test_only_one_active_policy_per_document_type(self):
        DocumentRetentionPolicy.objects.create(
            name="Active identity retention",
            document_type=HRDocument.DocumentType.IDENTITY_DOCUMENT,
            retention_days=365,
        )

        duplicate = DocumentRetentionPolicy(
            name="Second active identity retention",
            document_type=HRDocument.DocumentType.IDENTITY_DOCUMENT,
            retention_days=730,
        )

        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_inactive_policy_allows_new_active_policy_for_same_type(self):
        DocumentRetentionPolicy.objects.create(
            name="Inactive identity retention",
            document_type=HRDocument.DocumentType.IDENTITY_DOCUMENT,
            retention_days=365,
            is_active=False,
        )

        active_policy = DocumentRetentionPolicy.objects.create(
            name="New active identity retention",
            document_type=HRDocument.DocumentType.IDENTITY_DOCUMENT,
            retention_days=730,
        )

        self.assertTrue(active_policy.is_active)

    def test_process_expired_documents_dry_run_integration(self):
        """Dry-run detects an expired document without modifying it."""
        from datetime import datetime

        self.document.uploaded_at = self.timezone.make_aware(
            datetime.combine(
                self.today - self.timedelta(days=31),
                datetime.min.time(),
            )
        )
        self.document.save(update_fields=["uploaded_at"])

        result = self.service.process_expired_documents(
            today=self.today,
            dry_run=True,
        )

        self.document.refresh_from_db()

        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["would_archive"], 1)
        self.assertEqual(result["archived"], 0)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(
            result["results"][0]["action"],
            "WOULD_ARCHIVE",
        )
        self.assertEqual(
            self.document.status,
            HRDocument.Status.PENDING_SCAN,
        )
        self.assertTrue(
            HRDocument.objects.filter(pk=self.document.pk).exists()
        )

    def test_process_expired_documents_archives_eligible_document(self):
        """Real processing archives an expired document."""
        from datetime import datetime

        self.document.uploaded_at = self.timezone.make_aware(
            datetime.combine(
                self.today - self.timedelta(days=31),
                datetime.min.time(),
            )
        )
        self.document.save(update_fields=["uploaded_at"])

        result = self.service.process_expired_documents(
            today=self.today,
            dry_run=False,
        )

        self.document.refresh_from_db()

        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["archived"], 1)
        self.assertEqual(result["would_archive"], 0)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(
            result["results"][0]["action"],
            "ARCHIVED",
        )
        self.assertEqual(
            self.document.status,
            HRDocument.Status.ARCHIVED,
        )
        self.assertTrue(
            HRDocument.objects.filter(pk=self.document.pk).exists()
        )

class DocumentAuditServiceTests(TestCase):
    """Tests for sensitive HR document audit logging."""

    def setUp(self):
        from rest_framework.test import APIRequestFactory

        from employees.models import DocumentAccessLog
        from employees.services.document_audit import (
            DocumentAuditService,
        )

        self.DocumentAccessLog = DocumentAccessLog
        self.service = DocumentAuditService
        self.factory = APIRequestFactory()

        self.user = User.objects.create_user(
            email="audit-employee@example.com",
            name="Audit Employee",
            password="StrongPassword123!",
            role="EMPLOYEE",
        )

        department = Department.objects.create(
            name="Audit Test Department",
            code="AUD",
        )
        position = Position.objects.create(
            title="Audit Test Position",
            department=department,
        )
        profile = EmployeeProfile.objects.create(
            user=self.user,
            employee_id="AUD-001",
            department=department,
            position=position,
            hire_date=date(2026, 1, 15),
        )

        self.document = HRDocument.objects.create(
            employee=profile,
            title="Audit Test Contract",
            document_type=HRDocument.DocumentType.EMPLOYMENT_CONTRACT,
            original_filename="audit-contract.pdf",
            storage_key="hr-documents/audit/contract.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            uploaded_by=self.user,
        )

        self.request = self.factory.get(
            "/api/hr-documents/",
            HTTP_USER_AGENT="DocumentAuditServiceTests",
        )
        self.request.user = self.user

    def test_record_creates_document_access_log(self):
        entry = self.service.record(
            request=self.request,
            action=self.DocumentAccessLog.Action.VIEW,
            document=self.document,
            details="Document metadata viewed.",
        )

        self.assertTrue(
            self.DocumentAccessLog.objects.filter(pk=entry.pk).exists()
        )
        self.assertEqual(entry.user, self.user)
        self.assertEqual(entry.document, self.document)
        self.assertEqual(
            entry.action,
            self.DocumentAccessLog.Action.VIEW,
        )
        self.assertEqual(entry.request_path, "/api/hr-documents/")
        self.assertEqual(
            entry.user_agent,
            "DocumentAuditServiceTests",
        )
        self.assertEqual(entry.details, "Document metadata viewed.")

    def test_record_supports_anonymous_request(self):
        request = self.factory.get("/api/hr-documents/")
        request.user = type(
            "AnonymousUser",
            (),
            {"is_authenticated": False},
        )()

        entry = self.service.record(
            request=request,
            action=self.DocumentAccessLog.Action.ACCESS_DENIED,
            document=self.document,
            details="Unauthenticated access attempt.",
        )

        self.assertIsNone(entry.user)
        self.assertEqual(
            entry.action,
            self.DocumentAccessLog.Action.ACCESS_DENIED,
        )

    @patch("employees.services.document_audit.create_security_event")
    def test_record_emits_security_event_when_requested(
        self,
        mock_create_security_event,
    ):
        entry = self.service.record(
            request=self.request,
            action=self.DocumentAccessLog.Action.VERIFY,
            document=self.document,
            details="Document verified.",
            emit_security_event=True,
            event_type="HR_DOCUMENT_VERIFIED",
        )

        self.assertTrue(
            self.DocumentAccessLog.objects.filter(pk=entry.pk).exists()
        )
        mock_create_security_event.assert_called_once_with(
            request=self.request,
            user=self.user,
            event_type="HR_DOCUMENT_VERIFIED",
            details="Document verified.",
        )

    @patch(
        "employees.services.document_audit.create_security_event",
        side_effect=RuntimeError("SIEM unavailable"),
    )
    def test_record_preserves_audit_entry_when_siem_fails(
        self,
        mock_create_security_event,
    ):
        with self.assertLogs(
            "employees.services.document_audit",
            level="ERROR",
        ):
            entry = self.service.record(
                request=self.request,
                action=self.DocumentAccessLog.Action.DOWNLOAD,
                document=self.document,
                details="Document download attempted.",
                emit_security_event=True,
                event_type="HR_DOCUMENT_DOWNLOADED",
            )

        self.assertTrue(
            self.DocumentAccessLog.objects.filter(pk=entry.pk).exists()
        )
        mock_create_security_event.assert_called_once()

class DocumentAccessLogAPITests(TestCase):
    """Tests for the read-only document audit log API."""

    def setUp(self):
        self.client = APIClient()

        self.super_admin = User.objects.create_user(
            email="audit-admin@example.com",
            name="Audit Super Admin",
            password="StrongPassword123!",
            role="SUPER_ADMIN",
            is_staff=True,
            is_superuser=True,
        )
        self.hr_admin = User.objects.create_user(
            email="audit-hradmin@example.com",
            name="Audit HR Admin",
            password="StrongPassword123!",
            role="HR_ADMIN",
        )
        self.hr_manager = User.objects.create_user(
            email="audit-manager@example.com",
            name="Audit HR Manager",
            password="StrongPassword123!",
            role="HR_MANAGER",
        )
        self.employee = User.objects.create_user(
            email="audit-employee@example.com",
            name="Audit Employee",
            password="StrongPassword123!",
            role="EMPLOYEE",
        )
        self.inactive_hr_admin = User.objects.create_user(
            email="audit-inactive@example.com",
            name="Inactive Audit HR Admin",
            password="StrongPassword123!",
            role="HR_ADMIN",
            is_active=False,
        )

        self.department = Department.objects.create(
            name="Audit Test Department",
            code="AUD",
        )
        self.position = Position.objects.create(
            title="Audit Test Position",
            department=self.department,
        )
        self.profile = EmployeeProfile.objects.create(
            user=self.employee,
            employee_id="AUD-001",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 15),
        )

        self.manager_profile = EmployeeProfile.objects.create(
            user=self.hr_manager,
            employee_id="AUD-MGR-001",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 15),
        )

        self.document = HRDocument.objects.create(
            employee=self.profile,
            title="Audit Test Contract",
            document_type=HRDocument.DocumentType.EMPLOYMENT_CONTRACT,
            original_filename="audit-contract.pdf",
            storage_key="hr-documents/audit-tests/audit-contract.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            uploaded_by=self.hr_admin,
        )

        self.url = "/api/v1/employees/document-access-logs/"

        self.view_log = DocumentAccessLog.objects.create(
            document=self.document,
            user=self.employee,
            action=DocumentAccessLog.Action.VIEW,
            ip_address="192.0.2.10",
            user_agent="DocumentAccessLogAPITests",
            request_path="/api/v1/employees/hr-documents/",
            details="Audit test document viewed.",
        )
        self.download_log = DocumentAccessLog.objects.create(
            document=self.document,
            user=self.hr_admin,
            action=DocumentAccessLog.Action.DOWNLOAD,
            ip_address="192.0.2.11",
            user_agent="DocumentAccessLogAPITests",
            request_path="/api/v1/employees/hr-documents/download/",
            details="Audit test document downloaded.",
        )
        self.verify_log = DocumentAccessLog.objects.create(
            document=self.document,
            user=self.hr_manager,
            action=DocumentAccessLog.Action.VERIFY,
            ip_address="192.0.2.12",
            user_agent="DocumentAccessLogAPITests",
            request_path="/api/v1/employees/hr-documents/verify/",
            details="Audit test document verified.",
        )

        self.other_department = Department.objects.create(
            name="Other Audit Department",
            code="OTH",
        )
        self.other_position = Position.objects.create(
            title="Other Audit Position",
            department=self.other_department,
        )
        self.other_employee = User.objects.create_user(
            email="audit-other@example.com",
            name="Other Audit Employee",
            password="StrongPassword123!",
            role="EMPLOYEE",
        )
        self.other_profile = EmployeeProfile.objects.create(
            user=self.other_employee,
            employee_id="OTH-001",
            department=self.other_department,
            position=self.other_position,
            hire_date=date(2026, 1, 15),
        )
        self.other_document = HRDocument.objects.create(
            employee=self.other_profile,
            title="Other Department Contract",
            document_type=HRDocument.DocumentType.EMPLOYMENT_CONTRACT,
            original_filename="other-contract.pdf",
            storage_key="hr-documents/audit-tests/other-contract.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            uploaded_by=self.hr_admin,
        )
        self.other_log = DocumentAccessLog.objects.create(
            document=self.other_document,
            user=self.other_employee,
            action=DocumentAccessLog.Action.VIEW,
            ip_address="192.0.2.20",
            user_agent="DocumentAccessLogAPITests",
            request_path="/api/v1/employees/hr-documents/",
            details="Other department document viewed.",
        )

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def test_authorized_hr_roles_can_list_audit_logs(self):
        for user in (
            self.super_admin,
            self.hr_admin,
            self.hr_manager,
        ):
            with self.subTest(role=user.role):
                self.client.force_authenticate(user=user)
                response = self.client.get(self.url)
                self.assertEqual(
                    response.status_code,
                    status.HTTP_200_OK,
                )
                self.assertGreaterEqual(response.data["count"], 3)

    def test_hr_admin_and_super_admin_retain_global_access(self):
        for user in (self.hr_admin, self.super_admin):
            with self.subTest(role=user.role):
                self.authenticate(user)

                # Verify access to the other department's audit log.
                list_response = self.client.get(self.url)

                self.assertEqual(
                    list_response.status_code,
                    status.HTTP_200_OK,
                )
                self.assertIn(
                    self.other_log.pk,
                    {
                        item["id"]
                        for item in list_response.data["results"]
                    },
                )

                # Verify direct retrieval as well.
                detail_response = self.client.get(
                    f"{self.url}{self.other_log.pk}/"
                )

                self.assertEqual(
                    detail_response.status_code,
                    status.HTTP_200_OK,
                )
                self.assertEqual(
                    detail_response.data["id"],
                    self.other_log.pk,
                )

    def test_authorized_hr_role_can_retrieve_audit_log(self):
        self.authenticate(self.hr_admin)

        response = self.client.get(
            f"{self.url}{self.view_log.pk}/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.view_log.pk)
        self.assertEqual(response.data["action"], "VIEW")

    def test_employee_is_denied_access(self):
        self.authenticate(self.employee)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_inactive_hr_account_is_denied_access(self):
        self.authenticate(self.inactive_hr_admin)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_audit_log_api_is_read_only(self):
        self.authenticate(self.hr_admin)

        response = self.client.post(
            self.url,
            {
                "action": "VIEW",
                "details": "Attempt to create a log through the API.",
            },
            format="json",
        )

        self.assertIn(
            response.status_code,
            (
                status.HTTP_403_FORBIDDEN,
                status.HTTP_405_METHOD_NOT_ALLOWED,
            ),
        )

    def test_filter_by_action(self):
        self.authenticate(self.hr_admin)

        response = self.client.get(
            self.url,
            {"action": "DOWNLOAD"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["action"],
            "DOWNLOAD",
        )

    def test_filter_by_user(self):
        self.authenticate(self.hr_admin)

        response = self.client.get(
            self.url,
            {"user": self.employee.pk},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["user"],
            self.employee.pk,
        )

    def test_filter_by_document(self):
        self.authenticate(self.hr_admin)

        response = self.client.get(
            self.url,
            {"document": str(self.document.pk)},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)

    def test_filter_by_date_range(self):
        self.authenticate(self.hr_admin)

        response = self.client.get(
            self.url,
            {
                "created_after": "2020-01-01T00:00:00Z",
                "created_before": "2035-01-01T00:00:00Z",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 4)

    def test_search_by_details(self):
        self.authenticate(self.hr_admin)

        response = self.client.get(
            self.url,
            {"search": "document downloaded"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["action"],
            "DOWNLOAD",
        )

    def test_search_by_user_email(self):
        self.authenticate(self.hr_admin)

        response = self.client.get(
            self.url,
            {"search": "audit-employee@example.com"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_ordering_by_action(self):
        self.authenticate(self.hr_admin)

        response = self.client.get(
            self.url,
            {"ordering": "action"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        actions = [
            item["action"]
            for item in response.data["results"]
        ]
        self.assertEqual(actions, sorted(actions))

    def test_pagination_defaults_to_twenty_results(self):
        self.authenticate(self.hr_admin)

        for index in range(22):
            DocumentAccessLog.objects.create(
                document=self.document,
                user=self.employee,
                action=DocumentAccessLog.Action.VIEW,
                request_path=f"/audit-pagination/{index}/",
                details=f"Pagination test entry {index}.",
            )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 26)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertIsNotNone(response.data["next"])

    def test_pagination_respects_requested_page_size(self):
        self.authenticate(self.hr_admin)

        response = self.client.get(
            self.url,
            {"page_size": 2},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

    def test_pagination_caps_page_size_at_one_hundred(self):
        self.authenticate(self.hr_admin)

        for index in range(105):
            DocumentAccessLog.objects.create(
                document=self.document,
                user=self.employee,
                action=DocumentAccessLog.Action.VIEW,
                request_path=f"/audit-page-cap/{index}/",
                details=f"Page cap test entry {index}.",
            )

        response = self.client.get(
            self.url,
            {"page_size": 500},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 100)
        self.assertIsNotNone(response.data["next"])

    def test_hr_manager_list_is_limited_to_own_department(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)

        returned_ids = {
            item["id"]
            for item in response.data["results"]
        }

        self.assertEqual(
            returned_ids,
            {
                self.view_log.pk,
                self.download_log.pk,
                self.verify_log.pk,
            },
        )
        self.assertNotIn(self.other_log.pk, returned_ids)

    def test_hr_manager_cannot_retrieve_other_department_log(self):
        self.authenticate(self.hr_manager)

        response = self.client.get(
            f"{self.url}{self.other_log.pk}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_hr_manager_without_profile_is_denied(self):
        manager_without_profile = User.objects.create_user(
            email="audit-no-profile@example.com",
            name="Manager Without Profile",
            password="StrongPassword123!",
            role="HR_MANAGER",
        )

        self.authenticate(manager_without_profile)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

class OnboardingMetricsServiceTests(TestCase):
    """Tests for enterprise onboarding dashboard metrics."""

    def setUp(self):
        from employees.models import (
            OnboardingJourney,
            OnboardingTask,
            OnboardingTemplate,
            OnboardingPhase,
            OnboardingActivityTemplate,
        )
        from employees.services.dashboard.onboarding_metrics import (
            OnboardingMetricsService,
        )

        self.OnboardingJourney = OnboardingJourney
        self.OnboardingTask = OnboardingTask
        self.OnboardingMetricsService = OnboardingMetricsService

        self.admin = User.objects.create_user(
            email="metrics-admin@example.com",
            name="Metrics Admin",
            password="TestPassword123!",
            role="HR_ADMIN",
            is_active=True,
        )

        self.employee_user = User.objects.create_user(
            email="metrics-employee@example.com",
            name="Metrics Employee",
            password="TestPassword123!",
            is_active=True,
        )

        self.department = Department.objects.create(
            name="Metrics Department",
            code="METRICS",
        )

        self.position = Position.objects.create(
            title="Metrics Specialist",
            department=self.department,
        )

        self.employee = EmployeeProfile.objects.create(
            user=self.employee_user,
            employee_id="METRICS-001",
            department=self.department,
            position=self.position,
            hire_date=date.today(),
        )

        template = OnboardingTemplate.objects.create(
            name="Metrics Template",
            description="Dashboard metrics test",
            version=1,
            created_by=self.admin,
        )

        phase = OnboardingPhase.objects.create(
            template=template,
            name="First phase",
            description="Metrics phase",
            order=1,
        )

        activity = OnboardingActivityTemplate.objects.create(
            phase=phase,
            name="Metrics activity",
            description="Metrics task",
            order=1,
            is_required=True,
            default_due_days=3,
        )

        from employees.services.onboarding import OnboardingService

        OnboardingService.publish_template(template.pk)

        self.journey = OnboardingService.create_journey(
            employee_id=self.employee.pk,
            template_id=template.pk,
            created_by=self.admin,
        )

        self.activity = activity

    def create_task(
        self,
        *,
        title,
        status="PENDING",
        priority="MEDIUM",
        due_date=None,
    ):
        return self.OnboardingTask.objects.create(
            journey=self.journey,
            activity_template=self.activity,
            title=title,
            status=status,
            priority=priority,
            due_date=due_date,
        )

    def test_dashboard_returns_journey_and_task_metrics(self):
        result = self.OnboardingMetricsService.get_dashboard()

        self.assertEqual(result["journeys"]["total"], 1)
        self.assertEqual(result["journeys"]["pending"], 1)
        self.assertEqual(result["tasks"]["total"], 1)
        self.assertEqual(result["tasks"]["pending"], 1)

    def test_overdue_tasks_are_counted(self):
        self.create_task(
            title="Overdue task",
            due_date=date(2020, 1, 1),
        )

        result = self.OnboardingMetricsService.get_dashboard(
            as_of=date.today(),
        )

        self.assertEqual(result["tasks"]["overdue"], 1)

    def test_completed_tasks_are_excluded_from_overdue_count(self):
        self.create_task(
            title="Completed task",
            status="COMPLETED",
            due_date=date(2020, 1, 1),
        )

        result = self.OnboardingMetricsService.get_dashboard(
            as_of=date.today(),
        )

        self.assertEqual(result["tasks"]["overdue"], 0)

    def test_progress_percentage_excludes_cancelled_tasks(self):
        self.create_task(
            title="Completed task",
            status="COMPLETED",
        )
        self.create_task(
            title="Cancelled task",
            status="CANCELLED",
        )
        self.create_task(
            title="Pending task",
            status="PENDING",
        )

        result = self.OnboardingMetricsService.get_dashboard()

        self.assertEqual(
            result["progress"]["percentage"],
            33.3,
        )


    def test_department_filter_isolates_all_onboarding_metrics(self):
        from employees.services.onboarding import OnboardingService

        as_of = date(2026, 11, 9)

        # Add tasks to the selected department's journey.
        self.create_task(
            title="Completed selected task",
            status="COMPLETED",
            priority="HIGH",
        )
        self.create_task(
            title="Cancelled selected task",
            status="CANCELLED",
            priority="LOW",
        )
        self.create_task(
            title="Overdue blocked selected task",
            status="BLOCKED",
            priority="URGENT",
            due_date=date(2026, 11, 1),
        )

        # Create a second department and employee.
        other_department = Department.objects.create(
            name="Other Onboarding Department",
            code="OTHER-ONBOARDING",
        )
        other_position = Position.objects.create(
            title="Other Onboarding Specialist",
            department=other_department,
        )
        other_user = User.objects.create_user(
            email="other-onboarding-employee@example.com",
            name="Other Onboarding Employee",
            password="TestPassword123!",
            role="EMPLOYEE",
            is_active=True,
        )
        other_employee = EmployeeProfile.objects.create(
            user=other_user,
            employee_id="OTHER-ONBOARD-001",
            department=other_department,
            position=other_position,
            hire_date=as_of,
        )

        # Create a real journey through the onboarding service.
        other_journey = OnboardingService.create_journey(
            employee_id=other_employee.pk,
            template_id=self.journey.template_id,
            created_by=self.admin,
        )

        other_journey.status = self.OnboardingJourney.Status.IN_PROGRESS
        other_journey.save(update_fields=["status"])

        # Add an overdue, urgent task to the other department.
        other_task = other_journey.tasks.first()
        other_task.status = self.OnboardingTask.Status.BLOCKED
        other_task.priority = self.OnboardingTask.Priority.URGENT
        other_task.due_date = date(2026, 11, 1)
        other_task.save(
            update_fields=["status", "priority", "due_date"]
        )

        result = self.OnboardingMetricsService.get_dashboard(
            department_id=self.department.pk,
            as_of=as_of,
        )

        # Only the selected department's journey is counted.
        self.assertEqual(result["journeys"]["total"], 1)
        self.assertEqual(result["journeys"]["pending"], 1)
        self.assertEqual(result["journeys"]["in_progress"], 0)
        self.assertEqual(result["journeys"]["suspended"], 0)
        self.assertEqual(result["journeys"]["completed"], 0)
        self.assertEqual(result["journeys"]["cancelled"], 0)

        # Only tasks belonging to the selected journey are counted.
        self.assertEqual(result["tasks"]["total"], 4)
        self.assertEqual(result["tasks"]["pending"], 1)
        self.assertEqual(result["tasks"]["completed"], 1)
        self.assertEqual(result["tasks"]["cancelled"], 1)
        self.assertEqual(result["tasks"]["blocked"], 1)
        self.assertEqual(result["tasks"]["overdue"], 1)

        # Priority indicators must also exclude the other department.
        self.assertEqual(result["tasks"]["low_priority"], 1)
        self.assertEqual(result["tasks"]["medium_priority"], 1)
        self.assertEqual(result["tasks"]["high_priority"], 1)
        self.assertEqual(result["tasks"]["urgent_priority"], 1)

        # Cancelled tasks are excluded from progress calculations.
        self.assertEqual(
            result["progress"]["total_eligible_tasks"],
            3,
        )
        self.assertEqual(result["progress"]["completed_tasks"], 1)
        self.assertEqual(result["progress"]["percentage"], 33.3)


    def test_department_filter_limits_journeys(self):
        result = self.OnboardingMetricsService.get_dashboard(
            department_id=self.department.pk,
        )

        self.assertEqual(result["journeys"]["total"], 1)

    def test_priority_metrics_are_counted(self):
        self.create_task(
            title="Urgent task",
            priority="URGENT",
        )
        self.create_task(
            title="High priority task",
            priority="HIGH",
        )

        result = self.OnboardingMetricsService.get_dashboard()

        self.assertEqual(result["tasks"]["urgent_priority"], 1)
        self.assertEqual(result["tasks"]["high_priority"], 1)

class OperationsMetricsServiceTests(TestCase):
    """Tests for workflow and notification dashboard metrics."""

    def setUp(self):
        from employees.models import WorkflowExecutionLog
        from employees.services.dashboard.operations_metrics import (
            OperationsMetricsService,
        )

        self.WorkflowExecutionLog = WorkflowExecutionLog
        self.OperationsMetricsService = OperationsMetricsService

        self.admin = User.objects.create_user(
            email="operations-admin@example.com",
            name="Operations Admin",
            password="TestPassword123!",
            role="HR_ADMIN",
            is_active=True,
        )

        self.department = Department.objects.create(
            name="Operations Department",
            code="OPERATIONS",
        )

        self.employee_user = User.objects.create_user(
            email="operations-employee@example.com",
            name="Operations Employee",
            password="TestPassword123!",
            is_active=True,
        )

        self.position = Position.objects.create(
            title="Operations Specialist",
            department=self.department,
        )

        self.employee = EmployeeProfile.objects.create(
            user=self.employee_user,
            employee_id="OPERATIONS-001",
            department=self.department,
            position=self.position,
            hire_date=date.today(),
        )

    def create_log(
        self,
        *,
        event_type,
        outcome="SUCCESS",
        details=None,
        journey=None,
    ):
        return self.WorkflowExecutionLog.objects.create(
            journey=journey,
            actor=self.admin,
            event_type=event_type,
            outcome=outcome,
            details=details or {},
        )

    def test_dashboard_returns_workflow_outcome_metrics(self):
        self.create_log(event_type="TASK_ASSIGNED")
        self.create_log(event_type="TASK_STATUS_CHANGED")
        self.create_log(
            event_type="NOTIFICATION_FAILED",
            outcome="FAILURE",
            details={"notification_type": "TASK_ASSIGNED"},
        )
        self.create_log(
            event_type="TASK_STATUS_CHANGED",
            outcome="DENIED",
        )

        result = self.OperationsMetricsService.get_dashboard()

        self.assertEqual(result["workflows"]["total"], 4)
        self.assertEqual(result["workflows"]["success"], 2)
        self.assertEqual(result["workflows"]["failure"], 1)
        self.assertEqual(result["workflows"]["denied"], 1)

    def test_notification_failures_are_counted_separately(self):
        self.create_log(
            event_type="NOTIFICATION_FAILED",
            outcome="FAILURE",
            details={"notification_type": "TASK_ASSIGNED"},
        )
        self.create_log(
            event_type="NOTIFICATION_FAILED",
            outcome="FAILURE",
            details={"notification_type": "TASK_COMPLETED"},
        )
        self.create_log(
            event_type="TASK_STATUS_CHANGED",
            outcome="FAILURE",
        )

        result = self.OperationsMetricsService.get_dashboard()

        self.assertEqual(result["notifications"]["failed"], 2)
        self.assertEqual(
            sum(item["count"] for item in result["notifications"]["by_type"]),
            2,
        )

    def test_event_distribution_groups_events_by_type(self):
        self.create_log(event_type="TASK_ASSIGNED")
        self.create_log(event_type="TASK_ASSIGNED")
        self.create_log(event_type="TASK_STATUS_CHANGED")

        result = self.OperationsMetricsService.get_dashboard()

        distribution = {
            item["event_type"]: item["count"]
            for item in result["events"]["distribution"]
        }

        self.assertEqual(distribution["TASK_ASSIGNED"], 2)
        self.assertEqual(distribution["TASK_STATUS_CHANGED"], 1)

    def test_daily_activity_respects_requested_period(self):
        from datetime import timedelta

        today = date.today()
        yesterday = today - timedelta(days=1)
        outside_period = today - timedelta(days=10)

        self.create_log(event_type="TASK_ASSIGNED")
        self.WorkflowExecutionLog.objects.filter(
            event_type="TASK_ASSIGNED"
        ).update(
            created_at=timezone.make_aware(
                datetime.combine(yesterday, datetime.min.time())
            )
        )

        self.create_log(event_type="TASK_STATUS_CHANGED")
        self.WorkflowExecutionLog.objects.filter(
            event_type="TASK_STATUS_CHANGED"
        ).update(
            created_at=timezone.make_aware(
                datetime.combine(outside_period, datetime.min.time())
            )
        )

        result = self.OperationsMetricsService.get_dashboard(
            as_of=today,
            days=7,
        )

        self.assertEqual(
            sum(item["count"] for item in result["daily_activity"]),
            1,
        )


    def test_department_filter_isolates_all_operation_metrics(self):
        from employees.models import (
            OnboardingJourney,
            OnboardingTemplate,
        )

        # Create a second department and its employee.
        other_department = Department.objects.create(
            name="Other Operations Department",
            code="OTHER_OPERATIONS",
        )

        other_position = Position.objects.create(
            title="Other Operations Specialist",
            department=other_department,
        )

        other_user = User.objects.create_user(
            email="other-operations-employee@example.com",
            name="Other Operations Employee",
            password="TestPassword123!",
            is_active=True,
        )

        other_employee = EmployeeProfile.objects.create(
            user=other_user,
            employee_id="OTHER-OPERATIONS-001",
            department=other_department,
            position=other_position,
            hire_date=date.today(),
        )

        # One template can be reused by both onboarding journeys.
        template = OnboardingTemplate.objects.create(
            name="Operations Isolation Test Template",
            created_by=self.admin,
        )

        # Create one journey per department.
        own_journey = OnboardingJourney.objects.create(
            employee=self.employee,
            template=template,
            template_version=template.version,
            created_by=self.admin,
        )

        other_journey = OnboardingJourney.objects.create(
            employee=other_employee,
            template=template,
            template_version=template.version,
            created_by=self.admin,
        )

        # Selected department: three workflow events.
        self.create_log(
            journey=own_journey,
            event_type="TASK_ASSIGNED",
            outcome="SUCCESS",
        )

        self.create_log(
            journey=own_journey,
            event_type="NOTIFICATION_FAILED",
            outcome="FAILURE",
            details={"notification_type": "TASK_ASSIGNED"},
        )

        self.create_log(
            journey=own_journey,
            event_type="TASK_STATUS_CHANGED",
            outcome="DENIED",
        )

        # Other department: these events must not appear.
        self.create_log(
            journey=other_journey,
            event_type="TASK_ASSIGNED",
            outcome="SUCCESS",
        )

        self.create_log(
            journey=other_journey,
            event_type="NOTIFICATION_FAILED",
            outcome="FAILURE",
            details={"notification_type": "TASK_COMPLETED"},
        )

        self.create_log(
            journey=other_journey,
            event_type="TASK_STATUS_CHANGED",
            outcome="DENIED",
        )

        # An event without a journey must also be excluded.
        self.create_log(
            journey=None,
            event_type="UNLINKED_EVENT",
            outcome="SUCCESS",
        )

        result = self.OperationsMetricsService.get_dashboard(
            department_id=self.department.pk,
            as_of=timezone.localdate(),
            days=7,
        )

        # Workflow outcome isolation.
        self.assertEqual(result["workflows"]["total"], 3)
        self.assertEqual(result["workflows"]["success"], 1)
        self.assertEqual(result["workflows"]["failure"], 1)
        self.assertEqual(result["workflows"]["denied"], 1)

        # Notification isolation.
        self.assertEqual(result["notifications"]["failed"], 1)
        self.assertEqual(
            result["notifications"]["by_type"],
            [
                {
                    "details__notification_type": "TASK_ASSIGNED",
                    "count": 1,
                }
            ],
        )

        # Event distribution isolation.
        distribution = {
            item["event_type"]: item["count"]
            for item in result["events"]["distribution"]
        }

        self.assertEqual(
            distribution,
            {
                "NOTIFICATION_FAILED": 1,
                "TASK_ASSIGNED": 1,
                "TASK_STATUS_CHANGED": 1,
            },
        )

        self.assertNotIn("UNLINKED_EVENT", distribution)

        # Daily activity must contain only the three selected events.
        self.assertEqual(
            sum(item["count"] for item in result["daily_activity"]),
            3,
        )

    def test_invalid_period_is_rejected(self):
        with self.assertRaises(ValueError):
            self.OperationsMetricsService.get_dashboard(days=0)

class WorkforceMetricsServiceTests(TestCase):
    """Tests for workforce dashboard metrics."""

    def setUp(self):
        from employees.services.dashboard.workforce_metrics import (
            WorkforceMetricsService,
        )

        self.WorkforceMetricsService = WorkforceMetricsService

        self.department = Department.objects.create(
            name="Workforce Department",
            code="WORKFORCE",
        )

        self.other_department = Department.objects.create(
            name="Other Department",
            code="OTHER",
        )

        self.position = Position.objects.create(
            title="HR Specialist",
            department=self.department,
        )

        self.other_position = Position.objects.create(
            title="HR Manager",
            department=self.department,
        )

        self.admin = User.objects.create_user(
            email="workforce-admin@example.com",
            name="Workforce Admin",
            password="TestPassword123!",
            role="HR_ADMIN",
            is_active=True,
        )

        self.employee_user = User.objects.create_user(
            email="workforce-employee@example.com",
            name="Workforce Employee",
            password="TestPassword123!",
            role="EMPLOYEE",
            is_active=True,
        )

        self.inactive_user = User.objects.create_user(
            email="workforce-inactive@example.com",
            name="Inactive Employee",
            password="TestPassword123!",
            role="EMPLOYEE",
            is_active=False,
        )

        self.employee = EmployeeProfile.objects.create(
            user=self.employee_user,
            employee_id="WORK-001",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 10, 5),
        )

        self.inactive_employee = EmployeeProfile.objects.create(
            user=self.inactive_user,
            employee_id="WORK-002",
            department=self.department,
            position=self.other_position,
            hire_date=date(2026, 9, 15),
        )

    def test_dashboard_returns_total_headcount(self):
        result = self.WorkforceMetricsService.get_dashboard()

        self.assertEqual(result["headcount"]["total"], 2)

    def test_dashboard_counts_active_and_inactive_accounts(self):
        result = self.WorkforceMetricsService.get_dashboard()

        self.assertEqual(
            result["headcount"]["active_accounts"],
            1,
        )
        self.assertEqual(
            result["headcount"]["inactive_accounts"],
            1,
        )

    def test_dashboard_returns_department_distribution(self):
        result = self.WorkforceMetricsService.get_dashboard()

        self.assertEqual(result["departments"]["total"], 1)
        self.assertEqual(
            result["departments"]["distribution"][0][
                "employee_count"
            ],
            2,
        )

    def test_dashboard_returns_position_distribution(self):
        result = self.WorkforceMetricsService.get_dashboard()

        self.assertEqual(result["positions"]["total"], 2)

    def test_dashboard_returns_role_distribution(self):
        result = self.WorkforceMetricsService.get_dashboard()

        roles = {
            item["user__role"]: item["employee_count"]
            for item in result["roles"]
        }

        self.assertEqual(roles["EMPLOYEE"], 2)

    def test_dashboard_counts_monthly_and_yearly_hires(self):
        result = self.WorkforceMetricsService.get_dashboard(
            as_of=date(2026, 10, 29),
        )

        self.assertEqual(result["hires"]["this_month"], 1)
        self.assertEqual(result["hires"]["this_year"], 2)

    def test_dashboard_department_filter(self):
        result = self.WorkforceMetricsService.get_dashboard(
            department_id=self.department.pk,
        )

        self.assertEqual(result["headcount"]["total"], 2)

    def test_dashboard_excludes_employees_from_other_departments(self):
        result = self.WorkforceMetricsService.get_dashboard(
            department_id=self.other_department.pk,
        )

        self.assertEqual(result["headcount"]["total"], 0)
        self.assertEqual(result["departments"]["total"], 0)


    def test_department_filter_isolates_all_workforce_metrics(self):
        # Create an employee in the other department.
        other_position = Position.objects.create(
            title="Other Department Specialist",
            department=self.other_department,
        )

        other_user = User.objects.create_user(
            email="other-workforce-employee@example.com",
            name="Other Workforce Employee",
            password="TestPassword123!",
            role="EMPLOYEE",
            is_active=True,
        )

        EmployeeProfile.objects.create(
            user=other_user,
            employee_id="OTHER-WORK-001",
            department=self.other_department,
            position=other_position,
            hire_date=date(2026, 10, 20),
        )

        # Add a second active employee to the selected department.
        second_user = User.objects.create_user(
            email="second-workforce-employee@example.com",
            name="Second Workforce Employee",
            password="TestPassword123!",
            role="EMPLOYEE",
            is_active=True,
        )

        EmployeeProfile.objects.create(
            user=second_user,
            employee_id="WORK-003",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 10, 15),
        )

        result = self.WorkforceMetricsService.get_dashboard(
            department_id=self.department.pk,
            as_of=date(2026, 10, 29),
        )

        # Headcount and account status.
        self.assertEqual(result["headcount"]["total"], 3)
        self.assertEqual(result["headcount"]["active_accounts"], 2)
        self.assertEqual(result["headcount"]["inactive_accounts"], 1)

        # Only the selected department is represented.
        self.assertEqual(result["departments"]["total"], 1)
        self.assertEqual(
            len(result["departments"]["distribution"]),
            1,
        )
        self.assertEqual(
            result["departments"]["distribution"][0]["department_id"],
            self.department.pk,
        )
        self.assertEqual(
            result["departments"]["distribution"][0]["employee_count"],
            3,
        )

        # Only positions from the selected department are represented.
        self.assertEqual(result["positions"]["total"], 2)

        position_department_names = {
            item["department__name"]
            for item in result["positions"]["distribution"]
        }
        self.assertEqual(
            position_department_names,
            {self.department.name},
        )

        # All employees in this fixture have the EMPLOYEE role.
        self.assertEqual(
            result["roles"],
            [
                {
                    "user__role": "EMPLOYEE",
                    "employee_count": 3,
                }
            ],
        )

        # Hiring metrics must exclude the other department.
        self.assertEqual(result["hires"]["this_month"], 2)
        self.assertEqual(result["hires"]["this_year"], 3)


    def test_dashboard_excludes_users_without_employee_profiles(self):
        result = self.WorkforceMetricsService.get_dashboard()

        self.assertEqual(result["headcount"]["total"], 2)

class ComplianceMetricsServiceTests(TestCase):
    """Tests for compliance dashboard metrics."""

    def setUp(self):
        from employees.services.dashboard.compliance_metrics import (
            ComplianceMetricsService,
        )

        self.ComplianceMetricsService = ComplianceMetricsService

        self.department = Department.objects.create(
            name="Compliance Metrics Department",
            code="COMPLIANCE-METRICS",
        )

        self.position = Position.objects.create(
            title="Compliance Specialist",
            department=self.department,
        )

        self.admin = User.objects.create_user(
            email="compliance-admin@example.com",
            name="Compliance Admin",
            password="TestPassword123!",
            role="HR_ADMIN",
        )

    def create_employee(self, employee_id, email, **fields):
        user = User.objects.create_user(
            email=email,
            name=f"Employee {employee_id}",
            password="TestPassword123!",
            role="EMPLOYEE",
        )

        return EmployeeProfile.objects.create(
            user=user,
            employee_id=employee_id,
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 15),
            **fields,
        )

    def test_dashboard_returns_zero_metrics_without_employees(self):
        result = self.ComplianceMetricsService.get_dashboard()

        self.assertEqual(result["headcount"], 0)
        self.assertEqual(
            result["profiles"]["completion_rate"],
            0.0,
        )
        self.assertEqual(
            result["documents"]["compliance_rate"],
            0.0,
        )

    def test_dashboard_calculates_profile_completion_rate(self):
        self.create_employee(
            "COMP-001",
            "complete@example.com",
            phone="4015550100",
            address="123 Main Street",
        )

        self.create_employee(
            "COMP-002",
            "incomplete@example.com",
            phone="",
            address="",
        )

        result = self.ComplianceMetricsService.get_dashboard()

        self.assertEqual(result["headcount"], 2)
        self.assertEqual(result["profiles"]["complete"], 1)
        self.assertEqual(result["profiles"]["incomplete"], 1)
        self.assertEqual(
            result["profiles"]["completion_rate"],
            50.0,
        )

    def test_dashboard_calculates_document_compliance_rate(self):
        self.create_employee(
            "COMP-003",
            "documents-missing@example.com",
        )

        result = self.ComplianceMetricsService.get_dashboard()

        self.assertEqual(
            result["documents"]["compliant_employees"],
            0,
        )
        self.assertEqual(
            result["documents"]["employees_missing_required_documents"],
            1,
        )
        self.assertEqual(
            result["documents"]["compliance_rate"],
            0.0,
        )

    def test_dashboard_returns_compliance_details(self):
        self.create_employee(
            "COMP-004",
            "details@example.com",
        )

        result = self.ComplianceMetricsService.get_dashboard()

        self.assertIn(
            "missing_documents_details",
            result["documents"],
        )
        self.assertIn(
            "expired_details",
            result["documents"],
        )
        self.assertIn(
            "expiring_soon_details",
            result["documents"],
        )


    def test_department_filter_isolates_all_compliance_metrics(self):
        from employees.models import HRDocument

        as_of = date(2026, 11, 9)

        # Create a second department and its employee.
        other_department = Department.objects.create(
            name="Other Compliance Department",
            code="OTHER-COMPLIANCE",
        )
        other_position = Position.objects.create(
            title="Other Compliance Specialist",
            department=other_department,
        )

        employee_a = self.create_employee(
            "COMP-ISO-001",
            "compliance-isolation-a@example.com",
            phone="",
            address="",
        )

        other_user = User.objects.create_user(
            email="compliance-isolation-b@example.com",
            name="Other Compliance Employee",
            password="TestPassword123!",
            role="EMPLOYEE",
            is_active=True,
        )

        employee_b = EmployeeProfile.objects.create(
            user=other_user,
            employee_id="COMP-ISO-002",
            department=other_department,
            position=other_position,
            hire_date=date(2026, 1, 15),
            phone="4015550199",
            address="456 Other Street",
        )

        def create_document(employee, document_type, filename, expires_at):
            return HRDocument.objects.create(
                employee=employee,
                title=filename,
                document_type=document_type,
                original_filename=filename,
                storage_key=f"hr-documents/compliance-isolation/{filename}",
                mime_type="application/pdf",
                size_bytes=1024,
                uploaded_by=self.admin,
                status=HRDocument.Status.VERIFIED,
                expires_at=expires_at,
            )

        # Department A: one expired and one soon-expiring document.
        create_document(
            employee_a,
            HRDocument.DocumentType.CERTIFICATION,
            "a-expired.pdf",
            date(2026, 11, 1),
        )
        create_document(
            employee_a,
            HRDocument.DocumentType.CERTIFICATION,
            "a-expiring-soon.pdf",
            date(2026, 11, 20),
        )

        # Department B: valid required documents and its own
        # expired and soon-expiring documents.
        for document_type, filename in [
            (HRDocument.DocumentType.IDENTITY_DOCUMENT, "b-identity.pdf"),
            (HRDocument.DocumentType.EMPLOYMENT_CONTRACT, "b-contract.pdf"),
            (HRDocument.DocumentType.TAX_FORM, "b-tax.pdf"),
        ]:
            create_document(
                employee_b,
                document_type,
                filename,
                None,
            )

        create_document(
            employee_b,
            HRDocument.DocumentType.CERTIFICATION,
            "b-expired.pdf",
            date(2026, 11, 1),
        )
        create_document(
            employee_b,
            HRDocument.DocumentType.CERTIFICATION,
            "b-expiring-soon.pdf",
            date(2026, 11, 20),
        )

        result = self.ComplianceMetricsService.get_dashboard(
            department_id=self.department.pk,
            as_of=as_of,
        )

        # Only Department A contributes to the headcount.
        self.assertEqual(result["headcount"], 1)

        # Profile completion must exclude Department B.
        self.assertEqual(result["profiles"]["complete"], 0)
        self.assertEqual(result["profiles"]["incomplete"], 1)
        self.assertEqual(result["profiles"]["completion_rate"], 0.0)

        # Missing required documents must only concern Department A.
        self.assertEqual(
            result["documents"]["compliant_employees"],
            0,
        )
        self.assertEqual(
            result["documents"]["employees_missing_required_documents"],
            1,
        )
        self.assertEqual(result["documents"]["compliance_rate"], 0.0)

        missing_details = result["documents"]["missing_documents_details"]
        self.assertEqual(len(missing_details), 1)
        self.assertEqual(
            missing_details[0]["employee_name"],
            employee_a.user.name,
        )

        # Expired and soon-expiring documents must exclude Department B.
        self.assertEqual(result["documents"]["expired_count"], 1)
        self.assertEqual(result["documents"]["expiring_soon_count"], 1)

        self.assertEqual(
            result["documents"]["expired_details"][0]["employee__user__name"],
            employee_a.user.name,
        )
        self.assertEqual(
            result["documents"]["expiring_soon_details"][0]["employee__user__name"],
            employee_a.user.name,
        )


    def test_dashboard_supports_department_filter(self):
        self.create_employee(
            "COMP-005",
            "department@example.com",
        )

        result = self.ComplianceMetricsService.get_dashboard(
            department_id=self.department.pk,
        )

        self.assertEqual(result["headcount"], 1)

class SecurityMetricsServiceTests(TestCase):
    """Tests for SOC/SIEM security dashboard metrics."""

    def setUp(self):
        from accounts.models import SecurityEvent
        from employees.services.dashboard.security_metrics import (
            SecurityMetricsService,
        )

        self.SecurityEvent = SecurityEvent
        self.SecurityMetricsService = SecurityMetricsService

        self.department_a = Department.objects.create(
            name="Security Department A",
            code="SEC-A",
        )
        self.department_b = Department.objects.create(
            name="Security Department B",
            code="SEC-B",
        )

        self.position_a = Position.objects.create(
            title="Security Analyst A",
            department=self.department_a,
        )
        self.position_b = Position.objects.create(
            title="Security Analyst B",
            department=self.department_b,
        )

        self.user = User.objects.create_user(
            email="security-metrics@example.com",
            name="Security Metrics User",
            password="TestPassword123!",
            is_active=True,
        )

        self.user_b = User.objects.create_user(
            email="security-metrics-b@example.com",
            name="Security Metrics User B",
            password="TestPassword123!",
            is_active=True,
        )

        self.employee_a = EmployeeProfile.objects.create(
            user=self.user,
            employee_id="SEC-EMP-001",
            department=self.department_a,
            position=self.position_a,
            hire_date=date.today(),
        )

        self.employee_b = EmployeeProfile.objects.create(
            user=self.user_b,
            employee_id="SEC-EMP-002",
            department=self.department_b,
            position=self.position_b,
            hire_date=date.today(),
        )

    def create_event(
        self,
        *,
        event_type,
        ip_address="192.0.2.10",
        user=None,
        request_path="/api/test/",
    ):
        return self.SecurityEvent.objects.create(
            user=user,
            event_type=event_type,
            ip_address=ip_address,
            request_path=request_path,
            user_agent="Security Metrics Test Agent",
        )

    def test_overview_counts_login_events(self):
        self.create_event(
            event_type="LOGIN_SUCCESS",
            user=self.user,
        )
        self.create_event(
            event_type="LOGIN_FAILED",
            user=self.user,
        )
        self.create_event(
            event_type="LOGIN_FAILED",
            user=self.user,
        )

        result = self.SecurityMetricsService.get_dashboard()

        self.assertEqual(result["overview"]["total_events"], 3)
        self.assertEqual(result["overview"]["login_success"], 1)
        self.assertEqual(result["overview"]["login_failed"], 2)

    def test_detection_metrics_count_security_events(self):
        event_types = [
            "BRUTE_FORCE_DETECTED",
            "SUSPICIOUS_IP_DETECTED",
            "UNAUTHORIZED_ACCESS",
            "PRIVILEGE_ESCALATION",
        ]

        for event_type in event_types:
            self.create_event(event_type=event_type)

        result = self.SecurityMetricsService.get_dashboard()

        self.assertEqual(result["detections"]["brute_force"], 1)
        self.assertEqual(result["detections"]["suspicious_ip"], 1)
        self.assertEqual(result["detections"]["unauthorized_access"], 1)
        self.assertEqual(result["detections"]["privilege_escalation"], 1)

    def test_event_distribution_groups_by_event_type(self):
        self.create_event(event_type="LOGIN_FAILED")
        self.create_event(event_type="LOGIN_FAILED")
        self.create_event(event_type="LOGIN_SUCCESS")

        result = self.SecurityMetricsService.get_dashboard()

        distribution = {
            item["event_type"]: item["count"]
            for item in result["events"]["distribution"]
        }

        self.assertEqual(distribution["LOGIN_FAILED"], 2)
        self.assertEqual(distribution["LOGIN_SUCCESS"], 1)

    def test_source_metrics_count_distinct_ips_and_users(self):
        second_user = User.objects.create_user(
            email="security-second@example.com",
            name="Second Security User",
            password="TestPassword123!",
            is_active=True,
        )

        self.create_event(
            event_type="LOGIN_FAILED",
            ip_address="192.0.2.10",
            user=self.user,
        )
        self.create_event(
            event_type="LOGIN_FAILED",
            ip_address="192.0.2.10",
            user=second_user,
        )
        self.create_event(
            event_type="LOGIN_FAILED",
            ip_address="192.0.2.20",
            user=self.user,
        )
        self.create_event(
            event_type="LOGIN_FAILED",
            ip_address=None,
            user=None,
        )

        result = self.SecurityMetricsService.get_dashboard()

        self.assertEqual(result["sources"]["distinct_ips"], 2)
        self.assertEqual(result["sources"]["distinct_users"], 2)

    def test_recent_events_respect_limit(self):
        for _ in range(12):
            self.create_event(event_type="LOGIN_FAILED")

        result = self.SecurityMetricsService.get_dashboard(
            recent_limit=5,
        )

        self.assertEqual(len(result["recent_events"]), 5)

        self.assertNotIn(
            "details",
            result["recent_events"][0],
        )
        self.assertNotIn(
            "user_agent",
            result["recent_events"][0],
        )

    def test_daily_activity_respects_requested_period(self):
        from datetime import timedelta

        today = date.today()
        yesterday = today - timedelta(days=1)
        outside_period = today - timedelta(days=10)

        self.create_event(event_type="LOGIN_FAILED")

        self.SecurityEvent.objects.filter(
            event_type="LOGIN_FAILED"
        ).update(
            created_at=timezone.make_aware(
                datetime.combine(yesterday, datetime.min.time())
            )
        )

        self.create_event(event_type="LOGIN_SUCCESS")

        self.SecurityEvent.objects.filter(
            event_type="LOGIN_SUCCESS"
        ).update(
            created_at=timezone.make_aware(
                datetime.combine(outside_period, datetime.min.time())
            )
        )

        result = self.SecurityMetricsService.get_dashboard(
            as_of=today,
            days=7,
        )

        self.assertEqual(
            sum(item["count"] for item in result["daily_activity"]),
            1,
        )

    def test_invalid_period_is_rejected(self):
        with self.assertRaises(ValueError):
            self.SecurityMetricsService.get_dashboard(days=0)

    def test_invalid_recent_limit_is_rejected(self):
        with self.assertRaises(ValueError):
            self.SecurityMetricsService.get_dashboard(
                recent_limit=0,
            )

    def test_department_filter_excludes_other_department_events(self):
        self.create_event(
            event_type="LOGIN_FAILED",
            user=self.user,
        )
        self.create_event(
            event_type="PRIVILEGE_ESCALATION",
            user=self.user_b,
        )

        result = self.SecurityMetricsService.get_dashboard(
            department_id=self.department_a.id,
        )

        self.assertEqual(result["overview"]["total_events"], 1)
        self.assertEqual(result["overview"]["login_failed"], 1)
        self.assertEqual(
            result["detections"]["privilege_escalation"],
            0,
        )

    def test_department_filter_excludes_events_without_employee_profile(self):
        self.create_event(
            event_type="LOGIN_FAILED",
            user=self.user,
        )
        self.create_event(
            event_type="UNAUTHORIZED_ACCESS",
            user=None,
        )

        result = self.SecurityMetricsService.get_dashboard(
            department_id=self.department_a.id,
        )

        self.assertEqual(result["overview"]["total_events"], 1)
        self.assertEqual(result["overview"]["login_failed"], 1)
        self.assertEqual(
            result["detections"]["unauthorized_access"],
            0,
        )

class AuditMetricsServiceTests(TestCase):
    """Tests for consolidated audit dashboard metrics."""

    def setUp(self):
        from accounts.models import AuditLog
        from employees.models import (
            DocumentAccessLog,
            WorkflowExecutionLog,
        )
        from employees.services.dashboard.audit_metrics import (
            AuditMetricsService,
        )

        self.AuditLog = AuditLog
        self.DocumentAccessLog = DocumentAccessLog
        self.WorkflowExecutionLog = WorkflowExecutionLog
        self.AuditMetricsService = AuditMetricsService

        self.user = User.objects.create_user(
            email="audit-metrics@example.com",
            name="Audit Metrics User",
            password="TestPassword123!",
            is_active=True,
        )

    def create_audit_log(self, action="LOGIN"):
        return self.AuditLog.objects.create(
            user=self.user,
            action=action,
            details="Audit metrics test",
        )

    def create_document_log(self, action):
        return self.DocumentAccessLog.objects.create(
            user=self.user,
            action=action,
            ip_address="192.0.2.10",
            request_path="/api/v1/employees/hr-documents/",
            details="Document audit test",
        )

    def create_workflow_log(self, outcome="SUCCESS"):
        return self.WorkflowExecutionLog.objects.create(
            actor=self.user,
            event_type="TASK_STATUS_CHANGED",
            outcome=outcome,
            details={"test": True},
        )

    def test_overview_counts_all_three_audit_sources(self):
        self.create_audit_log()
        self.create_document_log(
            self.DocumentAccessLog.Action.VIEW
        )
        self.create_workflow_log()

        result = self.AuditMetricsService.get_dashboard()

        self.assertEqual(result["overview"]["total_entries"], 3)
        self.assertEqual(result["overview"]["general_audit_entries"], 1)
        self.assertEqual(result["overview"]["document_access_entries"], 1)
        self.assertEqual(result["overview"]["workflow_entries"], 1)

    def test_general_audit_distribution_groups_by_action(self):
        self.create_audit_log("LOGIN")
        self.create_audit_log("LOGIN")
        self.create_audit_log("PASSWORD_CHANGE")

        result = self.AuditMetricsService.get_dashboard()

        distribution = {
            item["action"]: item["count"]
            for item in result["general_audit"]["distribution"]
        }

        self.assertEqual(distribution["LOGIN"], 2)
        self.assertEqual(distribution["PASSWORD_CHANGE"], 1)

    def test_document_access_distribution_groups_by_action(self):
        self.create_document_log(
            self.DocumentAccessLog.Action.VIEW
        )
        self.create_document_log(
            self.DocumentAccessLog.Action.VIEW
        )
        self.create_document_log(
            self.DocumentAccessLog.Action.DOWNLOAD
        )

        result = self.AuditMetricsService.get_dashboard()

        distribution = {
            item["action"]: item["count"]
            for item in result["document_access"]["distribution"]
        }

        self.assertEqual(distribution["VIEW"], 2)
        self.assertEqual(distribution["DOWNLOAD"], 1)

    def test_document_access_denied_is_counted(self):
        self.create_document_log(
            self.DocumentAccessLog.Action.ACCESS_DENIED
        )
        self.create_document_log(
            self.DocumentAccessLog.Action.VIEW
        )

        result = self.AuditMetricsService.get_dashboard()

        self.assertEqual(
            result["document_access"]["access_denied"],
            1,
        )

    def test_workflow_distribution_groups_by_event_type(self):
        self.create_workflow_log("SUCCESS")
        self.create_workflow_log("FAILURE")

        result = self.AuditMetricsService.get_dashboard()

        distribution = {
            item["event_type"]: item["count"]
            for item in result["workflows"]["distribution"]
        }

        self.assertEqual(distribution["TASK_STATUS_CHANGED"], 2)

    def test_workflow_outcomes_are_counted(self):
        self.create_workflow_log("SUCCESS")
        self.create_workflow_log("SUCCESS")
        self.create_workflow_log("FAILURE")
        self.create_workflow_log("DENIED")

        result = self.AuditMetricsService.get_dashboard()

        self.assertEqual(result["workflows"]["outcomes"]["SUCCESS"], 2)
        self.assertEqual(result["workflows"]["outcomes"]["FAILURE"], 1)
        self.assertEqual(result["workflows"]["outcomes"]["DENIED"], 1)

    def test_recent_events_respect_limit(self):
        for _ in range(12):
            self.create_audit_log()

        result = self.AuditMetricsService.get_dashboard(
            recent_limit=5
        )

        self.assertEqual(
            len(result["recent_events"]["general_audit"]),
            5,
        )

    def test_daily_activity_contains_each_audit_source(self):
        self.create_audit_log()
        self.create_document_log(
            self.DocumentAccessLog.Action.VIEW
        )
        self.create_workflow_log()

        result = self.AuditMetricsService.get_dashboard()

        self.assertEqual(
            sum(
                item["count"]
                for item in result["daily_activity"]["general_audit"]
            ),
            1,
        )
        self.assertEqual(
            sum(
                item["count"]
                for item in result["daily_activity"]["document_access"]
            ),
            1,
        )
        self.assertEqual(
            sum(
                item["count"]
                for item in result["daily_activity"]["workflow"]
            ),
            1,
        )

    def test_invalid_period_is_rejected(self):
        with self.assertRaises(ValueError):
            self.AuditMetricsService.get_dashboard(days=0)

    def test_invalid_recent_limit_is_rejected(self):
        with self.assertRaises(ValueError):
            self.AuditMetricsService.get_dashboard(recent_limit=0)

    def test_department_filter_isolates_all_audit_sources(self):
        from django.utils import timezone
        from accounts.models import AuditLog
        from employees.models import (
            Department,
            Position,
            EmployeeProfile,
            HRDocument,
            OnboardingTemplate,
            OnboardingJourney,
        )

        # Create two departments.
        department_a = Department.objects.create(
            name="Audit Department A",
            code="AUD-A",
        )
        department_b = Department.objects.create(
            name="Audit Department B",
            code="AUD-B",
        )

        # Create one position per department.
        position_a = Position.objects.create(
            title="Audit Employee A",
            department=department_a,
        )
        position_b = Position.objects.create(
            title="Audit Employee B",
            department=department_b,
        )

        # Create employees.
        user_a = User.objects.create_user(
            email="audit-department-a@example.com",
            name="Audit Employee A",
            password="TestPassword123!",
            is_active=True,
        )
        user_b = User.objects.create_user(
            email="audit-department-b@example.com",
            name="Audit Employee B",
            password="TestPassword123!",
            is_active=True,
        )

        employee_a = EmployeeProfile.objects.create(
            user=user_a,
            employee_id="AUD-EMP-001",
            department=department_a,
            position=position_a,
            hire_date=timezone.localdate(),
        )
        employee_b = EmployeeProfile.objects.create(
            user=user_b,
            employee_id="AUD-EMP-002",
            department=department_b,
            position=position_b,
            hire_date=timezone.localdate(),
        )

        # General audit events belong to the employee's department.
        AuditLog.objects.create(
            user=user_a,
            action="LOGIN",
            details="Department A audit event",
        )
        AuditLog.objects.create(
            user=user_b,
            action="PASSWORD_CHANGE",
            details="Department B audit event",
        )

        # Create documents owned by employees in different departments.
        document_a = HRDocument.objects.create(
            employee=employee_a,
            title="Department A Document",
            document_type=HRDocument.DocumentType.OTHER,
            original_filename="department-a.pdf",
            storage_key="hr-documents/audit/department-a.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            uploaded_by=user_a,
        )
        document_b = HRDocument.objects.create(
            employee=employee_b,
            title="Department B Document",
            document_type=HRDocument.DocumentType.OTHER,
            original_filename="department-b.pdf",
            storage_key="hr-documents/audit/department-b.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            uploaded_by=user_b,
        )

        # Document access events must follow document ownership,
        # not the department of the user performing the action.
        self.DocumentAccessLog.objects.create(
            document=document_a,
            user=self.user,
            action=self.DocumentAccessLog.Action.VIEW,
            ip_address="192.0.2.10",
            request_path="/api/v1/employees/hr-documents/",
            details="Department A document access",
        )
        self.DocumentAccessLog.objects.create(
            document=document_b,
            user=self.user,
            action=self.DocumentAccessLog.Action.DOWNLOAD,
            ip_address="192.0.2.11",
            request_path="/api/v1/employees/hr-documents/",
            details="Department B document access",
        )

        # Create an onboarding template shared by both journeys.
        template = OnboardingTemplate.objects.create(
            name="Audit Metrics Department Template",
            created_by=self.user,
        )

        journey_a = OnboardingJourney.objects.create(
            employee=employee_a,
            template=template,
            template_version=template.version,
            created_by=self.user,
        )
        journey_b = OnboardingJourney.objects.create(
            employee=employee_b,
            template=template,
            template_version=template.version,
            created_by=self.user,
        )

        # Workflow events must follow the journey employee,
        # not the actor's department.
        self.WorkflowExecutionLog.objects.create(
            journey=journey_a,
            actor=self.user,
            event_type="TASK_STATUS_CHANGED",
            outcome="SUCCESS",
            details={"department": "A"},
        )
        self.WorkflowExecutionLog.objects.create(
            journey=journey_b,
            actor=self.user,
            event_type="TASK_STATUS_CHANGED",
            outcome="FAILURE",
            details={"department": "B"},
        )

        # Create events without a department relationship.
        AuditLog.objects.create(
            user=None,
            action="LOGIN",
            details="Unassigned audit event",
        )
        self.DocumentAccessLog.objects.create(
            document=None,
            user=self.user,
            action=self.DocumentAccessLog.Action.VIEW,
            ip_address="192.0.2.12",
            request_path="/api/v1/employees/hr-documents/",
            details="Unassigned document event",
        )
        self.WorkflowExecutionLog.objects.create(
            journey=None,
            actor=self.user,
            event_type="TASK_STATUS_CHANGED",
            outcome="SUCCESS",
            details={"department": None},
        )

        # Request metrics for Department A only.
        result = self.AuditMetricsService.get_dashboard(
            department_id=department_a.pk,
        )

        # Verify overview counts.
        self.assertEqual(
            result["overview"]["general_audit_entries"],
            1,
        )
        self.assertEqual(
            result["overview"]["document_access_entries"],
            1,
        )
        self.assertEqual(
            result["overview"]["workflow_entries"],
            1,
        )
        self.assertEqual(
            result["overview"]["total_entries"],
            3,
        )

        # Verify general audit distribution.
        audit_distribution = {
            item["action"]: item["count"]
            for item in result["general_audit"]["distribution"]
        }
        self.assertEqual(audit_distribution, {"LOGIN": 1})

        # Verify document access distribution.
        document_distribution = {
            item["action"]: item["count"]
            for item in result["document_access"]["distribution"]
        }
        self.assertEqual(
            document_distribution,
            {"VIEW": 1},
        )

        # Verify workflow outcomes.
        self.assertEqual(
            result["workflows"]["outcomes"]["SUCCESS"],
            1,
        )
        self.assertEqual(
            result["workflows"]["outcomes"].get("FAILURE", 0),
            0,
        )

        # Verify daily activity uses the filtered querysets.
        self.assertEqual(
            sum(
                item["count"]
                for item in result["daily_activity"]["general_audit"]
            ),
            1,
        )
        self.assertEqual(
            sum(
                item["count"]
                for item in result["daily_activity"]["document_access"]
            ),
            1,
        )
        self.assertEqual(
            sum(
                item["count"]
                for item in result["daily_activity"]["workflow"]
            ),
            1,
        )

class RiskMetricsServiceTests(TestCase):
    """Tests for HR compliance, document and security risk indicators."""

    def setUp(self):
        from accounts.models import SecurityEvent
        from employees.models import HRDocument
        from employees.services.dashboard.risk_metrics import (
            RiskMetricsService,
        )

        self.SecurityEvent = SecurityEvent
        self.HRDocument = HRDocument
        self.RiskMetricsService = RiskMetricsService

        self.department = Department.objects.create(
            name="Risk Department",
            code="RISK",
        )

        self.position = Position.objects.create(
            title="Risk Employee",
            department=self.department,
        )

        self.user = User.objects.create_user(
            email="risk@example.com",
            name="Risk Employee",
            password="TestPassword123!",
            is_active=True,
        )

        self.profile = EmployeeProfile.objects.create(
            user=self.user,
            employee_id="RISK-001",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 15),
        )

    def create_document(self, *, status, document_type=None, suffix="1"):
        return self.HRDocument.objects.create(
            employee=self.profile,
            title=f"Risk Document {suffix}",
            document_type=(
                document_type
                or self.HRDocument.DocumentType.OTHER
            ),
            original_filename=f"risk-{suffix}.pdf",
            storage_key=f"hr-documents/risk/{suffix}.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            uploaded_by=self.user,
            status=status,
        )

    def create_security_event(self, event_type):
        return self.SecurityEvent.objects.create(
            user=self.user,
            event_type=event_type,
            ip_address="192.0.2.10",
            request_path="/api/test/",
            user_agent="Risk Metrics Test Agent",
        )

    def test_document_lifecycle_counts_statuses(self):
        self.create_document(
            status=self.HRDocument.Status.PENDING_SCAN,
            suffix="1",
        )
        self.create_document(
            status=self.HRDocument.Status.PENDING_REVIEW,
            suffix="2",
        )
        self.create_document(
            status=self.HRDocument.Status.QUARANTINED,
            suffix="3",
        )
        self.create_document(
            status=self.HRDocument.Status.REJECTED,
            suffix="4",
        )
        self.create_document(
            status=self.HRDocument.Status.VERIFIED,
            suffix="5",
        )
        self.create_document(
            status=self.HRDocument.Status.ARCHIVED,
            suffix="6",
        )

        result = self.RiskMetricsService.get_dashboard()

        self.assertEqual(
            result["document_lifecycle"],
            {
                "pending_scan": 1,
                "pending_review": 1,
                "quarantined": 1,
                "rejected": 1,
                "verified": 1,
                "archived": 1,
            },
        )

    def test_security_detections_are_counted(self):
        event_types = [
            "BRUTE_FORCE_DETECTED",
            "SUSPICIOUS_IP_DETECTED",
            "UNAUTHORIZED_ACCESS",
            "PRIVILEGE_ESCALATION",
        ]

        for event_type in event_types:
            self.create_security_event(event_type)

        result = self.RiskMetricsService.get_dashboard()

        self.assertEqual(
            result["security"],
            {
                "brute_force": 1,
                "suspicious_ip": 1,
                "unauthorized_access": 1,
                "privilege_escalation": 1,
            },
        )

    def test_compliance_risks_are_included(self):
        result = self.RiskMetricsService.get_dashboard()

        self.assertEqual(
            result["compliance"]["incomplete_profiles"],
            1,
        )
        self.assertEqual(
            result["compliance"][
                "employees_missing_required_documents"
            ],
            1,
        )

    def test_department_filter_applies_to_documents(self):
        other_department = Department.objects.create(
            name="Other Risk Department",
            code="RISK2",
        )

        other_position = Position.objects.create(
            title="Other Risk Employee",
            department=other_department,
        )

        other_user = User.objects.create_user(
            email="other-risk@example.com",
            name="Other Risk Employee",
            password="TestPassword123!",
            is_active=True,
        )

        other_profile = EmployeeProfile.objects.create(
            user=other_user,
            employee_id="RISK-002",
            department=other_department,
            position=other_position,
            hire_date=date(2026, 1, 15),
        )

        self.HRDocument.objects.create(
            employee=other_profile,
            title="Other Department Document",
            document_type=self.HRDocument.DocumentType.OTHER,
            original_filename="other.pdf",
            storage_key="hr-documents/risk/other.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            uploaded_by=other_user,
            status=self.HRDocument.Status.QUARANTINED,
        )

        result = self.RiskMetricsService.get_dashboard(
            department_id=self.department.pk,
        )

        self.assertEqual(
            result["document_lifecycle"]["quarantined"],
            0,
        )

    def test_dashboard_does_not_generate_artificial_risk_score(self):
        result = self.RiskMetricsService.get_dashboard()

        self.assertNotIn("risk_score", result)
        self.assertIn("compliance", result)
        self.assertIn("document_lifecycle", result)
        self.assertIn("security", result)


    def test_department_filter_isolates_all_risk_indicators(self):
        as_of = date(2026, 11, 9)

        # Create a second department and employee.
        other_department = Department.objects.create(
            name="Other Risk Department",
            code="RISK3",
        )
        other_position = Position.objects.create(
            title="Other Risk Employee",
            department=other_department,
        )
        other_user = User.objects.create_user(
            email="other-risk-isolation@example.com",
            name="Other Risk Employee",
            password="TestPassword123!",
            is_active=True,
        )
        other_profile = EmployeeProfile.objects.create(
            user=other_user,
            employee_id="RISK-003",
            department=other_department,
            position=other_position,
            phone="",
            address="",
            hire_date=as_of,
        )

        # Make the employee in the selected department incomplete.
        self.profile.phone = ""
        self.profile.address = ""
        self.profile.save(update_fields=["phone", "address"])

        # Create a quarantined document in each department.
        self.create_document(
            status=self.HRDocument.Status.QUARANTINED,
            suffix="selected-quarantine",
        )
        self.HRDocument.objects.create(
            employee=other_profile,
            title="Other Department Quarantined",
            document_type=self.HRDocument.DocumentType.OTHER,
            original_filename="other-quarantine.pdf",
            storage_key="hr-documents/risk/other-quarantine.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            uploaded_by=other_user,
            status=self.HRDocument.Status.QUARANTINED,
        )

        # Create expired and soon-expiring verified documents
        # for both departments.
        for profile, user, prefix in (
            (self.profile, self.user, "selected"),
            (other_profile, other_user, "other"),
        ):
            for suffix, expiry in (
                ("expired", as_of - timedelta(days=1)),
                ("soon", as_of + timedelta(days=15)),
            ):
                self.HRDocument.objects.create(
                    employee=profile,
                    title=f"{prefix} {suffix}",
                    document_type=self.HRDocument.DocumentType.OTHER,
                    original_filename=f"{prefix}-{suffix}.pdf",
                    storage_key=f"hr-documents/risk/{prefix}-{suffix}.pdf",
                    mime_type="application/pdf",
                    size_bytes=1024,
                    uploaded_by=user,
                    status=self.HRDocument.Status.VERIFIED,
                    expires_at=expiry,
                )

        # Create one security detection per department.
        self.create_security_event("BRUTE_FORCE_DETECTED")
        self.SecurityEvent.objects.create(
            user=other_user,
            event_type="BRUTE_FORCE_DETECTED",
            ip_address="192.0.2.20",
            request_path="/api/test/",
            user_agent="Other Risk Test Agent",
        )

        result = self.RiskMetricsService.get_dashboard(
            department_id=self.department.pk,
            as_of=as_of,
        )

        self.assertEqual(
            result["document_lifecycle"]["quarantined"],
            1,
        )
        self.assertEqual(
            result["security"]["brute_force"],
            1,
        )
        self.assertEqual(
            result["compliance"]["incomplete_profiles"],
            1,
        )
        self.assertEqual(
            result["compliance"][
                "employees_missing_required_documents"
            ],
            1,
        )
        self.assertEqual(
            result["compliance"]["expired_documents"],
            1,
        )
        self.assertEqual(
            result["compliance"]["documents_expiring_soon"],
            1,
        )


class DashboardServiceTests(TestCase):
    """Tests for the dashboard orchestration service."""

    def setUp(self):
        from employees.services.dashboard.dashboard_service import (
            DashboardService,
        )

        self.DashboardService = DashboardService

    @patch(
        "employees.services.dashboard.dashboard_service."
        "WorkforceMetricsService.get_dashboard"
    )
    @patch(
        "employees.services.dashboard.dashboard_service."
        "ComplianceMetricsService.get_dashboard"
    )
    @patch(
        "employees.services.dashboard.dashboard_service."
        "OnboardingMetricsService.get_dashboard"
    )
    @patch(
        "employees.services.dashboard.dashboard_service."
        "OperationsMetricsService.get_dashboard"
    )
    @patch(
        "employees.services.dashboard.dashboard_service."
        "SecurityMetricsService.get_dashboard"
    )
    @patch(
        "employees.services.dashboard.dashboard_service."
        "AuditMetricsService.get_dashboard"
    )
    @patch(
        "employees.services.dashboard.dashboard_service."
        "RiskMetricsService.get_dashboard"
    )
    @patch(
        "employees.services.dashboard.dashboard_service."
        "RecruitmentMetricsService.get_dashboard"
    )
    def test_dashboard_aggregates_all_eight_services(
        self,
        recruitment_mock,
        risk_mock,
        audit_mock,
        security_mock,
        operations_mock,
        onboarding_mock,
        compliance_mock,
        workforce_mock,
    ):
        services = {
            "workforce": workforce_mock,
            "compliance": compliance_mock,
            "onboarding": onboarding_mock,
            "operations": operations_mock,
            "security": security_mock,
            "audit": audit_mock,
            "risk": risk_mock,
            "recruitment": recruitment_mock,
        }

        for name, service_mock in services.items():
            service_mock.return_value = {"service": name}

        result = self.DashboardService.get_dashboard()

        self.assertEqual(
            result,
            {
                name: {"service": name}
                for name in services
            },
        )

        for service_mock in services.values():
            service_mock.assert_called_once()

    @patch(
        "employees.services.dashboard.dashboard_service."
        "WorkforceMetricsService.get_dashboard"
    )
    @patch(
        "employees.services.dashboard.dashboard_service."
        "ComplianceMetricsService.get_dashboard"
    )
    @patch(
        "employees.services.dashboard.dashboard_service."
        "OnboardingMetricsService.get_dashboard"
    )
    @patch(
        "employees.services.dashboard.dashboard_service."
        "OperationsMetricsService.get_dashboard"
    )
    @patch(
        "employees.services.dashboard.dashboard_service."
        "SecurityMetricsService.get_dashboard"
    )
    @patch(
        "employees.services.dashboard.dashboard_service."
        "AuditMetricsService.get_dashboard"
    )
    @patch(
        "employees.services.dashboard.dashboard_service."
        "RiskMetricsService.get_dashboard"
    )
    @patch(
        "employees.services.dashboard.dashboard_service."
        "RecruitmentMetricsService.get_dashboard"
    )
    def test_dashboard_forwards_parameters_to_services(
        self,
        recruitment_mock,
        risk_mock,
        audit_mock,
        security_mock,
        operations_mock,
        onboarding_mock,
        compliance_mock,
        workforce_mock,
    ):
        from datetime import date

        as_of = date(2026, 10, 30)

        self.DashboardService.get_dashboard(
            department_id=12,
            as_of=as_of,
            days=14,
            recent_limit=5,
        )

        for service_mock in (
            workforce_mock,
            compliance_mock,
            onboarding_mock,
            risk_mock,
        ):
            service_mock.assert_called_once_with(
                department_id=12,
                as_of=as_of,
            )

        operations_mock.assert_called_once_with(
            department_id=12,
            as_of=as_of,
            days=14,
        )

        recruitment_mock.assert_called_once_with(
            department_id=12,
            as_of=as_of,
            days=14,
        )
        for service_mock in (security_mock, audit_mock):
            service_mock.assert_called_once_with(
                department_id=12,
                as_of=as_of,
                days=14,
                recent_limit=5,
            )

    @patch(
        "employees.services.dashboard.dashboard_service."
        "WorkforceMetricsService.get_dashboard"
    )
    def test_dashboard_propagates_service_errors(self, workforce_mock):
        workforce_mock.side_effect = ValueError("Metrics unavailable")

        with self.assertRaisesMessage(
            ValueError,
            "Metrics unavailable",
        ):
            self.DashboardService.get_dashboard()


    def test_dashboard_response_matches_serializer_contract(self):
        """Real dashboard data matches the complete response serializer."""

        from employees.models import (
            OnboardingTemplate,
            OnboardingPhase,
            OnboardingActivityTemplate,
            OnboardingJourney,
            OnboardingTask,
            WorkflowExecutionLog,
        )
        from employees.services.onboarding import OnboardingService
        from employees.serializers import DashboardResponseSerializer

        today = timezone.localdate()

        # --------------------------------------------------
        # 1. Workforce and compliance fixtures
        # --------------------------------------------------
        department = Department.objects.create(
            name="Dashboard Contract Department",
            code="DASH-CONTRACT",
        )

        position = Position.objects.create(
            title="Dashboard Contract Employee",
            department=department,
        )

        user = User.objects.create_user(
            email="dashboard-contract@example.com",
            name="Dashboard Contract Employee",
            password="TestPassword123!",
            is_active=True,
        )

        employee = EmployeeProfile.objects.create(
            user=user,
            employee_id="DASH-CONTRACT-001",
            department=department,
            position=position,
            hire_date=today,
        )

        # Intentionally incomplete profile:
        # phone and address remain blank.

        # --------------------------------------------------
        # 2. HR documents: compliance and lifecycle metrics
        # --------------------------------------------------
        def create_document(suffix, status, expires_at=None):
            return HRDocument.objects.create(
                employee=employee,
                title=f"Dashboard Contract Document {suffix}",
                document_type=HRDocument.DocumentType.OTHER,
                original_filename=f"dashboard-{suffix}.pdf",
                storage_key=f"dashboard-contract/{suffix}.pdf",
                mime_type="application/pdf",
                size_bytes=1024,
                uploaded_by=user,
                status=status,
                expires_at=expires_at,
            )

        create_document(
            "pending-scan",
            HRDocument.Status.PENDING_SCAN,
        )
        create_document(
            "pending-review",
            HRDocument.Status.PENDING_REVIEW,
        )
        create_document(
            "quarantined",
            HRDocument.Status.QUARANTINED,
        )
        create_document(
            "rejected",
            HRDocument.Status.REJECTED,
        )
        create_document(
            "expired",
            HRDocument.Status.VERIFIED,
            expires_at=today - timedelta(days=1),
        )
        create_document(
            "archived",
            HRDocument.Status.ARCHIVED,
        )
        create_document(
            "expiring-soon",
            HRDocument.Status.VERIFIED,
            expires_at=today + timedelta(days=10),
        )

        # OTHER documents do not satisfy the required
        # identity, employment contract and tax document types.

        # --------------------------------------------------
        # 3. Onboarding fixtures
        # --------------------------------------------------
        template = OnboardingTemplate.objects.create(
            name="Dashboard Contract Template",
            description="Dashboard response contract test",
            version=1,
            created_by=user,
        )

        phase = OnboardingPhase.objects.create(
            template=template,
            name="Contract Test Phase",
            description="Dashboard contract phase",
            order=1,
        )

        activity = OnboardingActivityTemplate.objects.create(
            phase=phase,
            name="Contract Test Activity",
            description="Dashboard contract activity",
            order=1,
            is_required=True,
            default_due_days=3,
        )

        OnboardingService.publish_template(template.pk)

        journey = OnboardingService.create_journey(
            employee_id=employee.pk,
            template_id=template.pk,
            created_by=user,
        )

        task = OnboardingTask.objects.get(
            journey=journey,
            activity_template=activity,
        )

        task.priority = "URGENT"
        task.due_date = today - timedelta(days=1)
        task.save(update_fields=["priority", "due_date"])

        # --------------------------------------------------
        # 4. Operations and workflow audit fixtures
        # --------------------------------------------------
        WorkflowExecutionLog.objects.create(
            journey=journey,
            actor=user,
            event_type="TASK_STATUS_CHANGED",
            outcome="SUCCESS",
            details={"source": "dashboard_contract_test"},
        )

        WorkflowExecutionLog.objects.create(
            journey=journey,
            actor=user,
            event_type="NOTIFICATION_FAILED",
            outcome="FAILURE",
            details={"notification_type": "EMAIL"},
        )

        # --------------------------------------------------
        # 5. Security fixtures
        # --------------------------------------------------
        SecurityEvent.objects.create(
            user=user,
            event_type="LOGIN_SUCCESS",
            ip_address="192.0.2.10",
            request_path="/api/test/login/",
            user_agent="Dashboard Contract Test",
        )

        SecurityEvent.objects.create(
            user=user,
            event_type="BRUTE_FORCE_DETECTED",
            ip_address="192.0.2.11",
            request_path="/api/test/login/",
            user_agent="Dashboard Contract Test",
        )

        # --------------------------------------------------
        # 6. General and document-access audit fixtures
        # --------------------------------------------------
        AuditLog.objects.create(
            user=user,
            action="LOGIN",
            details="Dashboard contract test",
        )

        DocumentAccessLog.objects.create(
            document=HRDocument.objects.get(
                employee=employee,
                title="Dashboard Contract Document quarantined",
            ),
            user=user,
            action=DocumentAccessLog.Action.ACCESS_DENIED,
            ip_address="192.0.2.10",
            request_path="/api/test/documents/",
            details="Dashboard contract test",
        )

        # --------------------------------------------------
        # 7. Execute the real dashboard and serialize it
        # --------------------------------------------------
        dashboard_data = self.DashboardService.get_dashboard(
            department_id=department.pk,
            as_of=today,
            days=7,
            recent_limit=10,
        )

        serializer = DashboardResponseSerializer(
            instance=dashboard_data,
        )

        serialized_data = serializer.data

        expected_sections = {
            "workforce",
            "compliance",
            "onboarding",
            "operations",
            "security",
            "audit",
            "risk",
            "recruitment",
        }

        self.assertEqual(
            set(serialized_data.keys()),
            expected_sections,
        )

        # --------------------------------------------------
        # 8. Workforce contract
        # --------------------------------------------------
        workforce = serialized_data["workforce"]

        self.assertEqual(workforce["headcount"]["total"], 1)
        self.assertEqual(workforce["departments"]["total"], 1)
        self.assertEqual(workforce["positions"]["total"], 1)
        self.assertTrue(workforce["departments"]["distribution"])
        self.assertTrue(workforce["positions"]["distribution"])
        self.assertTrue(workforce["roles"])
        self.assertEqual(workforce["as_of"], today.isoformat())

        # --------------------------------------------------
        # 9. Compliance contract
        # --------------------------------------------------
        compliance = serialized_data["compliance"]

        self.assertEqual(compliance["headcount"], 1)
        self.assertEqual(compliance["profiles"]["incomplete"], 1)
        self.assertEqual(
            len(compliance["profiles"]["incomplete_details"]),
            1,
        )
        self.assertEqual(
            compliance["documents"][
                "employees_missing_required_documents"
            ],
            1,
        )
        self.assertTrue(
            compliance["documents"]["missing_documents_details"]
        )
        self.assertEqual(compliance["documents"]["expired_count"], 1)
        self.assertEqual(
            compliance["documents"]["expiring_soon_count"],
            1,
        )
        self.assertTrue(compliance["documents"]["expired_details"])
        self.assertTrue(
            compliance["documents"]["expiring_soon_details"]
        )

        # --------------------------------------------------
        # 10. Onboarding contract
        # --------------------------------------------------
        onboarding = serialized_data["onboarding"]

        self.assertEqual(onboarding["journeys"]["total"], 1)
        self.assertEqual(onboarding["tasks"]["total"], 1)
        self.assertEqual(onboarding["tasks"]["urgent_priority"], 1)
        self.assertEqual(onboarding["tasks"]["overdue"], 1)
        self.assertEqual(
            onboarding["progress"]["total_eligible_tasks"],
            1,
        )

        # --------------------------------------------------
        # 11. Operations contract
        # --------------------------------------------------
        operations = serialized_data["operations"]

        self.assertEqual(operations["workflows"]["total"], 2)
        self.assertEqual(operations["workflows"]["success"], 1)
        self.assertEqual(operations["workflows"]["failure"], 1)
        self.assertEqual(operations["notifications"]["failed"], 1)
        self.assertTrue(operations["notifications"]["by_type"])
        self.assertTrue(operations["events"]["distribution"])
        self.assertTrue(operations["daily_activity"])

        # --------------------------------------------------
        # 12. Security contract
        # --------------------------------------------------
        security = serialized_data["security"]

        self.assertEqual(security["overview"]["total_events"], 2)
        self.assertEqual(security["overview"]["login_success"], 1)
        self.assertEqual(security["detections"]["brute_force"], 1)
        self.assertTrue(security["events"]["distribution"])
        self.assertTrue(security["daily_activity"])
        self.assertEqual(len(security["recent_events"]), 2)

        # --------------------------------------------------
        # 13. Audit contract
        # --------------------------------------------------
        audit = serialized_data["audit"]

        self.assertEqual(
            audit["overview"]["general_audit_entries"],
            1,
        )
        self.assertEqual(
            audit["overview"]["document_access_entries"],
            1,
        )
        self.assertEqual(
            audit["overview"]["workflow_entries"],
            2,
        )
        self.assertEqual(
            audit["document_access"]["access_denied"],
            1,
        )
        self.assertTrue(audit["general_audit"]["distribution"])
        self.assertTrue(audit["document_access"]["distribution"])
        self.assertTrue(audit["workflows"]["distribution"])
        self.assertTrue(audit["workflows"]["outcomes"])
        self.assertTrue(audit["recent_events"]["general_audit"])
        self.assertTrue(audit["recent_events"]["document_access"])
        self.assertTrue(audit["recent_events"]["workflow"])

        # --------------------------------------------------
        # 14. Risk contract
        # --------------------------------------------------
        risk = serialized_data["risk"]

        self.assertEqual(risk["compliance"]["incomplete_profiles"], 1)
        self.assertEqual(
            risk["compliance"]["employees_missing_required_documents"],
            1,
        )
        self.assertEqual(risk["compliance"]["expired_documents"], 1)
        self.assertEqual(
            risk["compliance"]["documents_expiring_soon"],
            1,
        )

        self.assertEqual(
            risk["document_lifecycle"]["pending_scan"],
            1,
        )
        self.assertEqual(
            risk["document_lifecycle"]["pending_review"],
            1,
        )
        self.assertEqual(
            risk["document_lifecycle"]["quarantined"],
            1,
        )
        self.assertEqual(
            risk["document_lifecycle"]["rejected"],
            1,
        )
        self.assertEqual(
            risk["document_lifecycle"]["verified"],
            2,
        )
        self.assertEqual(
            risk["document_lifecycle"]["archived"],
            1,
        )

        self.assertEqual(risk["security"]["brute_force"], 1)

        self.assertNotIn("risk_score", risk)
        # --------------------------------------------------
        # 15. Recruitment contract
        # --------------------------------------------------
        recruitment = serialized_data["recruitment"]

        self.assertEqual(
            recruitment["job_postings"]["total"],
            0,
        )
        self.assertTrue(recruitment["job_postings"]["by_status"])
        self.assertTrue(
            all(
                item["count"] == 0
                for item in recruitment["job_postings"]["by_status"]
            )
        )

        self.assertEqual(
            recruitment["applications"]["total"],
            0,
        )
        self.assertTrue(recruitment["applications"]["by_status"])
        self.assertTrue(
            all(
                item["count"] == 0
                for item in recruitment["applications"]["by_status"]
            )
        )
        self.assertEqual(
            recruitment["applications"]["received_in_period"],
            0,
        )
        self.assertEqual(
            recruitment["applications"]["hired_in_period"],
            0,
        )
        self.assertEqual(recruitment["daily_activity"], [])

class DashboardFilterSerializerTests(TestCase):
    """Tests for the HR dashboard filter serializer."""

    def setUp(self):
        self.department = Department.objects.create(
            name="Dashboard Engineering",
            code="DASH-ENG",
        )

    def test_default_values_are_applied(self):
        serializer = DashboardFilterSerializer(data={})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["days"], 7)
        self.assertEqual(serializer.validated_data["recent_limit"], 10)

    def test_existing_department_is_valid(self):
        serializer = DashboardFilterSerializer(
            data={"department_id": self.department.pk}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["department_id"],
            self.department.pk,
        )

    def test_nonexistent_department_is_invalid(self):
        serializer = DashboardFilterSerializer(
            data={"department_id": 999999}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("department_id", serializer.errors)

    def test_zero_department_id_is_invalid(self):
        serializer = DashboardFilterSerializer(
            data={"department_id": 0}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("department_id", serializer.errors)

    def test_days_boundaries(self):
        for value in (1, 365):
            with self.subTest(days=value):
                serializer = DashboardFilterSerializer(
                    data={"days": value}
                )
                self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_days_outside_boundaries_are_invalid(self):
        for value in (0, 366):
            with self.subTest(days=value):
                serializer = DashboardFilterSerializer(
                    data={"days": value}
                )
                self.assertFalse(serializer.is_valid())
                self.assertIn("days", serializer.errors)

    def test_recent_limit_boundaries(self):
        for value in (1, 100):
            with self.subTest(recent_limit=value):
                serializer = DashboardFilterSerializer(
                    data={"recent_limit": value}
                )
                self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_recent_limit_outside_boundaries_is_invalid(self):
        for value in (0, 101):
            with self.subTest(recent_limit=value):
                serializer = DashboardFilterSerializer(
                    data={"recent_limit": value}
                )
                self.assertFalse(serializer.is_valid())
                self.assertIn("recent_limit", serializer.errors)

    def test_past_reference_date_is_valid(self):
        past_date = date.today() - timedelta(days=1)

        serializer = DashboardFilterSerializer(
            data={"as_of": past_date.isoformat()}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["as_of"],
            past_date,
        )

    def test_future_reference_date_is_invalid(self):
        future_date = date.today() + timedelta(days=1)

        serializer = DashboardFilterSerializer(
            data={"as_of": future_date.isoformat()}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("as_of", serializer.errors)

    def test_malformed_reference_date_is_invalid(self):
        serializer = DashboardFilterSerializer(
            data={"as_of": "not-a-date"}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("as_of", serializer.errors)

class DashboardPermissionTests(TestCase):
    """Unit tests for HR dashboard access permissions."""

    def setUp(self):
        self.permission = DashboardPermission()

        self.view = type("DashboardView", (), {})()

        self.request = type("Request", (), {})()
        self.request.method = "GET"

    def make_user(self, role, is_active=True):
        return User.objects.create_user(
            email=f"{role.lower()}@dashboard.test",
            name=f"{role} User",
            password="TestPassword123!",
            role=role,
            is_active=is_active,
        )

    def test_super_admin_can_access_dashboard(self):
        self.request.user = self.make_user("SUPER_ADMIN")

        self.assertTrue(
            self.permission.has_permission(
                self.request,
                self.view,
            )
        )

    def test_hr_admin_can_access_dashboard(self):
        self.request.user = self.make_user("HR_ADMIN")

        self.assertTrue(
            self.permission.has_permission(
                self.request,
                self.view,
            )
        )

    def test_hr_manager_can_access_dashboard(self):
        self.request.user = self.make_user("HR_MANAGER")

        self.assertTrue(
            self.permission.has_permission(
                self.request,
                self.view,
            )
        )

    def test_employee_cannot_access_dashboard(self):
        self.request.user = self.make_user("EMPLOYEE")

        self.assertFalse(
            self.permission.has_permission(
                self.request,
                self.view,
            )
        )

    def test_inactive_hr_admin_cannot_access_dashboard(self):
        self.request.user = self.make_user(
            "HR_ADMIN",
            is_active=False,
        )

        self.assertFalse(
            self.permission.has_permission(
                self.request,
                self.view,
            )
        )

    def test_unauthenticated_user_cannot_access_dashboard(self):
        from django.contrib.auth.models import AnonymousUser
        from rest_framework.test import APIRequestFactory

        self.request = APIRequestFactory().get("/api/dashboard/")
        self.request.user = AnonymousUser()

        self.assertFalse(
            self.permission.has_permission(
                self.request,
                self.view,
            )
        )


    def test_post_request_is_denied(self):
        self.request.user = self.make_user("HR_ADMIN")
        self.request.method = "POST"

        self.assertFalse(
            self.permission.has_permission(
                self.request,
                self.view,
            )
        )

class DashboardAPITests(TestCase):
    """Tests for the HR dashboard API endpoint."""

    def setUp(self):
        from django.urls import reverse

        self.client = APIClient()
        self.dashboard_url = reverse("dashboard")

        self.super_admin = User.objects.create_user(
            email="dashboard-api-admin@example.com",
            name="Dashboard Super Admin",
            password="StrongPassword123!",
            role="SUPER_ADMIN",
        )

        self.hr_admin = User.objects.create_user(
            email="dashboard-api-hr@example.com",
            name="Dashboard HR Admin",
            password="StrongPassword123!",
            role="HR_ADMIN",
        )

        self.hr_manager = User.objects.create_user(
            email="dashboard-api-manager@example.com",
            name="Dashboard HR Manager",
            password="StrongPassword123!",
            role="HR_MANAGER",
        )

        self.employee = User.objects.create_user(
            email="dashboard-api-employee@example.com",
            name="Dashboard Employee",
            password="StrongPassword123!",
            role="EMPLOYEE",
        )

        self.inactive_hr_admin = User.objects.create_user(
            email="dashboard-api-inactive@example.com",
            name="Inactive Dashboard HR Admin",
            password="StrongPassword123!",
            role="HR_ADMIN",
            is_active=False,
        )

        self.department = Department.objects.create(
            name="Dashboard Engineering",
            code="DASH-ENG",
        )
        self.manager_position = Position.objects.create(
            title="Dashboard HR Manager",
            department=self.department,
        )

        self.manager_profile = EmployeeProfile.objects.create(
            user=self.hr_manager,
            employee_id="DASH-MANAGER-001",
            department=self.department,
            position=self.manager_position,
            hire_date=date.today(),
        )
        self.dashboard_data = {
            "workforce": {"total_employees": 10},
            "compliance": {"compliance_rate": 95},
            "onboarding": {"active_journeys": 3},
            "operations": {"pending_leave_requests": 2},
            "security": {"security_events": 1},
            "audit": {"recent_events": []},
            "risk": {"risk_level": "LOW"},
        }

    def test_hr_roles_can_access_dashboard(self):
        """All authorized HR roles can access the dashboard."""

        authorized_users = (
            self.super_admin,
            self.hr_admin,
            self.hr_manager,
        )

        for user in authorized_users:
            with self.subTest(role=user.role):
                self.client.force_authenticate(user=user)

                with patch(
                    "employees.views.DashboardService.get_dashboard",
                    return_value=self.dashboard_data,
                ):
                    response = self.client.get(self.dashboard_url)

                self.assertEqual(
                    response.status_code,
                    status.HTTP_200_OK,
                )

        self.client.force_authenticate(user=None)

    def test_dashboard_returns_expected_json_structure(self):
        """The endpoint returns aggregated dashboard data."""

        self.client.force_authenticate(user=self.hr_admin)

        with patch(
            "employees.views.DashboardService.get_dashboard",
            return_value=self.dashboard_data,
        ) as mock_service:
            response = self.client.get(self.dashboard_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data,
            self.dashboard_data,
        )

        mock_service.assert_called_once_with(
            days=7,
            recent_limit=10,
        )

    def test_dashboard_forwards_valid_filters_to_service(self):
        """Validated query parameters are forwarded to DashboardService."""

        self.client.force_authenticate(user=self.hr_admin)

        reference_date = date.today() - timedelta(days=1)

        params = {
            "department_id": self.department.pk,
            "as_of": reference_date.isoformat(),
            "days": 30,
            "recent_limit": 25,
        }

        with patch(
            "employees.views.DashboardService.get_dashboard",
            return_value=self.dashboard_data,
        ) as mock_service:
            response = self.client.get(
                self.dashboard_url,
                params,
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        mock_service.assert_called_once_with(
            department_id=self.department.pk,
            as_of=reference_date,
            days=30,
            recent_limit=25,
        )

    def test_invalid_filters_return_400(self):
        """Invalid filters are rejected before service execution."""

        self.client.force_authenticate(user=self.hr_admin)

        with patch(
            "employees.views.DashboardService.get_dashboard",
        ) as mock_service:
            response = self.client.get(
                self.dashboard_url,
                {"days": 0},
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        mock_service.assert_not_called()

    def test_nonexistent_department_returns_400(self):
        """A nonexistent department cannot be used as a filter."""

        self.client.force_authenticate(user=self.hr_admin)

        with patch(
            "employees.views.DashboardService.get_dashboard",
        ) as mock_service:
            response = self.client.get(
                self.dashboard_url,
                {"department_id": 999999},
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        mock_service.assert_not_called()

    def test_employee_cannot_access_dashboard(self):
        """Employees are denied access to the HR dashboard."""

        self.client.force_authenticate(user=self.employee)

        with patch(
            "employees.views.DashboardService.get_dashboard",
        ) as mock_service:
            response = self.client.get(self.dashboard_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        mock_service.assert_not_called()

    def test_inactive_hr_user_cannot_access_dashboard(self):
        """Inactive HR users are denied access."""

        self.client.force_authenticate(
            user=self.inactive_hr_admin,
        )

        with patch(
            "employees.views.DashboardService.get_dashboard",
        ) as mock_service:
            response = self.client.get(self.dashboard_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        mock_service.assert_not_called()

    def test_unauthenticated_user_cannot_access_dashboard(self):
        """Unauthenticated requests cannot access the dashboard."""

        with patch(
            "employees.views.DashboardService.get_dashboard",
        ) as mock_service:
            response = self.client.get(self.dashboard_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        mock_service.assert_not_called()


    def test_hr_manager_is_restricted_to_own_department(self):
        """HR managers automatically use their assigned department."""

        self.client.force_authenticate(user=self.hr_manager)

        with patch(
            "employees.views.DashboardService.get_dashboard",
            return_value=self.dashboard_data,
        ) as mock_service:
            response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        mock_service.assert_called_once_with(
            department_id=self.department.pk,
            days=7,
            recent_limit=10,
        )

    def test_hr_manager_can_explicitly_request_own_department(self):
        """HR managers can explicitly select their own department."""

        self.client.force_authenticate(user=self.hr_manager)

        with patch(
            "employees.views.DashboardService.get_dashboard",
            return_value=self.dashboard_data,
        ) as mock_service:
            response = self.client.get(
                self.dashboard_url,
                {"department_id": self.department.pk},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        mock_service.assert_called_once_with(
            department_id=self.department.pk,
            days=7,
            recent_limit=10,
        )

    def test_hr_manager_cannot_access_another_department(self):
        """HR managers cannot access another department's data."""

        another_department = Department.objects.create(
            name="Dashboard Finance",
            code="DASH-FIN",
        )

        self.client.force_authenticate(user=self.hr_manager)

        with patch(
            "employees.views.DashboardService.get_dashboard",
        ) as mock_service:
            response = self.client.get(
                self.dashboard_url,
                {"department_id": another_department.pk},
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        mock_service.assert_not_called()

    def test_security_event_details_are_redacted_for_hr_manager_only(self):
        """HR managers cannot see individual IP addresses or request paths."""

        users = (
            (self.hr_manager, True),
            (self.hr_admin, False),
            (self.super_admin, False),
        )

        for user, should_redact in users:
            with self.subTest(role=user.role):
                self.client.force_authenticate(user=user)

                dashboard_data = {
                    **self.dashboard_data,
                    "security": {
                        "security_events": 1,
                        "recent_events": [{
                            "id": 1,
                            "event_type": "LOGIN_FAILED",
                            "ip_address": "203.0.113.10",
                            "request_path": "/api/v1/accounts/login/",
                            "created_at": timezone.now(),
                        }],
                    },
                }

                with patch(
                    "employees.views.DashboardService.get_dashboard",
                    return_value=dashboard_data,
                ):
                    response = self.client.get(self.dashboard_url)

                self.assertEqual(response.status_code, status.HTTP_200_OK)

                event = response.data["security"]["recent_events"][0]

                if should_redact:
                    self.assertIsNone(event["ip_address"])
                    self.assertEqual(event["request_path"], "")
                else:
                    self.assertEqual(event["ip_address"], "203.0.113.10")
                    self.assertEqual(
                        event["request_path"],
                        "/api/v1/accounts/login/",
                    )

        self.client.force_authenticate(user=None)

    def test_security_event_details_are_redacted_for_hr_manager_only(self):
        """HR managers cannot see individual IP addresses or request paths."""

        users = (
            (self.hr_manager, True),
            (self.hr_admin, False),
            (self.super_admin, False),
        )

        for user, should_redact in users:
            with self.subTest(role=user.role):
                self.client.force_authenticate(user=user)

                dashboard_data = {
                    **self.dashboard_data,
                    "security": {
                        "security_events": 1,
                        "recent_events": [{
                            "id": 1,
                            "event_type": "LOGIN_FAILED",
                            "ip_address": "203.0.113.10",
                            "request_path": "/api/v1/accounts/login/",
                            "created_at": timezone.now(),
                        }],
                    },
                }

                with patch(
                    "employees.views.DashboardService.get_dashboard",
                    return_value=dashboard_data,
                ):
                    response = self.client.get(self.dashboard_url)

                self.assertEqual(response.status_code, status.HTTP_200_OK)

                event = response.data["security"]["recent_events"][0]

                if should_redact:
                    self.assertIsNone(event["ip_address"])
                    self.assertEqual(event["request_path"], "")
                else:
                    self.assertEqual(event["ip_address"], "203.0.113.10")
                    self.assertEqual(
                        event["request_path"],
                        "/api/v1/accounts/login/",
                    )

        self.client.force_authenticate(user=None)


    def test_hr_manager_without_profile_is_denied(self):
        """HR managers without an employee profile are denied."""

        manager_without_profile = User.objects.create_user(
            email="dashboard-manager-no-profile@example.com",
            name="Manager Without Profile",
            password="StrongPassword123!",
            role="HR_MANAGER",
        )

        self.client.force_authenticate(
            user=manager_without_profile,
        )

        with patch(
            "employees.views.DashboardService.get_dashboard",
        ) as mock_service:
            response = self.client.get(self.dashboard_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        mock_service.assert_not_called()


class RotateBankEncryptionKeyCommandTests(TestCase):
    """Tests for secure bank encryption key rotation."""

    def setUp(self):
        self.old_key = Fernet.generate_key()
        self.new_key = Fernet.generate_key()

        self.user = User.objects.create_user(
            email="rotation@example.com",
            name="Rotation Employee",
            password="TestPass123!",
        )

        self.department = Department.objects.create(
            name="Rotation Department",
            code="ROT",
        )

        self.position = Position.objects.create(
            title="Rotation Accountant",
            department=self.department,
        )

        self.employee = EmployeeProfile.objects.create(
            user=self.user,
            employee_id="EMP-ROT-001",
            department=self.department,
            position=self.position,
            hire_date=date(2026, 1, 1),
        )

        self.old_fernet = Fernet(self.old_key)
        self.new_fernet = Fernet(self.new_key)

        self.env = {
            "BANK_ENCRYPTION_KEY": self.new_key.decode(),
            "BANK_ENCRYPTION_OLD_KEYS": self.old_key.decode(),
        }

    def insert_raw_rows(self, rows):
        """Insert encrypted values directly into the database."""

        quote = connection.ops.quote_name

        table = quote("employees_bankaccount")

        columns = [
            "employee_id",
            "account_type",
            "routing_number",
            "account_number",
            "last_four",
            "is_primary",
            "is_verified",
            "created_at",
            "updated_at",
        ]

        quoted_columns = ", ".join(
            quote(column) for column in columns
        )

        placeholders = ", ".join(["%s"] * len(columns))

        sql = (
            f"INSERT INTO {table} "
            f"({quoted_columns}) VALUES ({placeholders})"
        )

        now = timezone.now()

        parameters = [
            (
                self.employee.pk,
                "CHECKING",
                routing_token,
                account_token,
                last_four,
                False,
                False,
                now,
                now,
            )
            for routing_token, account_token, last_four in rows
        ]

        with connection.cursor() as cursor:
            cursor.executemany(sql, parameters)

    def fetch_raw_rows(self):
        """Read encrypted values without ORM decryption."""

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT routing_number, account_number
                FROM employees_bankaccount
                ORDER BY id
                """
            )
            return cursor.fetchall()

    def make_old_tokens(self):
        """Create tokens encrypted with the previous key."""

        return (
            self.old_fernet.encrypt(b"123456789").decode(),
            self.old_fernet.encrypt(b"9876543210").decode(),
            "3210",
        )

    def test_dry_run_does_not_modify_database(self):
        """Dry-run validates data without changing encrypted values."""

        self.insert_raw_rows([self.make_old_tokens()])

        original_rows = self.fetch_raw_rows()

        from io import StringIO

        output = StringIO()

        with patch.dict("os.environ", self.env):
            call_command(
                "rotate_bank_encryption_key",
                dry_run=True,
                stdout=output,
            )

        self.assertEqual(
            self.fetch_raw_rows(),
            original_rows,
        )

        self.assertIn("DRY RUN", output.getvalue())
        self.assertIn("Fields that would be rotated: 2", output.getvalue())

    def test_confirm_rotates_data_to_primary_key(self):
        """Confirmed rotation must use the new primary key."""

        self.insert_raw_rows([self.make_old_tokens()])

        with patch.dict("os.environ", self.env):
            call_command("rotate_bank_encryption_key", confirm=True)

        rows = self.fetch_raw_rows()

        self.assertEqual(len(rows), 1)

        self.assertEqual(
            self.new_fernet.decrypt(rows[0][0].encode()).decode(),
            "123456789",
        )

        self.assertEqual(
            self.new_fernet.decrypt(rows[0][1].encode()).decode(),
            "9876543210",
        )

    def test_already_rotated_data_is_not_modified(self):
        """Values already using the primary key must remain unchanged."""

        routing_token = self.new_fernet.encrypt(
            b"123456789"
        ).decode()

        account_token = self.new_fernet.encrypt(
            b"9876543210"
        ).decode()

        self.insert_raw_rows([
            (routing_token, account_token, "3210")
        ])

        original_rows = self.fetch_raw_rows()

        from io import StringIO

        output = StringIO()

        with patch.dict("os.environ", self.env):
            call_command(
                "rotate_bank_encryption_key",
                confirm=True,
                stdout=output,
            )

        self.assertEqual(
            self.fetch_raw_rows(),
            original_rows,
        )

        self.assertIn("Fields rotated: 0", output.getvalue())

    def test_corrupted_data_rolls_back_entire_rotation(self):
        """A failure must roll back all earlier updates."""

        valid_row = self.make_old_tokens()

        corrupted_row = (
            "INVALID-ENCRYPTED-DATA",
            self.old_fernet.encrypt(b"9876543210").decode(),
            "3210",
        )

        self.insert_raw_rows([valid_row, corrupted_row])

        original_rows = self.fetch_raw_rows()

        with patch.dict("os.environ", self.env):
            with self.assertRaises(CommandError) as context:
                call_command(
                    "rotate_bank_encryption_key",
                    confirm=True,
                )

        self.assertEqual(
            self.fetch_raw_rows(),
            original_rows,
        )

        self.assertNotIn(
            "123456789",
            str(context.exception),
        )

        self.assertNotIn(
            "9876543210",
            str(context.exception),
        )

    def test_rotation_processes_more_than_one_batch(self):
        """Rotation must process all records beyond the batch size."""

        tokens = self.make_old_tokens()

        rows_to_insert = [
            tokens for _ in range(501)
        ]

        self.insert_raw_rows(rows_to_insert)

        from io import StringIO

        output = StringIO()

        with patch.dict("os.environ", self.env):
            call_command(
                "rotate_bank_encryption_key",
                confirm=True,
                stdout=output,
            )

        rows = self.fetch_raw_rows()

        self.assertEqual(len(rows), 501)

        self.assertIn("Rows scanned: 501", output.getvalue())
        self.assertIn("Rows updated: 501", output.getvalue())
        self.assertIn("Fields rotated: 1002", output.getvalue())

        for routing_token, account_token in rows:
            self.assertEqual(
                self.new_fernet.decrypt(
                    routing_token.encode()
                ).decode(),
                "123456789",
            )

            self.assertEqual(
                self.new_fernet.decrypt(
                    account_token.encode()
                ).decode(),
                "9876543210",
            )


class RecruitmentMetricsServiceTests(TestCase):
    """Tests for aggregate recruitment dashboard metrics."""

    def setUp(self):
        from recruitment.models import (
            ApplicationStatusHistory,
            Candidate,
            JobApplication,
            JobPosting,
        )
        from employees.services.dashboard.recruitment_metrics import (
            RecruitmentMetricsService,
        )

        self.ApplicationStatusHistory = ApplicationStatusHistory
        self.Candidate = Candidate
        self.JobApplication = JobApplication
        self.JobPosting = JobPosting
        self.RecruitmentMetricsService = RecruitmentMetricsService

        self.user = User.objects.create_user(
            email="recruitment.metrics@example.com",
            name="Recruitment Metrics Admin",
            password="StrongPassword123!",
            role=User.Role.HR_ADMIN,
        )

        self.department = Department.objects.create(
            name="Metrics HR",
            code="MET-HR",
        )
        self.position = Position.objects.create(
            title="HR Specialist",
            department=self.department,
        )

        self.other_department = Department.objects.create(
            name="Metrics Finance",
            code="MET-FIN",
        )
        self.other_position = Position.objects.create(
            title="Financial Analyst",
            department=self.other_department,
        )

        self.as_of = timezone.localdate()

    def create_posting(self, *, department=None, position=None, status=None):
        department = department or self.department
        position = position or self.position

        return self.JobPosting.objects.create(
            title=f"Posting {department.code} {status or 'DRAFT'}",
            department=department,
            position=position,
            description="Dashboard metrics test posting.",
            employment_type=self.JobPosting.EmploymentType.FULL_TIME,
            created_by=self.user,
            status=status or self.JobPosting.Status.DRAFT,
        )

    def create_application(self, *, posting, status=None, email):
        candidate = self.Candidate.objects.create(
            first_name="Metrics",
            last_name="Candidate",
            email=email,
            department=posting.department,
        )

        return self.JobApplication.objects.create(
            candidate=candidate,
            job_posting=posting,
            status=status or self.JobApplication.Status.SUBMITTED,
            privacy_consent=True,
            privacy_consent_at=timezone.now(),
        )

    def test_returns_complete_status_distributions(self):
        posting = self.create_posting(
            status=self.JobPosting.Status.OPEN
        )
        self.create_application(
            posting=posting,
            status=self.JobApplication.Status.SCREENING,
            email="screening.metrics@example.com",
        )

        result = self.RecruitmentMetricsService.get_dashboard(
            department_id=self.department.pk,
            as_of=self.as_of,
        )

        posting_counts = {
            item["status"]: item["count"]
            for item in result["job_postings"]["by_status"]
        }
        application_counts = {
            item["status"]: item["count"]
            for item in result["applications"]["by_status"]
        }

        self.assertEqual(result["job_postings"]["total"], 1)
        self.assertEqual(result["applications"]["total"], 1)

        self.assertEqual(
            posting_counts[self.JobPosting.Status.OPEN],
            1,
        )
        self.assertEqual(
            posting_counts[self.JobPosting.Status.DRAFT],
            0,
        )
        self.assertEqual(
            application_counts[self.JobApplication.Status.SCREENING],
            1,
        )
        self.assertEqual(
            application_counts[self.JobApplication.Status.HIRED],
            0,
        )

    def test_department_filter_excludes_other_department_data(self):
        own_posting = self.create_posting(
            status=self.JobPosting.Status.OPEN
        )
        other_posting = self.create_posting(
            department=self.other_department,
            position=self.other_position,
            status=self.JobPosting.Status.CLOSED,
        )

        self.create_application(
            posting=own_posting,
            email="own.metrics@example.com",
        )
        self.create_application(
            posting=other_posting,
            email="other.metrics@example.com",
        )

        result = self.RecruitmentMetricsService.get_dashboard(
            department_id=self.department.pk,
            as_of=self.as_of,
        )

        self.assertEqual(result["job_postings"]["total"], 1)
        self.assertEqual(result["applications"]["total"], 1)
        self.assertEqual(
            result["applications"]["received_in_period"],
            1,
        )

        self.assertNotIn(
            self.JobPosting.Status.CLOSED,
            [
                item["status"]
                for item in result["job_postings"]["by_status"]
                if item["count"] > 0
            ],
        )

    def test_hired_in_period_counts_status_transitions(self):
        posting = self.create_posting(
            status=self.JobPosting.Status.OPEN
        )
        application = self.create_application(
            posting=posting,
            status=self.JobApplication.Status.HIRED,
            email="hired.metrics@example.com",
        )

        self.ApplicationStatusHistory.objects.create(
            application=application,
            previous_status=self.JobApplication.Status.OFFER,
            new_status=self.JobApplication.Status.HIRED,
            changed_by=self.user,
        )

        result = self.RecruitmentMetricsService.get_dashboard(
            department_id=self.department.pk,
            as_of=self.as_of,
        )

        self.assertEqual(
            result["applications"]["by_status"][
                list(self.JobApplication.Status.values).index(
                    self.JobApplication.Status.HIRED
                )
            ]["count"],
            1,
        )
        self.assertEqual(
            result["applications"]["hired_in_period"],
            1,
        )

    def test_period_excludes_applications_and_hires_before_start_date(self):
        posting = self.create_posting(
            status=self.JobPosting.Status.OPEN
        )

        old_application = self.create_application(
            posting=posting,
            email="old.metrics@example.com",
        )
        current_application = self.create_application(
            posting=posting,
            email="current.metrics@example.com",
        )

        start_date = self.as_of - timedelta(days=6)
        start_datetime = timezone.make_aware(
            datetime.combine(start_date, datetime.min.time())
        )
        old_datetime = start_datetime - timedelta(seconds=1)

        self.JobApplication.objects.filter(
            pk=old_application.pk
        ).update(applied_at=old_datetime)

        self.JobApplication.objects.filter(
            pk=current_application.pk
        ).update(applied_at=start_datetime)

        self.ApplicationStatusHistory.objects.create(
            application=old_application,
            previous_status=self.JobApplication.Status.OFFER,
            new_status=self.JobApplication.Status.HIRED,
            changed_by=self.user,
        )
        self.ApplicationStatusHistory.objects.create(
            application=current_application,
            previous_status=self.JobApplication.Status.OFFER,
            new_status=self.JobApplication.Status.HIRED,
            changed_by=self.user,
        )

        # Move the old history entry outside the reporting period.
        self.ApplicationStatusHistory.objects.filter(
            application=old_application
        ).update(created_at=old_datetime)

        result = self.RecruitmentMetricsService.get_dashboard(
            department_id=self.department.pk,
            as_of=self.as_of,
            days=7,
        )

        self.assertEqual(
            result["applications"]["total"],
            2,
        )
        self.assertEqual(
            result["applications"]["received_in_period"],
            1,
        )
        self.assertEqual(
            result["applications"]["hired_in_period"],
            1,
        )

    def test_daily_activity_contains_only_period_applications(self):
        posting = self.create_posting(
            status=self.JobPosting.Status.OPEN
        )
        application = self.create_application(
            posting=posting,
            email="daily.metrics@example.com",
        )

        result = self.RecruitmentMetricsService.get_dashboard(
            department_id=self.department.pk,
            as_of=self.as_of,
        )

        self.assertEqual(
            sum(item["count"] for item in result["daily_activity"]),
            1,
        )
        self.assertEqual(
            result["daily_activity"][0]["count"],
            1,
        )

    def test_dashboard_does_not_expose_candidate_personal_data(self):
        posting = self.create_posting()
        self.create_application(
            posting=posting,
            email="private.metrics@example.com",
        )

        result = self.RecruitmentMetricsService.get_dashboard(
            department_id=self.department.pk,
            as_of=self.as_of,
        )

        serialized_result = str(result).lower()

        self.assertNotIn("private.metrics@example.com", serialized_result)
        self.assertNotIn("candidate", result["applications"])
        self.assertNotIn("email", result["applications"])

    def test_rejects_days_less_than_one(self):
        with self.assertRaisesMessage(
            ValueError,
            "days must be greater than or equal to 1.",
        ):
            self.RecruitmentMetricsService.get_dashboard(days=0)

class NotificationJobModelTests(TestCase):
    """Tests for durable notification jobs."""

    def test_create_notification_job_with_defaults(self):
        job = NotificationJob.objects.create(
            notification_type=NotificationJob.NotificationType.TASK_ASSIGNED,
            idempotency_key="task-assigned-123",
            payload={"task_id": "123"},
        )

        self.assertIsNotNone(job.id)
        self.assertEqual(job.status, NotificationJob.Status.PENDING)
        self.assertEqual(job.attempts, 0)
        self.assertEqual(job.max_attempts, 5)
        self.assertIsNotNone(job.next_attempt_at)
        self.assertEqual(job.payload, {"task_id": "123"})
        self.assertEqual(job.last_error, "")

    def test_idempotency_key_must_be_unique(self):
        NotificationJob.objects.create(
            notification_type=NotificationJob.NotificationType.TASK_ASSIGNED,
            idempotency_key="duplicate-event-123",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                NotificationJob.objects.create(
                    notification_type=NotificationJob.NotificationType.TASK_ASSIGNED,
                    idempotency_key="duplicate-event-123",
                )

    def test_max_attempts_must_be_positive(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                NotificationJob.objects.create(
                    notification_type=NotificationJob.NotificationType.TASK_ASSIGNED,
                    idempotency_key="invalid-max-attempts",
                    max_attempts=0,
                )

    def test_attempts_cannot_exceed_max_attempts(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                NotificationJob.objects.create(
                    notification_type=NotificationJob.NotificationType.TASK_ASSIGNED,
                    idempotency_key="invalid-attempt-count",
                    attempts=6,
                    max_attempts=5,
                )

    def test_notification_job_can_transition_to_success(self):
        job = NotificationJob.objects.create(
            notification_type=NotificationJob.NotificationType.TASK_ASSIGNED,
            idempotency_key="successful-notification",
        )

        job.status = NotificationJob.Status.SUCCESS
        job.save(update_fields=["status", "updated_at"])

        job.refresh_from_db()
        self.assertEqual(job.status, NotificationJob.Status.SUCCESS)

    def test_notification_job_can_store_correlation_id(self):
        correlation_id = uuid.uuid4()

        job = NotificationJob.objects.create(
            notification_type=NotificationJob.NotificationType.TASK_OVERDUE,
            idempotency_key="overdue-task-123",
            correlation_id=correlation_id,
        )

        self.assertEqual(job.correlation_id, correlation_id)

class NotificationWorkerTests(TestCase):
    """Tests for asynchronous notification job processing."""

    def setUp(self):
        from employees.services.onboarding_notifications import (
            OnboardingNotificationService,
        )

        self.admin = User.objects.create_user(
            email="worker-admin@example.com",
            name="Worker Admin",
            password="TestPassword123!",
            role="HR_ADMIN",
            is_active=True,
        )

        self.employee_user = User.objects.create_user(
            email="worker-employee@example.com",
            name="Worker Employee",
            password="TestPassword123!",
            role="EMPLOYEE",
            is_active=True,
        )

        department = Department.objects.create(
            name="Worker Department",
            code="WORKER",
        )
        position = Position.objects.create(
            title="Worker Specialist",
            department=department,
        )
        employee = EmployeeProfile.objects.create(
            user=self.employee_user,
            employee_id="WORKER-001",
            department=department,
            position=position,
            hire_date=date.today(),
        )
        self.profile = employee
        from employees.models import (
            OnboardingActivityTemplate,
            OnboardingPhase,
            OnboardingTemplate,
        )
        from employees.services.onboarding import OnboardingService

        template = OnboardingTemplate.objects.create(
            name="Worker test template",
            description="Worker test",
            version=1,
            created_by=self.admin,
        )
        phase = OnboardingPhase.objects.create(
            template=template,
            name="Worker phase",
            description="Worker phase",
            order=1,
        )
        OnboardingActivityTemplate.objects.create(
            phase=phase,
            name="Worker task",
            description="Worker task",
            order=1,
            is_required=True,
            default_due_days=3,
        )

        OnboardingService.publish_template(template.pk)
        self.journey = OnboardingService.create_journey(
            employee_id=employee.pk,
            template_id=template.pk,
            created_by=self.admin,
        )
        self.task = self.journey.tasks.get()
        self.task.assigned_to = self.employee_user
        self.task.save(update_fields=["assigned_to"])

        OnboardingNotificationService.notify_task_assigned(
            task_id=self.task.pk,
        )
        self.job = NotificationJob.objects.get(
            notification_type=NotificationJob.NotificationType.TASK_ASSIGNED,
        )

    @patch("employees.services.notification_worker.send_mail")
    def test_worker_sends_assignment_notification(self, mock_send_mail):
        from employees.services.notification_worker import (
            NotificationWorker,
        )

        mock_send_mail.return_value = 1

        result = NotificationWorker.process_batch(batch_size=1)

        self.job.refresh_from_db()

        self.assertEqual(result["processed"], 1)
        self.assertEqual(self.job.status, NotificationJob.Status.SUCCESS)
        mock_send_mail.assert_called_once()

    @patch("employees.services.notification_worker.send_mail")
    def test_reassigned_task_does_not_send_to_old_recipient(
        self,
        mock_send_mail,
    ):
        from employees.services.notification_worker import (
            NotificationWorker,
        )

        another_user = User.objects.create_user(
            email="worker-another@example.com",
            name="Another Employee",
            password="TestPassword123!",
            role="EMPLOYEE",
            is_active=True,
        )

        self.task.assigned_to = another_user
        self.task.save(update_fields=["assigned_to"])

        result = NotificationWorker.process_batch(batch_size=1)

        self.job.refresh_from_db()

        self.assertEqual(result["processed"], 1)
        self.assertEqual(self.job.status, NotificationJob.Status.SUCCESS)
        mock_send_mail.assert_not_called()

    @patch("employees.services.notification_worker.send_mail")
    def test_email_failure_schedules_retry(self, mock_send_mail):
        from employees.services.notification_worker import (
            NotificationWorker,
        )

        mock_send_mail.side_effect = RuntimeError("SMTP unavailable")

        before = timezone.now()
        result = NotificationWorker.process_batch(batch_size=1)

        self.job.refresh_from_db()

        self.assertEqual(result["processed"], 1)
        self.assertEqual(self.job.status, NotificationJob.Status.PENDING)
        self.assertEqual(self.job.attempts, 1)
        self.assertEqual(self.job.last_error, "RuntimeError")
        self.assertGreater(self.job.next_attempt_at, before)

    @patch("employees.services.notification_worker.send_mail")
    def test_terminal_failure_creates_audit_event(self, mock_send_mail):
        from employees.services.notification_worker import (
            NotificationWorker,
        )
        from employees.models import WorkflowExecutionLog

        self.job.attempts = self.job.max_attempts - 1
        self.job.save(update_fields=["attempts"])

        mock_send_mail.side_effect = RuntimeError("SMTP unavailable")

        result = NotificationWorker.process_batch(batch_size=1)

        self.job.refresh_from_db()

        self.assertEqual(result["processed"], 1)
        self.assertEqual(self.job.status, NotificationJob.Status.FAILED)

        event = WorkflowExecutionLog.objects.get(
            event_type="NOTIFICATION_FAILED",
        )
        self.assertEqual(
            event.correlation_id,
            self.job.correlation_id,
        )
        self.assertEqual(
            event.outcome,
            WorkflowExecutionLog.Outcome.FAILURE,
        )
        self.assertNotIn(
            self.employee_user.email,
            str(event.details),
        )
        self.assertNotIn(
            "Worker task",
            str(event.details),
        )

    def test_stale_processing_job_is_recovered(self):
        from employees.services.notification_worker import (
            NotificationWorker,
        )

        self.job.status = NotificationJob.Status.PROCESSING
        self.job.attempts = 1
        self.job.save(update_fields=["status", "attempts"])

        NotificationJob.objects.filter(
            pk=self.job.pk,
        ).update(
            updated_at=timezone.now() - timedelta(minutes=11),
        )
        claimed_job = NotificationWorker._claim_next_job()

        self.job.refresh_from_db()

        self.assertIsNotNone(claimed_job)
        self.assertEqual(claimed_job.pk, self.job.pk)
        self.assertEqual(
            self.job.status,
            NotificationJob.Status.PROCESSING,
        )
        self.assertEqual(self.job.attempts, 2)

    def test_stale_processing_job_exhausted_attempts_creates_audit_event(self):
        from employees.services.notification_worker import (
            NotificationWorker,
        )
        from employees.models import WorkflowExecutionLog

        self.job.status = NotificationJob.Status.PROCESSING
        self.job.attempts = self.job.max_attempts
        self.job.save(update_fields=["status", "attempts"])

        NotificationJob.objects.filter(
            pk=self.job.pk,
        ).update(
            updated_at=timezone.now() - timedelta(minutes=11),
        )

        claimed_job = NotificationWorker._claim_next_job()

        self.job.refresh_from_db()

        self.assertIsNone(claimed_job)
        self.assertEqual(
            self.job.status,
            NotificationJob.Status.FAILED,
        )
        self.assertEqual(
            self.job.attempts,
            self.job.max_attempts,
        )

        event = WorkflowExecutionLog.objects.get(
            event_type="NOTIFICATION_FAILED",
        )
        self.assertEqual(
            event.correlation_id,
            self.job.correlation_id,
        )
        self.assertEqual(
            event.outcome,
            WorkflowExecutionLog.Outcome.FAILURE,
        )
        self.assertEqual(
            event.details["reason"],
            "WORKER_LEASE_EXPIRED",
        )
        self.assertEqual(
            event.details["notification_type"],
            self.job.notification_type,
        )


    @patch("employees.services.notification_worker.send_mail")
    def test_inactive_recipient_does_not_receive_notification(
        self,
        mock_send_mail,
    ):
        from employees.services.notification_worker import (
            NotificationWorker,
        )

        self.employee_user.is_active = False
        self.employee_user.save(update_fields=["is_active"])

        result = NotificationWorker.process_batch(batch_size=1)

        self.job.refresh_from_db()

        self.assertEqual(result["processed"], 1)
        self.assertEqual(self.job.status, NotificationJob.Status.SUCCESS)
        mock_send_mail.assert_not_called()

    @patch("employees.services.notification_worker.send_mail")
    def test_task_completed_notification_is_sent_to_journey_creator(
        self,
        mock_send_mail,
    ):
        from employees.services.notification_worker import (
            NotificationWorker,
        )
        from employees.models import OnboardingTask

        self.task.status = OnboardingTask.Status.COMPLETED
        self.task.save(update_fields=["status"])

        self.job.notification_type = (
            NotificationJob.NotificationType.TASK_COMPLETED
        )
        self.job.payload = {
            "task_id": str(self.task.pk),
            "recipient_user_id": str(self.admin.pk),
        }
        self.job.save(update_fields=["notification_type", "payload"])

        mock_send_mail.return_value = 1

        result = NotificationWorker.process_batch(batch_size=1)

        self.job.refresh_from_db()

        self.assertEqual(result["processed"], 1)
        self.assertEqual(self.job.status, NotificationJob.Status.SUCCESS)
        mock_send_mail.assert_called_once()

        self.assertEqual(
            mock_send_mail.call_args.kwargs["recipient_list"],
            [self.admin.email],
        )

    @patch("employees.services.notification_worker.send_mail")
    def test_overdue_task_notification_is_sent(self, mock_send_mail):
        from employees.services.notification_worker import (
            NotificationWorker,
        )

        self.task.due_date = timezone.localdate() - timedelta(days=1)
        self.task.save(update_fields=["due_date"])

        self.job.notification_type = (
            NotificationJob.NotificationType.TASK_OVERDUE
        )
        self.job.payload = {
            "task_id": str(self.task.pk),
            "recipient_user_id": str(self.employee_user.pk),
        }
        self.job.save(update_fields=["notification_type", "payload"])

        mock_send_mail.return_value = 1

        result = NotificationWorker.process_batch(batch_size=1)

        self.job.refresh_from_db()

        self.assertEqual(result["processed"], 1)
        self.assertEqual(self.job.status, NotificationJob.Status.SUCCESS)
        mock_send_mail.assert_called_once()

    @patch("employees.services.notification_worker.send_mail")
    def test_expiring_verified_document_notification_is_sent(
        self,
        mock_send_mail,
    ):
        from employees.services.notification_worker import (
            NotificationWorker,
        )

        document = HRDocument.objects.create(
            employee=self.profile,
            title="Worker test document",
            document_type=HRDocument.DocumentType.EMPLOYMENT_CONTRACT,
            original_filename="worker-contract.pdf",
            storage_key=(
                f"hr-documents/notification-worker/{self.job.pk}/contract.pdf"
            ),
            mime_type="application/pdf",
            size_bytes=1024,
            uploaded_by=self.admin,
            status=HRDocument.Status.VERIFIED,
            expires_at=timezone.localdate() + timedelta(days=10),
        )

        self.job.notification_type = (
            NotificationJob.NotificationType.DOCUMENT_EXPIRING
        )
        self.job.payload = {
            "document_id": str(document.pk),
            "recipient_user_id": str(self.employee_user.pk),
        }
        self.job.save(update_fields=["notification_type", "payload"])

        mock_send_mail.return_value = 1

        result = NotificationWorker.process_batch(batch_size=1)

        self.job.refresh_from_db()

        self.assertEqual(result["processed"], 1)
        self.assertEqual(self.job.status, NotificationJob.Status.SUCCESS)
        mock_send_mail.assert_called_once()

    @patch("employees.services.notification_worker.send_mail")
    def test_non_verified_document_does_not_trigger_email(
        self,
        mock_send_mail,
    ):
        from employees.services.notification_worker import (
            NotificationWorker,
        )

        document = HRDocument.objects.create(
            employee=self.profile,
            title="Archived worker document",
            document_type=HRDocument.DocumentType.EMPLOYMENT_CONTRACT,
            original_filename="archived-contract.pdf",
            storage_key=(
                f"hr-documents/notification-worker/{self.job.pk}/archived.pdf"
            ),
            mime_type="application/pdf",
            size_bytes=1024,
            uploaded_by=self.admin,
            status=HRDocument.Status.ARCHIVED,
            expires_at=timezone.localdate() + timedelta(days=10),
        )

        self.job.notification_type = (
            NotificationJob.NotificationType.DOCUMENT_EXPIRING
        )
        self.job.payload = {
            "document_id": str(document.pk),
            "recipient_user_id": str(self.employee_user.pk),
        }
        self.job.save(update_fields=["notification_type", "payload"])

        result = NotificationWorker.process_batch(batch_size=1)

        self.job.refresh_from_db()

        self.assertEqual(result["processed"], 1)
        self.assertEqual(self.job.status, NotificationJob.Status.SUCCESS)
        mock_send_mail.assert_not_called()

    @patch("employees.services.notification_worker.send_mail")
    def test_retry_failure_is_reported_as_retry_scheduled(
        self,
        mock_send_mail,
    ):
        from employees.services.notification_worker import (
            NotificationWorker,
        )
        mock_send_mail.side_effect = RuntimeError("SMTP unavailable")

        result = NotificationWorker.process_batch(batch_size=1)

        self.assertEqual(
            result["results"],
            ["RETRY_SCHEDULED"],
        )

    @patch("employees.services.notification_worker.send_mail")
    def test_terminal_failure_is_reported_as_failed(
        self,
        mock_send_mail,
    ):
        from employees.services.notification_worker import (
            NotificationWorker,
        )
        self.job.attempts = self.job.max_attempts - 1
        self.job.save(update_fields=["attempts"])

        mock_send_mail.side_effect = RuntimeError("SMTP unavailable")

        result = NotificationWorker.process_batch(batch_size=1)

        self.assertEqual(
            result["results"],
            ["FAILED"],
        )

class ProcessNotificationsCommandTests(TestCase):
    """Tests for the process_notifications management command."""

    @patch(
        "employees.management.commands.process_notifications.connection.vendor",
        "sqlite",
    )
    @patch(
        "employees.management.commands.process_notifications.NotificationWorker.process_batch"
    )
    def test_processes_pending_notifications(self, mock_process_batch):
        """The command processes queued notifications."""

        mock_process_batch.return_value = {
            "processed": 2,
            "results": ["SUCCESS", "RETRY_SCHEDULED"],
        }

        from io import StringIO

        output = StringIO()

        call_command(
            "process_notifications",
            batch_size=10,
            max_batches=3,
            stdout=output,
        )

        mock_process_batch.assert_called_once_with(batch_size=10)
        self.assertIn("processed=2", output.getvalue())
        self.assertIn("retries_scheduled=1", output.getvalue())
        self.assertIn("failed=0", output.getvalue())

    @patch(
        "employees.management.commands.process_notifications.connection.vendor",
        "sqlite",
    )
    @patch(
        "employees.management.commands.process_notifications.NotificationWorker.process_batch"
    )
    def test_processes_multiple_batches_until_queue_is_empty(
        self,
        mock_process_batch,
    ):
        """The command stops when a batch contains fewer jobs than requested."""

        mock_process_batch.side_effect = [
            {
                "processed": 2,
                "results": ["SUCCESS", "SUCCESS"],
            },
            {
                "processed": 1,
                "results": ["SUCCESS"],
            },
        ]

        call_command(
            "process_notifications",
            batch_size=2,
            max_batches=5,
        )

        self.assertEqual(mock_process_batch.call_count, 2)

    def test_rejects_invalid_batch_size(self):
        """A batch size below one must be rejected."""

        with self.assertRaises(CommandError):
            call_command(
                "process_notifications",
                batch_size=0,
            )

    def test_rejects_invalid_max_batches(self):
        """A maximum batch count below one must be rejected."""

        with self.assertRaises(CommandError):
            call_command(
                "process_notifications",
                max_batches=0,
            )

    @patch(
        "employees.management.commands.process_notifications.connection.vendor",
        "sqlite",
    )
    @patch(
        "employees.management.commands.process_notifications.NotificationWorker.process_batch"
    )
    @patch(
        "employees.management.commands.process_notifications.OnboardingNotificationService.enqueue_expiring_document_notifications"
    )
    @patch(
        "employees.management.commands.process_notifications.OnboardingNotificationService.enqueue_overdue_task_notifications"
    )
    def test_enqueue_daily_creates_both_notification_types(
        self,
        mock_overdue,
        mock_expiring,
        mock_process_batch,
    ):
        """Daily mode invokes both notification producers."""

        mock_overdue.return_value = 3
        mock_expiring.return_value = 2
        mock_process_batch.return_value = {
            "processed": 0,
            "results": [],
        }

        from io import StringIO

        output = StringIO()

        call_command(
            "process_notifications",
            enqueue_daily=True,
            stdout=output,
        )

        mock_overdue.assert_called_once_with()
        mock_expiring.assert_called_once_with()
        mock_process_batch.assert_called_once()

        self.assertIn("overdue_tasks=3", output.getvalue())
        self.assertIn("expiring_documents=2", output.getvalue())
        state = NotificationSchedulerState.objects.get(
            name="notification_scheduler",
        )

        self.assertEqual(
            state.last_daily_enqueue_date,
            timezone.localdate(
                timezone=ZoneInfo("America/New_York"),
            )
        )

    @patch(
        "employees.management.commands.process_notifications.connection.vendor",
        "sqlite",
    )
    @patch(
        "employees.management.commands.process_notifications.NotificationWorker.process_batch"
    )
    @patch(
        "employees.management.commands.process_notifications.OnboardingNotificationService.enqueue_expiring_document_notifications"
    )
    @patch(
        "employees.management.commands.process_notifications.OnboardingNotificationService.enqueue_overdue_task_notifications"
    )
    def test_daily_enqueue_is_skipped_when_already_completed_today(
        self,
        mock_overdue,
        mock_expiring,
        mock_process_batch,
    ):
        """Daily producers must not run twice on the same day."""

        today = timezone.localdate(timezone=ZoneInfo("America/New_York"),)

        NotificationSchedulerState.objects.create(
            name="notification_scheduler",
            last_daily_enqueue_date=today,
        )

        mock_process_batch.return_value = {
            "processed": 0,
            "results": [],
        }

        from io import StringIO

        output = StringIO()

        call_command(
            "process_notifications",
            enqueue_daily=True,
            stdout=output,
        )

        mock_overdue.assert_not_called()
        mock_expiring.assert_not_called()
        mock_process_batch.assert_called_once()

        self.assertIn(
            "Daily notifications already queued for",
            output.getvalue(),
        )

    @patch(
        "employees.management.commands.process_notifications.connection.vendor",
        "sqlite",
    )
    @patch(
        "employees.management.commands.process_notifications.NotificationWorker.process_batch"
    )
    @patch(
        "employees.management.commands.process_notifications.OnboardingNotificationService.enqueue_expiring_document_notifications"
    )
    @patch(
        "employees.management.commands.process_notifications.OnboardingNotificationService.enqueue_overdue_task_notifications"
    )
    def test_daily_enqueue_failure_does_not_persist_date(
        self,
        mock_overdue,
        mock_expiring,
        mock_process_batch,
    ):
        """A failed daily enqueue must not persist a successful date."""

        mock_overdue.return_value = 3
        mock_expiring.side_effect = RuntimeError("Test enqueue failure")

        with self.assertRaises(CommandError):
            call_command(
                "process_notifications",
                enqueue_daily=True,
            )

        self.assertFalse(
            NotificationSchedulerState.objects.filter(
                name="notification_scheduler",
            ).exists()
        )

        mock_overdue.assert_called_once_with()
        mock_expiring.assert_called_once_with()
        mock_process_batch.assert_not_called()

    @patch(
        "employees.management.commands.process_notifications.connection.vendor",
        "sqlite",
    )
    @patch(
        "employees.management.commands.process_notifications.NotificationWorker.process_batch"
    )
    def test_worker_exception_is_reported_as_command_error(
        self,
        mock_process_batch,
    ):
        """Unexpected worker errors must fail the management command."""

        mock_process_batch.side_effect = RuntimeError("Internal test error")

        with self.assertRaises(CommandError) as context:
            call_command("process_notifications")

        self.assertEqual(
            str(context.exception),
            "Notification processing failed.",
        )
        self.assertNotIn("Internal test error", str(context.exception))


    @patch(
        "employees.management.commands.process_notifications.connection.vendor",
        "postgresql",
    )
    @patch(
        "employees.management.commands.process_notifications.connection.cursor"
    )
    @patch(
        "employees.management.commands.process_notifications.NotificationWorker.process_batch"
    )
    def test_skips_when_advisory_lock_is_unavailable(
        self,
        mock_process_batch,
        mock_cursor,
    ):
        """The command skips processing when another worker holds the lock."""

        cursor = mock_cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (False,)

        call_command("process_notifications")

        cursor.execute.assert_called_once_with(
            "SELECT pg_try_advisory_lock(%s)",
            [726194003],
        )
        mock_process_batch.assert_not_called()

    @patch(
        "employees.management.commands.process_notifications.connection.vendor",
        "postgresql",
    )
    @patch(
        "employees.management.commands.process_notifications.connection.cursor"
    )
    @patch(
        "employees.management.commands.process_notifications.NotificationWorker.process_batch"
    )
    def test_releases_advisory_lock_after_success(
        self,
        mock_process_batch,
        mock_cursor,
    ):
        """The command releases its advisory lock after successful processing."""

        cursor = mock_cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (True,)
        mock_process_batch.return_value = {
            "processed": 0,
            "results": [],
        }

        call_command("process_notifications")

        cursor.execute.assert_any_call(
            "SELECT pg_try_advisory_lock(%s)",
            [726194003],
        )
        cursor.execute.assert_any_call(
            "SELECT pg_advisory_unlock(%s)",
            [726194003],
        )

    @patch(
        "employees.management.commands.process_notifications.connection.vendor",
        "postgresql",
    )
    @patch(
        "employees.management.commands.process_notifications.connection.cursor"
    )
    @patch(
        "employees.management.commands.process_notifications.NotificationWorker.process_batch"
    )
    def test_releases_advisory_lock_after_worker_failure(
        self,
        mock_process_batch,
        mock_cursor,
    ):
        """The command releases its advisory lock even after a worker failure."""

        cursor = mock_cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (True,)
        mock_process_batch.side_effect = RuntimeError("Internal test error")

        with self.assertRaises(CommandError):
            call_command("process_notifications")

        cursor.execute.assert_any_call(
            "SELECT pg_advisory_unlock(%s)",
            [726194003],
        )
