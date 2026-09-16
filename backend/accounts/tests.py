from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import User
from django.test import override_settings

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

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_with_invalid_password(self):
        response = self.client.post(
            reverse("login"),
            {
                "email": self.user_data["email"],
                "password": "WrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

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
