from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)


class UserManager(BaseUserManager):
    """Manager for the custom HR platform user model."""

    def create_user(
        self,
        email,
        name,
        password=None,
        **extra_fields,
    ):
        if not email:
            raise ValueError(
                "Users must have an email address."
            )

        if not name:
            raise ValueError(
                "Users must have a name."
            )

        email = self.normalize_email(email)

        user = self.model(
            email=email,
            name=name,
            **extra_fields,
        )

        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(
        self,
        email,
        name,
        password=None,
        **extra_fields,
    ):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", "SUPER_ADMIN")

        if extra_fields.get("is_staff") is not True:
            raise ValueError(
                "Superuser must have is_staff=True."
            )

        if extra_fields.get("is_superuser") is not True:
            raise ValueError(
                "Superuser must have is_superuser=True."
            )

        return self.create_user(
            email=email,
            name=name,
            password=password,
            **extra_fields,
        )


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model for the Secure HR Platform."""

    class Role(models.TextChoices):
        SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"
        HR_ADMIN = "HR_ADMIN", "HR Admin"
        HR_MANAGER = "HR_MANAGER", "HR Manager"
        EMPLOYEE = "EMPLOYEE", "Employee"

    email = models.EmailField(
        max_length=255,
        unique=True,
    )

    name = models.CharField(
        max_length=255,
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.EMPLOYEE,
    )

    email_verified = models.BooleanField(
        default=False,
    )

    is_active = models.BooleanField(
        default=True,
    )

    is_staff = models.BooleanField(
        default=False,
    )

    objects = UserManager()

    USERNAME_FIELD = "email"

    REQUIRED_FIELDS = ["name"]

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name

    def __str__(self):
        return self.email


class AuditLog(models.Model):
    """Records important actions performed in the HR platform."""

    ACTION_CHOICES = (
        ("LOGIN", "Login"),
        ("LOGIN_FAILED", "Login Failed"),
        ("PASSWORD_CHANGE", "Password Change"),
        ("ACCOUNT_ACTIVATED", "Account Activated"),
        ("ACCOUNT_DEACTIVATED", "Account Deactivated"),
        ("ACCOUNT_CHANGE", "Account Change"),
        ("UNAUTHORIZED_ACCESS", "Unauthorized Access"),
    )

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )

    action = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    details = models.TextField(
        blank=True,
    )

    def __str__(self):
        return f"{self.action} - {self.user}"


class SecurityEvent(models.Model):
    """Records security-related events for monitoring and SIEM."""

    EVENT_TYPES = (
        ("LOGIN_SUCCESS", "Login Success"),
        ("LOGIN_FAILED", "Login Failed"),
        ("BRUTE_FORCE_DETECTED", "Brute Force Detected"),
        ("PASSWORD_CHANGED", "Password Changed"),
        ("ACCOUNT_ACTIVATED", "Account Activated"),
        ("ACCOUNT_DEACTIVATED", "Account Deactivated"),
        ("ACCOUNT_CHANGE", "Account Change"),
        ("UNAUTHORIZED_ACCESS", "Unauthorized Access"),
        ("PRIVILEGE_ESCALATION", "Privilege Escalation"),
        ("SUSPICIOUS_IP_DETECTED", "Suspicious IP Detected"),
        ("EMPLOYEE_CREATED", "Employee Created"),
        ("EMPLOYEE_UPDATED", "Employee Updated"),
        ("EMPLOYEE_DELETED", "Employee Deleted"),
        ("LEAVE_REQUEST_CREATED", "Leave Request Created"),
        ("LEAVE_REQUEST_APPROVED", "Leave Request Approved"),
        ("LEAVE_REQUEST_REJECTED", "Leave Request Rejected"),
        ("LEAVE_REQUEST_CANCELLED", "Leave Request Cancelled"),
    )

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="security_events",
    )

    event_type = models.CharField(
        max_length=50,
        choices=EVENT_TYPES,
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
    )

    user_agent = models.TextField(
        blank=True,
    )

    request_path = models.CharField(
        max_length=500,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    details = models.TextField(
        blank=True,
    )

    def __str__(self):
        return f"{self.event_type} - {self.user}"
