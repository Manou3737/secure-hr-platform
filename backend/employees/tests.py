from django.test import TestCase
from datetime import date

from django.test import TestCase

from accounts.models import User, SecurityEvent
from .models import EmployeeProfile
from .serializers import EmployeeProfileSerializer

from rest_framework import status
from rest_framework.test import APIClient

class EmployeeProfileModelTests(TestCase):
    """Tests for the EmployeeProfile model."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="employee@example.com",
            name="John Employee",
            password="StrongPassword123!",
        )

        self.profile = EmployeeProfile.objects.create(
            user=self.user,
            employee_id="EMP-001",
            department="Engineering",
            job_title="Software Engineer",
            phone="401-555-0100",
            hire_date=date(2026, 1, 15),
        )

    def test_employee_profile_is_created(self):
        self.assertEqual(
            self.profile.employee_id,
            "EMP-001",
        )
        self.assertEqual(
            self.profile.department,
            "Engineering",
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
                department="HR",
                job_title="HR Specialist",
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

        self.profile = EmployeeProfile.objects.create(
            user=self.user,
            employee_id="EMP-001",
            department="Engineering",
            job_title="Software Engineer",
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
            "job_title",
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

        self.profile = EmployeeProfile.objects.create(
            user=self.employee,
            employee_id="EMP-001",
            department="Engineering",
            job_title="Software Engineer",
            hire_date=date(2026, 1, 15),
        )

        self.other_profile = EmployeeProfile.objects.create(
            user=self.other_employee,
            employee_id="EMP-002",
            department="HR",
            job_title="HR Specialist",
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
                "department": "Finance",
                "job_title": "Financial Analyst",
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
                "department": "Finance",
                "job_title": "Financial Analyst",
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
                "department": "Finance",
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
                "department": "Finance",
                "job_title": "Financial Analyst",
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
                "department": "Engineering",
                "job_title": "Backend Developer",
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
                "job_title": "Senior Software Engineer",
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
            f"/api/v1/employees/{self.profile.id}/",
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
            f"/api/v1/employees/{profile_id}/",
        )
        self.assertIn(
            employee_id,
            event.details,
        )
