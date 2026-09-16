from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import (
    urlsafe_base64_decode,
    urlsafe_base64_encode,
)

from rest_framework import status
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import AnonRateThrottle

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from . import models
from . import permissions
from . import serializers

from .detections import (
    detect_brute_force,
    detect_suspicious_ip,
)

from .siem import (
    create_security_event,
    get_client_ip,
)


class LoginRateThrottle(AnonRateThrottle):
    """Limit anonymous login attempts."""

    rate = "5/min"


class UserRegistrationViewSet(viewsets.ViewSet):
    """Handles user registration."""

    serializer_class = serializers.UserRegistrationSerializer
    permission_classes = (AllowAny,)

    def create(self, request):
        serializer = self.serializer_class(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        user = serializer.save()

        return Response(
            {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "email_verified": user.email_verified,
            },
            status=status.HTTP_201_CREATED,
        )


class EmailVerificationViewSet(viewsets.ViewSet):
    """Handles email verification."""

    permission_classes = (AllowAny,)

    def list(self, request):
        uid = request.query_params.get("uid")
        token = request.query_params.get("token")

        if not uid or not token:
            return Response(
                {
                    "detail": (
                        "UID and token are required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user_id = force_str(
                urlsafe_base64_decode(uid)
            )

            user = models.User.objects.get(
                pk=user_id
            )

        except (
            TypeError,
            ValueError,
            OverflowError,
            models.User.DoesNotExist,
        ):
            return Response(
                {
                    "detail": (
                        "Invalid email verification link."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user.email_verified:
            return Response(
                {
                    "detail": (
                        "Email address is already verified."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not default_token_generator.check_token(
            user,
            token,
        ):
            return Response(
                {
                    "detail": (
                        "Invalid or expired "
                        "email verification token."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.email_verified = True

        user.save(
            update_fields=["email_verified"]
        )

        return Response(
            {
                "detail": (
                    "Email address verified successfully."
                )
            },
            status=status.HTTP_200_OK,
        )


class LoginViewSet(viewsets.ViewSet):
    """Authenticates users and returns JWT tokens."""

    serializer_class = serializers.AuthTokenSerializer
    throttle_classes = (
        (LoginRateThrottle,)
        if not settings.TESTING
        else ()
    )
    permission_classes = (AllowAny,)

    def create(self, request):
        ip_address = get_client_ip(request)

        detect_suspicious_ip(
            ip_address
        )

        serializer = self.serializer_class(
            data=request.data,
            context={
                "request": request
            },
        )

        try:
            serializer.is_valid(
                raise_exception=True
            )

        except ValidationError:
            models.AuditLog.objects.create(
                action="LOGIN_FAILED",
                details="Failed login attempt.",
            )

            create_security_event(
                request=request,
                event_type="LOGIN_FAILED",
                details="Failed login attempt.",
            )

            detect_brute_force(
                ip_address
            )

            raise

        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(
            user
        )

        models.AuditLog.objects.create(
            user=user,
            action="LOGIN",
            details=(
                "User logged in successfully."
            ),
        )

        create_security_event(
            request=request,
            user=user,
            event_type="LOGIN_SUCCESS",
            details=(
                "User logged in successfully."
            ),
        )

        return Response(
            {
                "refresh": str(refresh),
                "access": str(
                    refresh.access_token

                 ),
            },
            status=status.HTTP_200_OK,
        )

class LogoutViewSet(viewsets.ViewSet):
    """Handles user logout by blacklisting the refresh token."""

    permission_classes = (AllowAny,)

    def create(self, request):
        refresh_token = request.data.get(
            "refresh"
        )

        if not refresh_token:
            return Response(
                {
                    "detail": (
                        "Refresh token is required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(
                refresh_token
            )

            token.blacklist()

        except TokenError:
            return Response(
                {
                    "detail": (
                        "Invalid or expired "
                        "refresh token."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "detail": (
                    "Successfully logged out."
                )
            },
            status=status.HTTP_205_RESET_CONTENT,
        )

class PasswordChangeViewSet(viewsets.ViewSet):
    """Allows authenticated users to change their password."""

    permission_classes = (IsAuthenticated,)

    def create(self, request):
        serializer = serializers.PasswordChangeSerializer(
            data=request.data,
            context={
                "request": request,
            },
        )

        serializer.is_valid(
            raise_exception=True
        )

        user = serializer.save()

        create_security_event(
            request=request,
            user=user,
            event_type="PASSWORD_CHANGED",
            details="User changed their password.",
        )

        models.AuditLog.objects.create(
            user=user,
            action="PASSWORD_CHANGE",
            details="User changed their password.",
        )

        return Response(
            {
                "detail": (
                    "Password changed successfully."
                )
            },
            status=status.HTTP_200_OK,
        )

class PasswordResetRequestViewSet(viewsets.ViewSet):
    """Send a password reset link to a user."""

    permission_classes = (AllowAny,)

    def create(self, request):
        serializer = serializers.PasswordResetRequestSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        email = serializer.validated_data["email"]

        user = models.User.objects.filter(
            email=email
        ).first()

        if user:
            uid = urlsafe_base64_encode(
                force_bytes(user.pk)
            )

            token = default_token_generator.make_token(
                user
            )

            reset_url = (
                "http://127.0.0.1:8000/"
                "api/v1/auth/password-reset-confirm/"
                f"?uid={uid}&token={token}"
            )

            send_mail(
                subject="Secure HR Platform - Password Reset",
                message=(
                    "Use the following link to reset "
                    "your password:\n\n"
                    f"{reset_url}"
                ),
                from_email=None,
                recipient_list=[user.email],
            )

        return Response(
            {
                "detail": (
                    "If an account exists for this email, "
                    "a password reset link has been sent."
                )
            },
            status=status.HTTP_200_OK,
        )

class PasswordResetConfirmViewSet(viewsets.ViewSet):
    """Confirm a password reset using a valid reset token."""

    permission_classes = (AllowAny,)

    def create(self, request):
        serializer = serializers.PasswordResetConfirmSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        user = serializer.save()

        create_security_event(
            request=request,
            user=user,
            event_type="PASSWORD_CHANGED",
            details="Password reset completed successfully.",
        )

        models.AuditLog.objects.create(
            user=user,
            action="PASSWORD_CHANGE",
            details="Password reset completed successfully.",
        )

        return Response(
            {
                "detail": (
                    "Password reset successfully."
                )
            },
            status=status.HTTP_200_OK,
        )

class AccountStatusViewSet(viewsets.ViewSet):
    """Activate or deactivate a user account."""

    permission_classes = (
        permissions.IsStaffOrOwnDeactivation,
    )

    def partial_update(self, request, pk=None):
        try:
            user = models.User.objects.get(
                pk=pk
            )
        except models.User.DoesNotExist:
            return Response(
                {
                    "detail": "User not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if not self.check_object_permissions(
            request,
            user,
        ):
            return Response(
                {
                    "detail": "You do not have permission to modify this account."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = serializers.AccountStatusSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        old_status = user.is_active
        new_status = serializer.validated_data["is_active"]

        user.is_active = new_status
        user.save(
            update_fields=["is_active"]
        )

        if new_status and not old_status:
            action = "ACCOUNT_ACTIVATED"
            detail = "User account activated."
        else:
            action = "ACCOUNT_DEACTIVATED"
            detail = "User account deactivated."

        models.AuditLog.objects.create(
            user=request.user,
            action=action,
            details=detail,
        )

        create_security_event(
            request=request,
            user=request.user,
            event_type=action,
            details=detail,
        )

        return Response(
            {
                "detail": detail,
                "is_active": user.is_active,
            },
            status=status.HTTP_200_OK,
        )

class PrivilegeManagementViewSet(viewsets.ViewSet):
    """Manage administrative privileges for user accounts."""

    permission_classes = (
        permissions.IsAdmin,
    )

    def partial_update(self, request, pk=None):
        try:
            user = models.User.objects.get(
                pk=pk
            )
        except models.User.DoesNotExist:
            return Response(
                {
                    "detail": "User not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = serializers.UserPrivilegeSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        changes = {}

        if "is_staff" in serializer.validated_data:
            user.is_staff = serializer.validated_data[
                "is_staff"
            ]
            changes["is_staff"] = user.is_staff

        if "is_superuser" in serializer.validated_data:
            user.is_superuser = serializer.validated_data[
                "is_superuser"
            ]
            changes["is_superuser"] = user.is_superuser

        user.save()

        models.AuditLog.objects.create(
            user=request.user,
            action="ACCOUNT_CHANGE",
            details=(
                f"Administrative privileges changed "
                f"for user {user.email}: {changes}"
            ),
        )

        create_security_event(
            request=request,
            user=request.user,
            event_type="PRIVILEGE_ESCALATION",
            details=(
                f"Administrative privileges changed "
                f"for user {user.email}: {changes}"
            ),
        )

        return Response(
            {
                "detail": (
                    "User privileges updated successfully."
                ),
                "changes": changes,
            },
            status=status.HTTP_200_OK,
        )

class MeView(APIView):
    """Return the authenticated user's account information."""

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        serializer = serializers.UserAccountSerializer(
            request.user
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )
