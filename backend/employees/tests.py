from django.test import TestCase
from datetime import date

from accounts.models import User, SecurityEvent

from rest_framework import status
from rest_framework.test import APIClient
from django.db.models.deletion import ProtectedError
from django.db import IntegrityError
from django.db import connection
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
from .serializers import (
    BankAccountSerializer,
    EmployeeProfileSerializer,
    LeaveRequestSerializer,
    PerformanceReviewSerializer,
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
)

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
            len(response.data),
            1,
        )

        self.assertEqual(
            response.data[0]["employee_id"],
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
            len(response.data),
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
            len(response.data),
            2,
        )

        self.assertEqual(
            response.data[0]["employee_id"],
            "EMP-002",
        )

        self.assertEqual(
            response.data[1]["employee_id"],
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
            len(response.data),
            2,
        )

        returned_ids = [
            profile["employee_id"]
            for profile in response.data
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
            len(response.data),
            2,
        )

        returned_ids = [
            profile["employee_id"]
            for profile in response.data
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
            for profile in response.data
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
            len(response.data),
            1,
        )

        self.assertEqual(
            response.data[0]["employee_id"],
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
            len(response.data),
            2,
        )

        self.assertEqual(
            response.data[0]["employee_id"],
            "EMP-002",
        )

        self.assertEqual(
            response.data[1]["employee_id"],
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
            len(response.data),
            1,
        )

        self.assertEqual(
            response.data[0]["employee_id"],
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
            len(response.data),
            1,
        )

        self.assertEqual(
            response.data[0]["employee_id"],
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
            len(response.data),
            1,
        )

        self.assertEqual(
            response.data[0]["employee_id"],
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
            len(response.data),
            2,
        )

        self.assertEqual(
            response.data[0]["employee_id"],
            "EMP-001",
        )

        self.assertEqual(
            response.data[1]["employee_id"],
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
            len(response.data),
            1,
        )

        self.assertEqual(
            response.data[0]["employee"],
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

    def test_hr_manager_can_list_all_leave_requests(self):
        """HR managers can view all leave requests."""

        self.authenticate(self.hr_manager)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            2,
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
            len(response.data),
            1,
        )

        self.assertEqual(
            response.data[0]["id"],
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
            len(response.data),
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
            len(response.data),
            1,
        )

        self.assertEqual(
            response.data[0]["id"],
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
            len(response.data),
            1,
        )

        self.assertEqual(
            response.data[0]["id"],
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
            len(response.data),
            1,
        )

        self.assertEqual(
            response.data[0]["id"],
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
            len(response.data),
            2,
        )

        self.assertEqual(
            response.data[0]["id"],
            self.leave_request.id,
        )

        self.assertEqual(
            response.data[1]["id"],
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
            len(response.data),
            2,
        )

        self.assertEqual(
            response.data[0]["id"],
            self.other_leave_request.id,
        )

        self.assertEqual(
            response.data[1]["id"],
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
            len(response.data),
            2,
        )

        returned_ids = [
            leave["id"]
            for leave in response.data
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
            len(response.data),
            2,
        )

        returned_ids = [
            leave["id"]
            for leave in response.data
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
            len(response.data),
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
            len(response.data),
            1,
        )

        self.assertEqual(
            response.data[0]["id"],
            self.leave_request.id,
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

        self.bank_account = BankAccount.objects.create(
            employee=self.other_employee,
            account_type="CHECKING",
            routing_number="021000021",
            account_number="123456789123",
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
            len(response.data),
            1,
        )

        self.assertEqual(
            response.data[0]["account_type"],
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
            len(response.data),
            1,
        )

        self.assertTrue(
            response.data[0]["is_primary"],
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
            len(response.data),
            1,
        )

        self.assertTrue(
            response.data[0]["is_verified"],
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
            len(response.data),
            1,
        )

        self.assertEqual(
            response.data[0]["id"],
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
            len(response.data),
            2,
        )

        returned_ids = [
            account["id"]
            for account in response.data
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
            len(response.data),
            2,
        )

        returned_ids = [
            account["id"]
            for account in response.data
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
            len(response.data),
            2,
        )

        returned_last_four = [
            account["last_four"]
            for account in response.data
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
            len(response.data),
            1,
        )

        self.assertEqual(
            response.data[0]["id"],
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
            len(response.data),
            1,
        )
        self.assertEqual(
            response.data[0]["id"],
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
            len(response.data),
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
            len(response.data),
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
            len(response.data),
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
            len(response.data),
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
            len(response.data),
            2,
        )
        self.assertEqual(
            response.data[0]["id"],
            self.review.id,
        )
        self.assertEqual(
            response.data[1]["id"],
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
            len(response.data),
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
            len(response.data),
            2,
        )
        self.assertEqual(
            response.data[0]["id"],
            self.other_review.id,
        )
        self.assertEqual(
            response.data[1]["id"],
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
            len(response.data),
            2,
        )
        self.assertEqual(
            response.data[0]["id"],
            self.review.id,
        )
        self.assertEqual(
            response.data[1]["id"],
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
            len(response.data),
            2,
        )
        self.assertEqual(
            response.data[0]["id"],
            self.review.id,
        )
        self.assertEqual(
            response.data[1]["id"],
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
            len(response.data),
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
            len(response.data),
            1,
        )
        self.assertEqual(
            response.data[0]["id"],
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
