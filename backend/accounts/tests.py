from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from pathlib import Path
from tempfile import TemporaryDirectory

from .models import SecurityEvent, User
from django.test import override_settings
from accounts.views import LoginViewSet, LoginRateThrottle
from datetime import timedelta
from unittest.mock import patch
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
import base64
import json

class AuthenticationAPITests(APITestCase):
    """Tests for registration and JWT authentication."""

    def setUp(self):
        self.user_data = {
            "email": "testuser@example.com",
            "name": "Test User",
            "password": "StrongPassword123!",
        }

        self.user = User.objects.create_user(
            email=self.user_data["email"],
            name=self.user_data["name"],
            password=self.user_data["password"],
        )

    def test_user_registration(self):
        response = self.client.post(
            reverse("register"),
            {
                "email": "newuser@example.com",
                "name": "New User",
                "password": "StrongPassword456!",
                "password_confirm": "StrongPassword456!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(email="newuser@example.com")

        self.assertEqual(user.name, "New User")
        self.assertTrue(
            user.check_password("StrongPassword456!")
        )

    def test_registration_rejects_weak_password(self):
        response = self.client.post(
            reverse("register"),
            {
                "email": "weak@example.com",
                "name": "Weak User",
                "password": "123",
                "password_confirm": "123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_registration_rejects_password_mismatch(self):
        response = self.client.post(
            reverse("register"),
            {
                "email": "mismatch@example.com",
                "name": "Mismatch User",
                "password": "StrongPassword123!",
                "password_confirm": "DifferentPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_with_valid_credentials(self):
        response = self.client.post(
            reverse("login"),
            {
                "email": self.user_data["email"],
                "password": self.user_data["password"],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        event = SecurityEvent.objects.get(
            event_type="LOGIN_SUCCESS"
        )

        self.assertEqual(
            event.user,
            self.user,
        )
        self.assertEqual(
            event.ip_address,
            "127.0.0.1",
        )
        self.assertEqual(
            event.request_path,
            reverse("login"),
        )
        self.assertIn(
            "successfully",
            event.details,
        )

    def test_login_does_not_set_authentication_cookies(self):
        response = self.client.post(
            reverse("login"),
            {
                "email": self.user_data["email"],
                "password": self.user_data["password"],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertNotIn(
            "sessionid",
            response.cookies,
        )

        self.assertNotIn(
            "csrftoken",
            response.cookies,
        )

    def test_failed_login_is_written_to_siem_log(self):
        with TemporaryDirectory() as temp_directory:
            with override_settings(
                BASE_DIR=Path(temp_directory)
            ):
                response = self.client.post(
                    reverse("login"),
                    {
                        "email": self.user_data["email"],
                        "password": "WrongPassword123!",
                    },
                    format="json",
                )

                self.assertEqual(
                    response.status_code,
                    status.HTTP_400_BAD_REQUEST,
                )

                log_file = (
                    Path(temp_directory)
                    / "logs"
                    / "security-events.jsonl"
                )

                self.assertTrue(
                    log_file.exists()
                )

                log_content = log_file.read_text(
                    encoding="utf-8"
                )

                self.assertIn(
                    "LOGIN_FAILED",
                    log_content,
                )

                self.assertIn(
                    "Failed login attempt",
                    log_content,
                )

    def test_siem_log_contains_valid_json_lines(self):
        with TemporaryDirectory() as temp_directory:
            with override_settings(
                BASE_DIR=Path(temp_directory)
            ):
                response = self.client.post(
                    reverse("login"),
                    {
                        "email": self.user_data["email"],
                        "password": "WrongPassword123!",
                    },
                    format="json",
                )

                self.assertEqual(
                    response.status_code,
                    status.HTTP_400_BAD_REQUEST,
                )

                log_file = (
                    Path(temp_directory)
                    / "logs"
                    / "security-events.jsonl"
                )

                self.assertTrue(log_file.exists())

                lines = log_file.read_text(
                    encoding="utf-8"
                ).splitlines()

                self.assertGreater(len(lines), 0)

                for line in lines:
                    with self.subTest(line=line):
                        payload = json.loads(line)

                        self.assertIsInstance(payload, dict)
                        self.assertIn("@timestamp", payload)
                        self.assertIn("event.action", payload)
                        self.assertIn("source.ip", payload)
                        self.assertIn("url.path", payload)
                        self.assertIn("message", payload)

                self.assertTrue(
                    any(
                        json.loads(line).get("event.action")
                        == "LOGIN_FAILED"
                        for line in lines
                    )
                )

    def test_siem_log_encodes_newlines_inside_json_messages(self):
        with TemporaryDirectory() as temp_directory:
            with override_settings(
                BASE_DIR=Path(temp_directory)
            ):
                from rest_framework.test import APIRequestFactory

                from accounts.siem import create_security_event

                request = APIRequestFactory().post(
                    "/api/test/",
                    {},
                    format="json",
                    HTTP_USER_AGENT="test-agent",
                )
                request.META["REMOTE_ADDR"] = "127.0.0.1"

                create_security_event(
                    request=request,
                    event_type="LOGIN_FAILED",
                    details='Failed login.\n{"event.action":"LOGIN_SUCCESS"}',
                )

                log_file = (
                    Path(temp_directory)
                    / "logs"
                    / "security-events.jsonl"
                )

                lines = log_file.read_text(
                    encoding="utf-8"
                ).splitlines()

                self.assertEqual(len(lines), 1)

                payload = json.loads(lines[0])

                self.assertEqual(
                    payload["message"],
                    'Failed login.\n{"event.action":"LOGIN_SUCCESS"}',
                )
                self.assertEqual(
                    payload["event.action"],
                    "LOGIN_FAILED",
                )

    @patch(
        "accounts.siem._write_siem_log",
        side_effect=OSError("Simulated SIEM file write failure"),
    )
    def test_siem_file_write_failure_preserves_database_event(
        self,
        mock_write_siem_log,
    ):
        from rest_framework.test import APIRequestFactory

        from accounts.siem import create_security_event

        request = APIRequestFactory().post(
            "/api/test/",
            {},
            format="json",
        )
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        with self.assertLogs(
            "accounts.siem",
            level="ERROR",
        ) as captured_logs:
            event = create_security_event(
                request=request,
                event_type="LOGIN_FAILED",
                details="Failed login attempt.",
                user=self.user,
            )

        self.assertTrue(
            SecurityEvent.objects.filter(pk=event.pk).exists()
        )
        self.assertIn(
            "Failed to write security event to the SIEM file",
            "\n".join(captured_logs.output),
        )
        mock_write_siem_log.assert_called_once_with(event)

    def test_login_does_not_trust_spoofed_forwarded_ip(self):
        response = self.client.post(
            reverse("login"),
            {
                "email": self.user_data["email"],
                "password": "WrongPassword123!",
            },
            format="json",
            HTTP_X_FORWARDED_FOR="203.0.113.99",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        event = SecurityEvent.objects.filter(
            event_type="LOGIN_FAILED"
        ).latest("created_at")

        self.assertEqual(
            event.ip_address,
            "127.0.0.1",
        )

    def test_brute_force_detection_after_failed_logins(self):
        for _ in range(5):
            response = self.client.post(
                reverse("login"),
                {
                    "email": self.user_data["email"],
                    "password": "WrongPassword123!",
                },
                format="json",
            )

            self.assertEqual(
                response.status_code,
                status.HTTP_400_BAD_REQUEST,
            )

        failed_events = SecurityEvent.objects.filter(
            event_type="LOGIN_FAILED"
        )

        self.assertEqual(
            failed_events.count(),
            5,
        )

        brute_force_event = SecurityEvent.objects.get(
            event_type="BRUTE_FORCE_DETECTED"
        )

        self.assertEqual(
            brute_force_event.ip_address,
            "127.0.0.1",
        )

        self.assertIn(
            "5 failed login attempts",
            brute_force_event.details,
        )

    def test_brute_force_detection_is_written_to_siem_log(self):
        with TemporaryDirectory() as temp_directory:
            with override_settings(
                BASE_DIR=Path(temp_directory)
            ):
                for _ in range(5):
                    response = self.client.post(
                        reverse("login"),
                        {
                            "email": self.user_data["email"],
                            "password": "WrongPassword123!",
                        },
                        format="json",
                    )

                    self.assertEqual(
                        response.status_code,
                        status.HTTP_400_BAD_REQUEST,
                    )

                log_file = (
                    Path(temp_directory)
                    / "logs"
                    / "security-events.jsonl"
                )

                self.assertTrue(
                    log_file.exists()
                )

                log_content = log_file.read_text(
                    encoding="utf-8"
                )

                self.assertIn(
                    "BRUTE_FORCE_DETECTED",
                    log_content,
                )

                self.assertIn(
                    "5 failed login attempts",
                    log_content,
                )

    def test_suspicious_ip_detection_is_written_to_siem_log(self):
        with TemporaryDirectory() as temp_directory:
            with override_settings(
                BASE_DIR=Path(temp_directory)
            ):
                for _ in range(10):
                    SecurityEvent.objects.create(
                        event_type="LOGIN_FAILED",
                        ip_address="127.0.0.1",
                        details="Previous failed login.",
                    )

                response = self.client.post(
                    reverse("login"),
                    {
                        "email": self.user_data["email"],
                        "password": "WrongPassword123!",
                    },
                    format="json",
                )

                self.assertEqual(
                    response.status_code,
                    status.HTTP_400_BAD_REQUEST,
                )

                log_file = (
                    Path(temp_directory)
                    / "logs"
                    / "security-events.jsonl"
                )

                self.assertTrue(
                    log_file.exists()
                )

                log_content = log_file.read_text(
                    encoding="utf-8"
                )

                self.assertIn(
                    "SUSPICIOUS_IP_DETECTED",
                    log_content,
                )

                self.assertIn(
                    "10 security events",
                    log_content,
                )

    def test_suspicious_ip_detection_after_excessive_events(self):
        for _ in range(10):
            SecurityEvent.objects.create(
                event_type="LOGIN_FAILED",
                ip_address="127.0.0.1",
                details="Previous failed login.",
            )

        response = self.client.post(
            reverse("login"),
            {
                "email": self.user_data["email"],
                "password": "WrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        suspicious_ip_event = SecurityEvent.objects.get(
            event_type="SUSPICIOUS_IP_DETECTED"
        )

        self.assertEqual(
            suspicious_ip_event.ip_address,
            "127.0.0.1",
        )

        self.assertIn(
            "10 security events",
            suspicious_ip_event.details,
        )

    def test_login_with_invalid_password(self):
        response = self.client.post(
            reverse("login"),
            {
                "email": self.user_data["email"],
                "password": "WrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        event = SecurityEvent.objects.get(
            event_type="LOGIN_FAILED"
        )

        self.assertIsNone(
            event.user,
        )
        self.assertEqual(
            event.ip_address,
            "127.0.0.1",
        )
        self.assertEqual(
            event.request_path,
            reverse("login"),
        )
        self.assertIn(
            "Failed login attempt",
            event.details,
        )

    def test_me_requires_authentication(self):
        response = self.client.get(reverse("me"))

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_me_returns_authenticated_user(self):
        login_response = self.client.post(
            reverse("login"),
            {
                "email": self.user_data["email"],
                "password": self.user_data["password"],
            },
            format="json",
        )

        access_token = login_response.data["access"]

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access_token}"
        )

        response = self.client.get(reverse("me"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["email"],
            self.user_data["email"],
        )
        self.assertEqual(
            response.data["name"],
            self.user_data["name"],
        )

    def test_login_is_throttled_after_five_attempts(self):
        original_throttle_classes = LoginViewSet.throttle_classes

        try:
            LoginViewSet.throttle_classes = (LoginRateThrottle,)

            for _ in range(5):
                response = self.client.post(
                    reverse("login"),
                    {
                        "email": self.user_data["email"],
                        "password": "WrongPassword123!",
                    },
                    format="json",
                )

                self.assertEqual(
                    response.status_code,
                    status.HTTP_400_BAD_REQUEST,
                )

            response = self.client.post(
                reverse("login"),
                {
                    "email": self.user_data["email"],
                    "password": "WrongPassword123!",
                },
                format="json",
            )

            self.assertEqual(
                response.status_code,
                status.HTTP_429_TOO_MANY_REQUESTS,
            )

        finally:
            LoginViewSet.throttle_classes = original_throttle_classes

class TokenManagementAPITests(APITestCase):
    """Tests for refresh token rotation and logout."""

    def setUp(self):
        self.email = "tokenuser@example.com"
        self.password = "StrongPassword123!"

        self.user = User.objects.create_user(
            email=self.email,
            name="Token User",
            password=self.password,
        )

        login_response = self.client.post(
            reverse("login"),
            {
                "email": self.email,
                "password": self.password,
            },
            format="json",
        )

        self.access_token = login_response.data["access"]
        self.refresh_token = login_response.data["refresh"]

    def test_refresh_token_returns_new_tokens(self):
        response = self.client.post(
            reverse("token_refresh"),
            {
                "refresh": self.refresh_token,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_old_refresh_token_is_blacklisted_after_rotation(self):
        response = self.client.post(
            reverse("token_refresh"),
            {
                "refresh": self.refresh_token,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        old_refresh_response = self.client.post(
            reverse("token_refresh"),
            {
                "refresh": self.refresh_token,
            },
            format="json",
        )

        self.assertEqual(
            old_refresh_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_logout_blacklists_refresh_token(self):
        refresh_response = self.client.post(
            reverse("token_refresh"),
            {
                "refresh": self.refresh_token,
            },
            format="json",
        )

        new_refresh_token = refresh_response.data["refresh"]

        logout_response = self.client.post(
            reverse("logout"),
            {
                "refresh": new_refresh_token,
            },
            format="json",
        )

        self.assertEqual(
            logout_response.status_code,
            status.HTTP_205_RESET_CONTENT,
        )

        refresh_after_logout = self.client.post(
            reverse("token_refresh"),
            {
                "refresh": new_refresh_token,
            },
            format="json",
        )

        self.assertEqual(
            refresh_after_logout.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_expired_access_token_is_rejected(self):
        token = AccessToken.for_user(self.user)
        token.set_exp(lifetime=timedelta(seconds=-1))

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {str(token)}"
        )

        response = self.client.get(
            reverse("me")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_tampered_access_token_is_rejected(self):
        token = AccessToken.for_user(self.user)
        encoded_token = str(token)

        header, payload, signature = encoded_token.split(".")

        payload_data = json.loads(
            base64.urlsafe_b64decode(
                payload + "=" * (-len(payload) % 4)
            )
        )

        payload_data["user_id"] = str(self.user.id + 9999)

        tampered_payload = base64.urlsafe_b64encode(
            json.dumps(
                payload_data,
                separators=(",", ":"),
            ).encode()
        ).decode().rstrip("=")

        tampered_token = (
            f"{header}.{tampered_payload}.{signature}"
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {tampered_token}"
        )

        response = self.client.get(
            reverse("me")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_expired_refresh_token_is_rejected(self):
        token = RefreshToken.for_user(self.user)
        token.set_exp(lifetime=timedelta(seconds=-1))

        response = self.client.post(
            reverse("token_refresh"),
            {
                "refresh": str(token),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

class PasswordChangeAPITests(APITestCase):
    """Tests for authenticated password changes."""

    def setUp(self):
        self.email = "passworduser@example.com"
        self.password = "StrongPassword123!"

        self.user = User.objects.create_user(
            email=self.email,
            name="Password User",
            password=self.password,
        )

        login_response = self.client.post(
            reverse("login"),
            {
                "email": self.email,
                "password": self.password,
            },
            format="json",
        )

        self.access_token = login_response.data["access"]

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )

    def test_password_change_requires_authentication(self):
        self.client.credentials()

        response = self.client.post(
            reverse("password_change"),
            {
                "old_password": self.password,
                "new_password": "NewStrongPassword456!",
                "new_password_confirm": "NewStrongPassword456!",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_password_change_with_valid_data(self):
        response = self.client.post(
            reverse("password_change"),
            {
                "old_password": self.password,
                "new_password": "NewStrongPassword456!",
                "new_password_confirm": "NewStrongPassword456!",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.user.refresh_from_db()

        self.assertTrue(
            self.user.check_password("NewStrongPassword456!")
        )

    def test_password_change_rejects_wrong_old_password(self):
        response = self.client.post(
            reverse("password_change"),
            {
                "old_password": "WrongPassword123!",
                "new_password": "NewStrongPassword456!",
                "new_password_confirm": "NewStrongPassword456!",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_password_change_rejects_mismatched_passwords(self):
        response = self.client.post(
            reverse("password_change"),
            {
                "old_password": self.password,
                "new_password": "NewStrongPassword456!",
                "new_password_confirm": "DifferentPassword456!",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_password_change_rejects_weak_password(self):
        response = self.client.post(
            reverse("password_change"),
            {
                "old_password": self.password,
                "new_password": "123",
                "new_password_confirm": "123",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

class PrivilegeManagementAPITests(APITestCase):
    """Tests for administrative privilege management."""

    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com",
            name="Admin User",
            password="StrongPassword123!",
        )

        self.admin.role = "SUPER_ADMIN"
        self.admin.save()

        self.target_user = User.objects.create_user(
            email="target@example.com",
            name="Target User",
            password="StrongPassword123!",
        )

        self.url = reverse(
            "privileges-detail",
            args=[self.target_user.id],
        )

        login_response = self.client.post(
            reverse("login"),
            {
                "email": "admin@example.com",
                "password": "StrongPassword123!",
            },
            format="json",
        )

        self.access_token = login_response.data["access"]

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )

    def test_promoting_user_to_staff_creates_privilege_escalation(self):
        response = self.client.patch(
            self.url,
            {
                "is_staff": True,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.target_user.refresh_from_db()

        self.assertTrue(
            self.target_user.is_staff
        )

        event = SecurityEvent.objects.get(
            event_type="PRIVILEGE_ESCALATION"
        )

        self.assertEqual(
            event.user,
            self.admin,
        )

        self.assertEqual(
            event.ip_address,
            "127.0.0.1",
        )

        self.assertEqual(
            event.request_path,
            self.url,
        )

        self.assertIn(
            "Administrative privileges escalated",
            event.details,
        )

    def test_promoting_user_to_superuser_creates_privilege_escalation(self):
        response = self.client.patch(
            self.url,
            {
                "is_superuser": True,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.target_user.refresh_from_db()

        self.assertTrue(
            self.target_user.is_superuser
        )

        event = SecurityEvent.objects.get(
            event_type="PRIVILEGE_ESCALATION"
        )

        self.assertEqual(
            event.user,
            self.admin,
        )

        self.assertIn(
            "Administrative privileges escalated",
            event.details,
        )

    def test_removing_staff_privilege_does_not_create_escalation(self):
        self.target_user.is_staff = True
        self.target_user.save()

        response = self.client.patch(
            self.url,
            {
                "is_staff": False,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.target_user.refresh_from_db()

        self.assertFalse(
            self.target_user.is_staff
        )

        self.assertFalse(
            SecurityEvent.objects.filter(
                event_type="PRIVILEGE_ESCALATION"
            ).exists()
        )

class AccountStatusAPITests(APITestCase):
    """Tests for account activation and deactivation."""


    def setUp(self):
        self.admin = User.objects.create_user(
            email="statusadmin@example.com",
            name="Status Admin",
            password="StrongPassword123!",
        )

        self.admin.role = "SUPER_ADMIN"
        self.admin.save()

        self.target_user = User.objects.create_user(
            email="statususer@example.com",
            name="Status User",
            password="StrongPassword123!",
        )

        self.url = reverse(
            "account-status-detail",
            args=[self.target_user.id],
        )

        login_response = self.client.post(
            reverse("login"),
            {
                "email": "statusadmin@example.com",
                "password": "StrongPassword123!",
            },
            format="json",
        )

        self.access_token = login_response.data["access"]

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )

    def test_deactivating_account_creates_security_event(self):
        response = self.client.patch(
            self.url,
            {
                "is_active": False,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.target_user.refresh_from_db()

        self.assertFalse(
            self.target_user.is_active
        )

        event = SecurityEvent.objects.get(
            event_type="ACCOUNT_DEACTIVATED"
        )

        self.assertEqual(
            event.user,
            self.admin,
        )

        self.assertEqual(
            event.ip_address,
            "127.0.0.1",
        )

        self.assertEqual(
            event.request_path,
            self.url,
        )

        self.assertIn(
            "deactivated",
            event.details.lower(),
        )

    def test_activating_account_creates_security_event(self):
        self.target_user.is_active = False
        self.target_user.save()

        response = self.client.patch(
            self.url,
            {
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.target_user.refresh_from_db()

        self.assertTrue(
            self.target_user.is_active
        )

        event = SecurityEvent.objects.get(
            event_type="ACCOUNT_ACTIVATED"
        )

        self.assertEqual(
            event.user,
            self.admin,
        )

        self.assertEqual(
            event.ip_address,
            "127.0.0.1",
        )

        self.assertEqual(
            event.request_path,
            self.url,
        )

        self.assertIn(
            "activated",
            event.details.lower(),
        )
