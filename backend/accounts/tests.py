from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from pathlib import Path
from tempfile import TemporaryDirectory

from .models import SecurityEvent, User
from django.test import TestCase
from django.urls import reverse
from django.test import override_settings
from django.core import mail
from django.contrib.auth.tokens import default_token_generator

from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from accounts.tokens import email_verification_token_generator
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
        self.user.email_verified = True
        self.user.save(update_fields=["email_verified"])

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
        self.assertEqual(
            set(response.data.keys()),
            {
                "id",
                "email",
                "name",
                "email_verified",
                "detail",
            },
        )

        self.assertNotIn("password", response.data)
        self.assertNotIn("password_confirm", response.data)
        self.assertNotIn("is_staff", response.data)
        self.assertNotIn("is_superuser", response.data)
        self.assertNotIn("role", response.data)
        user = User.objects.get(email="newuser@example.com")

        self.assertEqual(user.name, "New User")
        self.assertTrue(
            user.check_password("StrongPassword456!")
        )
        self.assertFalse(user.email_verified)

        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]

        self.assertEqual(
            email.subject,
            "Secure HR Platform - Verify your email",
        )

        self.assertEqual(
            email.to,
            ["newuser@example.com"],
        )

        self.assertIn(
            "/api/v1/auth/verify-email/",
            email.body,
        )

        self.assertIn("uid=", email.body)
        self.assertIn("token=", email.body)

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

        # HTTP response
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        # Access token is returned in JSON
        self.assertEqual(
            set(response.data.keys()),
            {"access"},
        )

        self.assertTrue(response.data["access"])
        self.assertNotIn("refresh", response.data)

        # Sensitive user information must not be exposed
        self.assertNotIn("password", response.data)
        self.assertNotIn("email", response.data)
        self.assertNotIn("is_staff", response.data)
        self.assertNotIn("is_superuser", response.data)
        self.assertNotIn("role", response.data)

        # Refresh token must be stored in an HttpOnly cookie
        refresh_cookie = response.cookies.get(
            "secure_hr_refresh"
        )

        self.assertIsNotNone(refresh_cookie)

        self.assertTrue(
            refresh_cookie["httponly"]
        )

        self.assertEqual(
            refresh_cookie["samesite"],
            "Lax",
        )

        self.assertEqual(
            refresh_cookie["path"],
            "/api/v1/auth/",
        )

        # Verify successful login security event
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


    def test_login_rejects_unverified_email(self):
        user = User.objects.create_user(
            email="unverified@example.com",
            name="Unverified User",
            password="StrongPassword123!",
        )

        self.assertFalse(user.email_verified)

        response = self.client.post(
            reverse("login"),
            {
                "email": "unverified@example.com",
                "password": "StrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertIn(
            "Please verify your email address before logging in.",
            str(response.data),
        )

        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)


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
    """Tests for cookie-based refresh token rotation and logout."""

    REFRESH_COOKIE_NAME = "secure_hr_refresh"

    def setUp(self):
        self.email = "tokenuser@example.com"
        self.password = "StrongPassword123!"

        self.user = User.objects.create_user(
            email=self.email,
            name="Token User",
            password=self.password,
        )
        self.user.email_verified = True
        self.user.save(update_fields=["email_verified"])

        # Enforce real CSRF validation.
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.defaults["HTTP_HOST"] = "localhost"

        # Initialize the CSRF cookie.
        csrf_response = self.client.get(
            reverse("csrf"),
        )

        self.assertEqual(
            csrf_response.status_code,
            status.HTTP_200_OK,
        )
        self.assertIn("csrftoken", self.client.cookies)

        self.csrf_token = self.client.cookies[
            "csrftoken"
        ].value

        # Authenticate and receive the refresh cookie.
        login_response = self.post_with_csrf(
            reverse("login"),
            {
                "email": self.email,
                "password": self.password,
            },
        )

        self.assertEqual(
            login_response.status_code,
            status.HTTP_200_OK,
        )

        self.access_token = login_response.data["access"]

        self.assertNotIn("refresh", login_response.data)
        self.assertIn(
            self.REFRESH_COOKIE_NAME,
            self.client.cookies,
        )

        self.refresh_token = self.client.cookies[
            self.REFRESH_COOKIE_NAME
        ].value

    def post_with_csrf(self, url, data=None):
        """Send a POST request with the initialized CSRF token."""
        return self.client.post(
            url,
            data or {},
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf_token,
        )

    def set_refresh_cookie(self, token):
        """Set a refresh cookie for a specific token."""
        self.client.cookies[
            self.REFRESH_COOKIE_NAME
        ] = token

    def test_refresh_token_returns_new_access_token(self):
        old_refresh_token = self.refresh_token

        response = self.post_with_csrf(
            reverse("token_refresh"),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            set(response.data.keys()),
            {"access"},
        )

        self.assertTrue(response.data["access"])
        self.assertNotIn("refresh", response.data)

        # The refresh cookie must be rotated.
        self.assertIn(
            self.REFRESH_COOKIE_NAME,
            response.cookies,
        )

        new_refresh_token = response.cookies[
            self.REFRESH_COOKIE_NAME
        ].value

        self.assertTrue(new_refresh_token)
        self.assertNotEqual(
            old_refresh_token,
            new_refresh_token,
        )

    def test_old_refresh_token_is_blacklisted_after_rotation(self):
        old_refresh_token = self.refresh_token

        response = self.post_with_csrf(
            reverse("token_refresh"),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        new_refresh_token = self.client.cookies[
            self.REFRESH_COOKIE_NAME
        ].value

        self.assertNotEqual(
            old_refresh_token,
            new_refresh_token,
        )

        # Simulate an attacker replaying the old token.
        self.set_refresh_cookie(old_refresh_token)

        replay_response = self.post_with_csrf(
            reverse("token_refresh"),
        )

        self.assertEqual(
            replay_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_logout_blacklists_refresh_token_and_clears_cookie(self):
        refresh_token = self.refresh_token

        response = self.post_with_csrf(
            reverse("logout"),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_205_RESET_CONTENT,
        )

        # The response must delete the refresh cookie.
        deleted_cookie = response.cookies.get(
            self.REFRESH_COOKIE_NAME
        )

        self.assertIsNotNone(deleted_cookie)
        self.assertEqual(deleted_cookie.value, "")
        self.assertEqual(
            deleted_cookie["path"],
            "/api/v1/auth/",
        )

        # Replaying the logged-out token must fail.
        self.set_refresh_cookie(refresh_token)

        refresh_after_logout = self.post_with_csrf(
            reverse("token_refresh"),
        )

        self.assertEqual(
            refresh_after_logout.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_refresh_without_csrf_is_rejected(self):
        response = self.client.post(
            reverse("token_refresh"),
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_logout_without_csrf_is_rejected(self):
        response = self.client.post(
            reverse("logout"),
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_login_without_csrf_is_rejected(self):
        response = self.client.post(
            reverse("login"),
            {
                "email": self.email,
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_refresh_without_cookie_returns_unauthorized(self):
        self.client.cookies.pop(
            self.REFRESH_COOKIE_NAME,
            None,
        )

        response = self.post_with_csrf(
            reverse("token_refresh"),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_expired_access_token_is_rejected(self):
        token = AccessToken.for_user(self.user)
        token.set_exp(lifetime=timedelta(seconds=-1))

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {str(token)}"
        )

        response = self.client.get(
            reverse("me"),
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
            reverse("me"),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_expired_refresh_token_is_rejected(self):
        token = RefreshToken.for_user(self.user)
        token.set_exp(lifetime=timedelta(seconds=-1))

        self.set_refresh_cookie(str(token))

        response = self.post_with_csrf(
            reverse("token_refresh"),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_refresh_rejects_inactive_user(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.post_with_csrf(
            reverse("token_refresh"),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_refresh_rejects_unverified_user(self):
        self.user.email_verified = False
        self.user.save(update_fields=["email_verified"])

        response = self.post_with_csrf(
            reverse("token_refresh"),
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
        self.user.email_verified = True
        self.user.save(update_fields=["email_verified"])
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
        self.admin.email_verified = True
        self.admin.save(update_fields=["email_verified"])
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

        self.assertEqual(
            event.details,
            "Administrative privileges escalated for a user.",
        )

        self.assertNotIn(
            self.target_user.email,
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

        self.assertEqual(
            event.details,
            "Administrative privileges escalated for a user.",
        )

        self.assertNotIn(
            self.target_user.email,
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
        self.admin.email_verified = True
        self.admin.save(update_fields=["email_verified"])
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

class EmailVerificationAPITests(APITestCase):
    """Tests for email verification."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="verification@example.com",
            name="Verification User",
            password="StrongPassword123!",
        )

        self.uid = urlsafe_base64_encode(
            force_bytes(self.user.pk)
        )

        self.token = email_verification_token_generator.make_token(
            self.user
        )

        self.url = reverse("verify-email-list")

    def test_valid_token_verifies_email(self):
        self.assertFalse(self.user.email_verified)

        response = self.client.get(
            self.url,
            {
                "uid": self.uid,
                "token": self.token,
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["detail"],
            "Email address verified successfully.",
        )

        self.user.refresh_from_db()

        self.assertTrue(self.user.email_verified)

    def test_invalid_token_does_not_verify_email(self):
        response = self.client.get(
            self.url,
            {
                "uid": self.uid,
                "token": "invalid-token",
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.user.refresh_from_db()

        self.assertFalse(self.user.email_verified)

    def test_password_reset_token_cannot_verify_email(self):
        password_reset_token = (
            default_token_generator.make_token(self.user)
        )

        response = self.client.get(
            self.url,
            {
                "uid": self.uid,
                "token": password_reset_token,
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertIn(
            "Invalid or expired",
            response.data["detail"],
        )

        self.user.refresh_from_db()

        self.assertFalse(self.user.email_verified)


    def test_already_verified_email_is_rejected(self):
        self.user.email_verified = True
        self.user.save(update_fields=["email_verified"])

        response = self.client.get(
            self.url,
            {
                "uid": self.uid,
                "token": self.token,
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            response.data["detail"],
            "Email address is already verified.",
        )

    def test_missing_verification_parameters_are_rejected(self):
        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            response.data["detail"],
            "UID and token are required.",
        )
