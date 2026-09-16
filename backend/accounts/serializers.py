from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError

from rest_framework import serializers

from . import models


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for creating a new HR platform user account."""

    password_confirm = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )

    class Meta:
        model = models.User
        fields = (
            "id",
            "email",
            "name",
            "password",
            "password_confirm",
        )
        extra_kwargs = {
            "password": {
                "write_only": True,
                "style": {"input_type": "password"},
            },
        }

    def validate(self, attrs):
        """Validate password confirmation and password strength."""

        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {
                    "password_confirm": "Passwords do not match.",
                }
            )

        try:
            validate_password(attrs["password"])
        except ValidationError as exc:
            raise serializers.ValidationError(
                {
                    "password": exc.messages,
                }
            )

        return attrs

    def create(self, validated_data):
        """Create and return a new HR user."""

        validated_data.pop("password_confirm")

        return models.User.objects.create_user(
            email=validated_data["email"],
            name=validated_data["name"],
            password=validated_data["password"],
        )


class AuthTokenSerializer(serializers.Serializer):
    """Validate user credentials for JWT authentication."""

    email = serializers.EmailField()

    password = serializers.CharField(
        style={"input_type": "password"},
        trim_whitespace=False,
        write_only=True,
    )

    def validate(self, attrs):
        """Authenticate the user using email and password."""

        email = attrs.get("email")
        password = attrs.get("password")

        if email and password:
            user = authenticate(
                request=self.context.get("request"),
                email=email,
                password=password,
            )

            if not user:
                raise serializers.ValidationError(
                    "Unable to authenticate with the provided credentials.",
                    code="authorization",
                )

            if not user.is_active:
                raise serializers.ValidationError(
                    "This account is inactive.",
                    code="authorization",
                )

        else:
            raise serializers.ValidationError(
                "Must include 'email' and 'password'."
            )

        attrs["user"] = user

        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    """Validate a password change for an authenticated user."""

    old_password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
        trim_whitespace=False,
    )

    new_password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
        trim_whitespace=False,
    )

    new_password_confirm = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
        trim_whitespace=False,
    )

    def validate(self, attrs):
        """Validate the current password and new password."""

        user = self.context["request"].user

        if not user.check_password(attrs["old_password"]):
            raise serializers.ValidationError(
                {
                    "old_password": "Current password is incorrect.",
                }
            )

        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {
                    "new_password_confirm": "Passwords do not match.",
                }
            )

        try:
            validate_password(
                attrs["new_password"],
                user=user,
            )
        except ValidationError as exc:
            raise serializers.ValidationError(
                {
                    "new_password": exc.messages,
                }
            )

        return attrs

    def create(self, validated_data):
        """Set and save the authenticated user's new password."""

        user = self.context["request"].user

        user.set_password(
            validated_data["new_password"]
        )

        user.save(
            update_fields=["password"]
        )

        return user
class PasswordResetRequestSerializer(serializers.Serializer):
    """Validate an email address for a password reset request."""

    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Validate a password reset using a valid UID and token."""

    uid = serializers.CharField()

    token = serializers.CharField()

    new_password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
        trim_whitespace=False,
    )

    new_password_confirm = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
        trim_whitespace=False,
    )

    def validate(self, attrs):
        """Validate the reset token and new password."""

        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {
                    "new_password_confirm": "Passwords do not match.",
                }
            )

        try:
            user = models.User.objects.get(
                pk=attrs["uid"]
            )
        except models.User.DoesNotExist:
            raise serializers.ValidationError(
                {
                    "uid": "Invalid user identifier.",
                }
            )

        if not default_token_generator.check_token(
            user,
            attrs["token"],
        ):
            raise serializers.ValidationError(
                {
                    "token": "Invalid or expired password reset token.",
                }
            )

        try:
            validate_password(
                attrs["new_password"],
                user=user,
            )
        except ValidationError as exc:
            raise serializers.ValidationError(
                {
                    "new_password": exc.messages,
                }
            )

        attrs["user"] = user

        return attrs

    def save(self, **kwargs):
        """Set the new password for the user."""

        user = self.validated_data["user"]

        user.set_password(
            self.validated_data["new_password"]
        )

        user.save(
            update_fields=["password"]
        )

        return user


class UserAccountSerializer(serializers.ModelSerializer):
    """Serializer for displaying a user's HR account information."""

    class Meta:
        model = models.User
        fields = (
            "id",
            "email",
            "name",
            "email_verified",
            "is_active",
        )
        read_only_fields = (
            "id",
            "email",
            "email_verified",
            "is_active",
        )


class AccountStatusSerializer(serializers.Serializer):
    """Serializer for activating or deactivating a user account."""

    is_active = serializers.BooleanField()


class UserPrivilegeSerializer(serializers.Serializer):
    """Serializer for managing administrative privileges."""

    is_staff = serializers.BooleanField(required=False)

    is_superuser = serializers.BooleanField(required=False)
