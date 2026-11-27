import uuid
from django.conf import settings
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from .encryption import EncryptedCharField

class Department(models.Model):
    """Represents an HR department."""

    name = models.CharField(
        max_length=100,
        unique=True,
    )

    code = models.CharField(
        max_length=20,
        unique=True,
    )

    description = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.name


class Position(models.Model):
    """Represents a job position within a department."""

    title = models.CharField(
        max_length=100,
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="positions",
    )

    description = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.title

class Site(models.Model):
    """Represents a physical work site belonging to a department."""

    name = models.CharField(
        max_length=100,
    )

    code = models.CharField(
        max_length=20,
        unique=True,
    )

    address = models.TextField(
        blank=True,
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="sites",
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("department", "name"),
                name="unique_site_name_per_department",
            ),
        ]
        ordering = ("name",)

    def __str__(self):
        return f"{self.name} ({self.department.code})"

class EmployeeProfile(models.Model):
    """Stores HR information associated with a user account."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee_profile",
    )

    employee_id = models.CharField(
        max_length=50,
        unique=True,
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="employee_profiles",
    )

    position = models.ForeignKey(
        Position,
        on_delete=models.PROTECT,
        related_name="employee_profiles",
    )

    site = models.ForeignKey(
        Site,
        on_delete=models.PROTECT,
        related_name="employee_profiles",
        null=True,
        blank=True,
    )

    phone = models.CharField(
        max_length=30,
        blank=True,
    )

    hire_date = models.DateField()

    date_of_birth = models.DateField(
        null=True,
        blank=True,
    )

    address = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return f"{self.employee_id} - {self.user.name}"

class LeaveRequest(models.Model):
    """Represents an employee leave request."""

    LEAVE_TYPES = (
        ("VACATION", "Vacation"),
        ("SICK", "Sick"),
        ("PERSONAL", "Personal"),
        ("OTHER", "Other"),
    )

    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("CANCELLED", "Cancelled"),
    )

    employee = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.PROTECT,
        related_name="leave_requests",
    )

    leave_type = models.CharField(
        max_length=20,
        choices=LEAVE_TYPES,
    )

    start_date = models.DateField()

    end_date = models.DateField()

    reason = models.TextField(
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviewed_leave_requests",
        null=True,
        blank=True,
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def clean(self):
        """Validate leave request business rules."""

        super().clean()

        if (
            self.start_date
            and self.end_date
            and self.start_date > self.end_date
        ):
            raise ValidationError(
                {
                    "end_date": (
                        "End date must be greater than "
                        "or equal to start date."
                    )
                }
            )

    def save(self, *args, **kwargs):
        """Validate the leave request before saving."""

        self.full_clean()

        super().save(*args, **kwargs)

    def approve(self, reviewer):
        """Approve a pending leave request."""

        if self.status != "PENDING":
            raise ValidationError(
                "Only pending leave requests can be approved."
            )

        self.status = "APPROVED"
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()

        self.save()

    def reject(self, reviewer):
        """Reject a pending leave request."""

        if self.status != "PENDING":
            raise ValidationError(
                "Only pending leave requests can be rejected."
            )

        self.status = "REJECTED"
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()

        self.save()

    def cancel(self):
        """Cancel a pending leave request."""

        if self.status != "PENDING":
            raise ValidationError(
                "Only pending leave requests can be cancelled."
            )

        self.status = "CANCELLED"

        self.save()

    def __str__(self):
        return (
            f"{self.employee.employee_id} - "
            f"{self.leave_type} - "
            f"{self.start_date}"
        )

class PayPeriod(models.Model):
    """Represents a payroll processing period."""

    STATUS_CHOICES = (
        ("OPEN", "Open"),
        ("PROCESSING", "Processing"),
        ("PROCESSED", "Processed"),
        ("CLOSED", "Closed"),
    )

    name = models.CharField(
        max_length=100,
        unique=True,
    )

    start_date = models.DateField()

    end_date = models.DateField()

    payment_date = models.DateField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="OPEN",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def clean(self):
        """Validate payroll period business rules."""

        super().clean()

        errors = {}

        if (
            self.start_date
            and self.end_date
            and self.start_date > self.end_date
        ):
            errors["end_date"] = (
                "End date must be greater than "
                "or equal to start date."
            )

        if (
            self.end_date
            and self.payment_date
            and self.payment_date < self.end_date
        ):
            errors["payment_date"] = (
                "Payment date must be greater than "
                "or equal to end date."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Validate the pay period before saving."""

        self.full_clean()

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Payroll(models.Model):
    """Represents payroll processing for a pay period."""

    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("PROCESSING", "Processing"),
        ("PROCESSED", "Processed"),
        ("CANCELLED", "Cancelled"),
    )

    pay_period = models.OneToOneField(
        PayPeriod,
        on_delete=models.PROTECT,
        related_name="payroll",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="DRAFT",
    )

    processed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="processed_payrolls",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def clean(self):
        """Validate payroll business rules."""

        super().clean()

        errors = {}

        if self.status == "PROCESSED":
            if not self.processed_at:
                errors["processed_at"] = (
                    "Processed payroll must have "
                    "a processed date."
                )

            if not self.processed_by:
                errors["processed_by"] = (
                    "Processed payroll must have "
                    "a processor."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Validate payroll before saving."""

        self.full_clean()

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.pay_period.name} - "
            f"{self.status}"
        )

class PayrollRecord(models.Model):
    """Represents an employee's payroll calculation."""

    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("CALCULATED", "Calculated"),
        ("PAID", "Paid"),
        ("VOID", "Void"),
    )

    payroll = models.ForeignKey(
        Payroll,
        on_delete=models.PROTECT,
        related_name="records",
    )

    employee = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.PROTECT,
        related_name="payroll_records",
    )

    base_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    total_earnings = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    gross_pay = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    total_deductions = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    net_pay = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=(
                    "payroll",
                    "employee",
                ),
                name="unique_employee_payroll_record",
            ),
        )

    def clean(self):
        """Validate payroll record calculations."""

        super().clean()

        errors = {}

        if self.base_salary < 0:
            errors["base_salary"] = (
                "Base salary cannot be negative."
            )

        if self.total_earnings < 0:
            errors["total_earnings"] = (
                "Total earnings cannot be negative."
            )

        if self.total_deductions < 0:
            errors["total_deductions"] = (
                "Total deductions cannot be negative."
            )

        expected_gross_pay = (
            self.base_salary
            + self.total_earnings
        )

        if self.gross_pay != expected_gross_pay:
            errors["gross_pay"] = (
                "Gross pay must equal base salary "
                "plus total earnings."
            )

        expected_net_pay = (
            self.gross_pay
            - self.total_deductions
        )

        if self.net_pay != expected_net_pay:
            errors["net_pay"] = (
                "Net pay must equal gross pay "
                "minus total deductions."
            )

        if self.net_pay < 0:
            errors["net_pay"] = (
                "Net pay cannot be negative."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Validate payroll record before saving."""

        self.full_clean()

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.employee.employee_id} - "
            f"{self.payroll.pay_period.name}"
        )

class Earning(models.Model):
    """Represents an additional earning for a payroll record."""

    EARNING_TYPES = (
        ("OVERTIME", "Overtime"),
        ("BONUS", "Bonus"),
        ("COMMISSION", "Commission"),
        ("ALLOWANCE", "Allowance"),
        ("OTHER", "Other"),
    )

    payroll_record = models.ForeignKey(
        PayrollRecord,
        on_delete=models.PROTECT,
        related_name="earnings",
    )

    earning_type = models.CharField(
        max_length=20,
        choices=EARNING_TYPES,
    )

    description = models.CharField(
        max_length=255,
        blank=True,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def clean(self):
        """Validate earning business rules."""

        super().clean()

        if self.amount < 0:
            raise ValidationError(
                {
                    "amount": (
                        "Earning amount cannot be negative."
                    )
                }
            )

    def save(self, *args, **kwargs):
        """Validate earning before saving."""

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.payroll_record.employee.employee_id} - "
            f"{self.earning_type} - "
            f"{self.amount}"
        )

class Deduction(models.Model):
    """Represents a deduction from a payroll record."""

    DEDUCTION_TYPES = (
        ("TAX", "Tax"),
        ("INSURANCE", "Insurance"),
        ("RETIREMENT", "Retirement"),
        ("BENEFIT", "Benefit"),
        ("OTHER", "Other"),
    )

    payroll_record = models.ForeignKey(
        PayrollRecord,
        on_delete=models.PROTECT,
        related_name="deductions",
    )

    deduction_type = models.CharField(
        max_length=20,
        choices=DEDUCTION_TYPES,
    )

    description = models.CharField(
        max_length=255,
        blank=True,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def clean(self):
        """Validate deduction business rules."""

        super().clean()

        if self.amount < 0:
            raise ValidationError(
                {
                    "amount": (
                        "Deduction amount cannot be negative."
                    )
                }
            )

    def save(self, *args, **kwargs):
        """Validate deduction before saving."""

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.payroll_record.employee.employee_id} - "
            f"{self.deduction_type} - "
            f"{self.amount}"
        )

class Payment(models.Model):
    """Represents a payment associated with a payroll record."""

    PAYMENT_METHODS = (
        ("DIRECT_DEPOSIT", "Direct Deposit"),
        ("CHECK", "Check"),
        ("CASH", "Cash"),
    )

    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
        ("CANCELLED", "Cancelled"),
    )

    payroll_record = models.ForeignKey(
        PayrollRecord,
        on_delete=models.PROTECT,
        related_name="payments",
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHODS,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
    )

    payment_date = models.DateTimeField(
        null=True,
        blank=True,
    )

    transaction_reference = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def clean(self):
        """Validate payment business rules."""

        super().clean()

        errors = {}

        if self.amount < 0:
            errors["amount"] = (
                "Payment amount cannot be negative."
            )

        if (
            self.status == "COMPLETED"
            and not self.payment_date
        ):
            errors["payment_date"] = (
                "Completed payment must have "
                "a payment date."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Validate payment before saving."""

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.payroll_record.employee.employee_id} - "
            f"{self.amount} - "
            f"{self.status}"
        )

class BankAccount(models.Model):
    """Stores an employee's bank account information."""

    ACCOUNT_TYPES = (
        ("CHECKING", "Checking"),
        ("SAVINGS", "Savings"),
    )

    employee = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.PROTECT,
        related_name="bank_accounts",
    )

    account_type = models.CharField(
        max_length=20,
        choices=ACCOUNT_TYPES,
    )

    routing_number = EncryptedCharField(
        max_length=255,
    )

    account_number = EncryptedCharField(
        max_length=255,
    )

    last_four = models.CharField(
        max_length=4,
        editable=False,
    )

    is_primary = models.BooleanField(
        default=False,
    )

    is_verified = models.BooleanField(
        default=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def clean(self):
        """Validate bank account business rules."""

        super().clean()

        errors = {}

        if not self.routing_number.isdigit():
            errors["routing_number"] = (
                "Routing number must contain only digits."
            )

        if not self.account_number.isdigit():
            errors["account_number"] = (
                "Account number must contain only digits."
            )

        if len(self.routing_number) != 9:
            errors["routing_number"] = (
                "Routing number must contain 9 digits."
            )

        if len(self.account_number) < 4:
            errors["account_number"] = (
                "Account number must contain at least 4 digits."
            )

        if self.is_primary:
            existing_primary = (
                BankAccount.objects
                .filter(
                    employee=self.employee,
                    is_primary=True,
                )
                .exclude(pk=self.pk)
                .exists()
            )

            if existing_primary:
                errors["is_primary"] = (
                    "An employee can have only one "
                    "primary bank account."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Validate and prepare bank account before saving."""

        self.last_four = self.account_number[-4:]

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.employee.employee_id} - "
            f"{self.account_type} - "
            f"****{self.last_four}"
        )

class PerformanceReview(models.Model):
    """Stores an employee performance review."""

    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("SUBMITTED", "Submitted"),
        ("ACKNOWLEDGED", "Acknowledged"),
    )

    employee = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.PROTECT,
        related_name="performance_reviews",
    )

    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="performance_reviews_given",
    )

    review_period_start = models.DateField()
    review_period_end = models.DateField()

    score = models.DecimalField(
        max_digits=3,
        decimal_places=2,
    )

    comments = models.TextField(
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="DRAFT",
    )

    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def clean(self):
        """Validate performance review business rules."""

        super().clean()

        errors = {}

        if (
            self.review_period_start
            and self.review_period_end
            and self.review_period_start
            > self.review_period_end
        ):
            errors["review_period_end"] = (
                "Review period end date must be "
                "greater than or equal to start date."
            )

        if self.score < 0 or self.score > 5:
            errors["score"] = (
                "Performance score must be between 0 and 5."
            )

        if self.status == "SUBMITTED" and not self.submitted_at:
            errors["submitted_at"] = (
                "Submitted performance review must "
                "have a submission date."
            )

        if self.status == "ACKNOWLEDGED" and not self.submitted_at:
            errors["submitted_at"] = (
                "Acknowledged performance review must "
                "have a submission date."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Validate performance review before saving."""

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.employee.employee_id} - "
            f"{self.review_period_start} to "
            f"{self.review_period_end}"
        )

class DocumentCategory(models.Model):
    """Classify HR documents by business category."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Document category"
        verbose_name_plural = "Document categories"

    def __str__(self):
        return self.name

class DocumentFolder(models.Model):
    """Organize HR documents in a hierarchical folder structure."""

    name = models.CharField(max_length=150)

    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["is_active"]),
        ]
        verbose_name = "Document folder"
        verbose_name_plural = "Document folders"

    def __str__(self):
        return self.name

class HRDocument(models.Model):
    """Stores metadata for a privately stored HR document."""

    class DocumentType(models.TextChoices):
        IDENTITY_DOCUMENT = "IDENTITY_DOCUMENT", "Identity document"
        EMPLOYMENT_CONTRACT = "EMPLOYMENT_CONTRACT", "Employment contract"
        TAX_FORM = "TAX_FORM", "Tax form"
        CERTIFICATION = "CERTIFICATION", "Certification"
        POLICY_ACKNOWLEDGMENT = (
            "POLICY_ACKNOWLEDGMENT",
            "Policy acknowledgment",
        )
        ONBOARDING_FORM = "ONBOARDING_FORM", "Onboarding form"
        OTHER = "OTHER", "Other"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    employee = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.PROTECT,
        related_name="hr_documents",
    )
    category = models.ForeignKey(
        DocumentCategory,
        on_delete=models.PROTECT,
        related_name="documents",
        null=True,
        blank=True,
    )

    folder = models.ForeignKey(
        DocumentFolder,
        on_delete=models.PROTECT,
        related_name="documents",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200)

    document_type = models.CharField(
        max_length=30,
        choices=DocumentType.choices,
    )

    original_filename = models.CharField(max_length=255)

    # Internal object key only; never a public URL.
    storage_key = models.CharField(
        max_length=512,
        unique=True,
        editable=False,
    )

    mime_type = models.CharField(max_length=100)

    size_bytes = models.PositiveBigIntegerField()

    checksum_sha256 = models.CharField(
        max_length=64,
        blank=True,
    )
    class Status(models.TextChoices):
        PENDING_SCAN = "PENDING_SCAN", "Pending antivirus scan"
        PENDING_REVIEW = "PENDING_REVIEW", "Pending HR review"
        VERIFIED = "VERIFIED", "Verified"
        QUARANTINED = "QUARANTINED", "Quarantined"
        REJECTED = "REJECTED", "Rejected"
        ARCHIVED = "ARCHIVED", "Archived"

    class Confidentiality(models.TextChoices):
        INTERNAL = "INTERNAL", "Internal"
        CONFIDENTIAL = "CONFIDENTIAL", "Confidential"
        RESTRICTED = "RESTRICTED", "Restricted"

    confidentiality = models.CharField(
        max_length=20,
        choices=Confidentiality.choices,
        default=Confidentiality.CONFIDENTIAL,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING_SCAN,
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="hr_documents_uploaded",
    )

    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="hr_documents_verified",
        null=True,
        blank=True,
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    verified_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    rejection_reason = models.TextField(
        blank=True,
    )

    expires_at = models.DateField(
        null=True,
        blank=True,
    )

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]
        indexes = [
            models.Index(
                fields=["employee", "status"],
                name="hrdoc_emp_status_idx",
            ),
            models.Index(
                fields=["document_type", "status"],
                name="hrdoc_type_status_idx",
            ),
            models.Index(
                fields=["-uploaded_at"],
                name="hrdoc_uploaded_idx",
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.employee.employee_id})"

class DocumentVersion(models.Model):
    """Store an immutable version of a privately stored HR document."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    document = models.ForeignKey(
        HRDocument,
        on_delete=models.PROTECT,
        related_name="versions",
    )

    version_number = models.PositiveIntegerField()

    # Internal private-storage key; never expose it through the API.
    storage_key = models.CharField(
        max_length=512,
        unique=True,
        editable=False,
    )

    original_filename = models.CharField(max_length=255)

    mime_type = models.CharField(max_length=100)

    size_bytes = models.PositiveBigIntegerField()

    checksum_sha256 = models.CharField(max_length=64)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="hr_document_versions_created",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["document", "version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "version_number"],
                name="unique_hr_doc_version_number",
            ),
        ]
        indexes = [
            models.Index(
                fields=["document", "-created_at"],
                name="hrdocver_doc_created_idx",
            ),
        ]
        verbose_name = "Document version"
        verbose_name_plural = "Document versions"

    def save(self, *args, **kwargs):
        """Prevent modifications to an existing document version."""
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError(
                "Document versions cannot be modified."
            )

        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Prevent deletion of an existing document version."""
        raise ValidationError(
            "Document versions cannot be deleted."
        )

    def __str__(self):
        return f"{self.document.title} - v{self.version_number}"

class DocumentReview(models.Model):
    """Immutable audit record of an HR document review decision."""

    class Decision(models.TextChoices):
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    document = models.ForeignKey(
        HRDocument,
        on_delete=models.PROTECT,
        related_name="reviews",
    )

    # Keep the exact version reviewed; null supports reviews of the
    # original HRDocument file when no DocumentVersion exists.
    version = models.ForeignKey(
        DocumentVersion,
        on_delete=models.PROTECT,
        related_name="reviews",
        null=True,
        blank=True,
    )

    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="hr_document_reviews",
    )

    decision = models.CharField(
        max_length=10,
        choices=Decision.choices,
    )

    comment = models.TextField(blank=True)

    reviewed_at = models.DateTimeField(
        default=timezone.now,
        editable=False,
    )

    class Meta:
        ordering = ["-reviewed_at"]
        indexes = [
            models.Index(
                fields=["document", "-reviewed_at"],
                name="hrdocreview_doc_date_idx",
            ),
            models.Index(
                fields=["reviewer", "-reviewed_at"],
                name="hrdocreview_user_date_idx",
            ),
        ]
        verbose_name = "Document review"
        verbose_name_plural = "Document reviews"

    def clean(self):
        super().clean()

        if self.version_id and self.document_id:
            if self.version.document_id != self.document_id:
                raise ValidationError(
                    {
                        "version": (
                            "The reviewed version must belong "
                            "to the selected document."
                        )
                    }
                )

        if (
            self.decision == self.Decision.REJECTED
            and not self.comment.strip()
        ):
            raise ValidationError(
                {
                    "comment": (
                        "A rejection reason is required."
                    )
                }
            )

    def save(self, *args, **kwargs):
        # A review record is an audit entry, not an editable record.
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError(
                "Document review records cannot be modified."
            )

        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Document review records cannot be deleted."
        )

    def __str__(self):
        return (
            f"{self.document.title} - "
            f"{self.decision} by {self.reviewer}"
        )

def _lock_draft_onboarding_templates(template_ids):
    """Lock templates and reject structural changes to published templates."""

    template_ids = sorted(set(template_ids))

    templates = list(
        OnboardingTemplate.objects
        .select_for_update()
        .filter(pk__in=template_ids)
        .order_by("pk")
    )

    if len(templates) != len(template_ids):
        raise ValidationError("An onboarding template was not found.")

    if any(
        template.status != OnboardingTemplate.Status.DRAFT
        for template in templates
    ):
        raise ValidationError(
            "Published or retired onboarding templates cannot be modified."
        )

class OnboardingTemplate(models.Model):
    """Reusable, versioned template for an employee onboarding journey."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        RETIRED = "RETIRED", "Retired"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(max_length=200)

    description = models.TextField(blank=True)

    version = models.PositiveIntegerField(default=1)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="onboarding_templates_created",
    )

    published_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "version"],
                name="onboarding_tpl_name_version_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "name"],
                name="onboarding_tpl_status_name_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.pk:
                current = (
                    type(self).objects
                    .select_for_update()
                    .filter(pk=self.pk)
                    .first()
                )

                if current:
                    structural_fields = (
                        "name",
                        "description",
                        "version",
                        "created_by_id",
                    )

                    if current.status in (
                        self.Status.PUBLISHED,
                        self.Status.RETIRED,
                    ):
                        changed = any(
                            getattr(current, field)
                            != getattr(self, field)
                            for field in structural_fields
                        )

                        if changed:
                            raise ValidationError(
                                "The structure of a published template "
                                "cannot be changed."
                            )

                    if current.status == self.Status.RETIRED:
                        if self.status != self.Status.RETIRED:
                            raise ValidationError(
                                "A retired template cannot be reactivated."
                            )

                    if current.status == self.Status.PUBLISHED:
                        if self.status not in (
                            self.Status.PUBLISHED,
                            self.Status.RETIRED,
                        ):
                            raise ValidationError(
                                "A published template cannot return to draft."
                            )

                        if self.published_at != current.published_at:
                            raise ValidationError(
                                "The publication date cannot be changed."
                            )

            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status != self.Status.DRAFT:
            raise ValidationError(
                "Published or retired templates cannot be deleted."
            )

        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.name} (v{self.version})"

class OnboardingPhase(models.Model):
    """An ordered phase within an onboarding template."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    template = models.ForeignKey(
        OnboardingTemplate,
        on_delete=models.PROTECT,
        related_name="phases",
    )

    name = models.CharField(max_length=200)

    description = models.TextField(blank=True)

    order = models.PositiveIntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["template", "order"],
                name="onboarding_phase_template_order_uniq",
            ),
        ]

    def __str__(self):
        return f"{self.template.name} - {self.name}"

class OnboardingActivityTemplate(models.Model):
    """Defines an activity required within an onboarding phase."""

    class ActivityType(models.TextChoices):
        TASK = "TASK", "Task"
        DOCUMENT = "DOCUMENT", "Document"
        TRAINING = "TRAINING", "Training"
        ACKNOWLEDGMENT = "ACKNOWLEDGMENT", "Acknowledgment"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    phase = models.ForeignKey(
        OnboardingPhase,
        on_delete=models.PROTECT,
        related_name="activities",
    )

    name = models.CharField(max_length=200)

    description = models.TextField(blank=True)

    activity_type = models.CharField(
        max_length=20,
        choices=ActivityType.choices,
        default=ActivityType.TASK,
    )

    order = models.PositiveIntegerField()

    is_required = models.BooleanField(default=True)

    default_due_days = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["phase", "order"],
                name="onboarding_activity_phase_order_uniq",
            ),
        ]

    def save(self, *args, **kwargs):
        with transaction.atomic():
            phase_ids = [self.phase_id]

            if self.pk:
                old_phase_id = (
                    type(self).objects
                    .filter(pk=self.pk)
                    .values_list("phase_id", flat=True)
                    .first()
                )

                if old_phase_id:
                    phase_ids.append(old_phase_id)

            template_ids = list(
                OnboardingPhase.objects
                .filter(pk__in=phase_ids)
                .values_list("template_id", flat=True)
            )

            _lock_draft_onboarding_templates(template_ids)
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            template_id = (
                OnboardingPhase.objects
                .filter(pk=self.phase_id)
                .values_list("template_id", flat=True)
                .first()
            )

            if template_id is None:
                raise ValidationError("The onboarding phase was not found.")

            _lock_draft_onboarding_templates([template_id])
            return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.phase.name} - {self.name}"

class OnboardingJourney(models.Model):
    """Tracks an employee's onboarding journey."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        SUSPENDED = "SUSPENDED", "Suspended"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    employee = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.PROTECT,
        related_name="onboarding_journeys",
    )

    template = models.ForeignKey(
        OnboardingTemplate,
        on_delete=models.PROTECT,
        related_name="journeys",
    )

    # Records the template version used to create this journey.
    template_version = models.PositiveIntegerField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    target_completion_date = models.DateField(
        null=True,
        blank=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="onboarding_journeys_created",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["employee", "status"],
                name="onboard_journey_emp_status_idx",
            ),
            models.Index(
                fields=["status", "target_completion_date"],
                name="onboard_journey_status_due_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Onboarding journey for {self.employee} "
            f"({self.get_status_display()})"
        )

class OnboardingTask(models.Model):
    """An actionable task within an employee onboarding journey."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        BLOCKED = "BLOCKED", "Blocked"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    journey = models.ForeignKey(
        OnboardingJourney,
        on_delete=models.PROTECT,
        related_name="tasks",
    )

    activity_template = models.ForeignKey(
        OnboardingActivityTemplate,
        on_delete=models.PROTECT,
        related_name="onboarding_tasks",
    )

    title = models.CharField(max_length=200)

    description = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="onboarding_tasks_assigned",
        null=True,
        blank=True,
    )

    due_date = models.DateField(
        null=True,
        blank=True,
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_date", "created_at"]
        indexes = [
            models.Index(
                fields=["journey", "status"],
                name="ob_task_journey_status",
            ),
            models.Index(
                fields=["assigned_to", "status"],
                name="ob_task_assignee_status",
            ),
            models.Index(
                fields=["status", "due_date"],
                name="onboard_task_status_due_idx",
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

class TaskDependency(models.Model):
    """Defines a prerequisite task for another onboarding task."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    prerequisite_task = models.ForeignKey(
        OnboardingTask,
        on_delete=models.PROTECT,
        related_name="dependent_tasks",
    )

    dependent_task = models.ForeignKey(
        OnboardingTask,
        on_delete=models.PROTECT,
        related_name="prerequisites",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["prerequisite_task", "dependent_task"],
                name="onboard_task_dependency_uniq",
            ),
            models.CheckConstraint(
                condition=~models.Q(
                    prerequisite_task=models.F("dependent_task")
                ),
                name="onboard_task_no_self_dependency",
            ),
        ]
        indexes = [
            models.Index(
                fields=["prerequisite_task"],
                name="ob_dep_prerequisite_idx",
            ),
            models.Index(
                fields=["dependent_task"],
                name="ob_dep_dependent_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Task {self.dependent_task_id} depends on "
            f"task {self.prerequisite_task_id}"
        )

class WorkflowCondition(models.Model):
    """Stores a structured condition used by the onboarding workflow."""

    class Operator(models.TextChoices):
        EQUALS = "EQUALS", "Equals"
        NOT_EQUALS = "NOT_EQUALS", "Not equals"
        IN = "IN", "In"
        NOT_IN = "NOT_IN", "Not in"
        EXISTS = "EXISTS", "Exists"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    task = models.ForeignKey(
        OnboardingTask,
        on_delete=models.PROTECT,
        related_name="workflow_conditions",
    )

    field_name = models.CharField(max_length=100)

    operator = models.CharField(
        max_length=20,
        choices=Operator.choices,
    )

    expected_value = models.JSONField(
        null=True,
        blank=True,
    )

    is_required = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["task", "is_required"],
                name="ob_condition_task_req_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Condition for task {self.task_id}: "
            f"{self.field_name} {self.operator}"
        )

class TaskComment(models.Model):
    """Stores a comment posted on an onboarding task."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    task = models.ForeignKey(
        OnboardingTask,
        on_delete=models.PROTECT,
        related_name="comments",
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="onboarding_task_comments",
    )

    content = models.TextField(max_length=5000)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["task", "created_at"],
                name="ob_comment_task_created_idx",
            ),
            models.Index(
                fields=["author", "created_at"],
                name="ob_comment_author_created_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Comment by {self.author_id} "
            f"on task {self.task_id}"
        )

class WorkflowExecutionLog(models.Model):
    """Audit log for onboarding workflow events."""

    class Outcome(models.TextChoices):
        SUCCESS = "SUCCESS", "Success"
        FAILURE = "FAILURE", "Failure"
        DENIED = "DENIED", "Denied"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    journey = models.ForeignKey(
        OnboardingJourney,
        on_delete=models.PROTECT,
        related_name="execution_logs",
        null=True,
        blank=True,
    )

    task = models.ForeignKey(
        OnboardingTask,
        on_delete=models.PROTECT,
        related_name="execution_logs",
        null=True,
        blank=True,
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="onboarding_workflow_logs",
        null=True,
        blank=True,
    )

    event_type = models.CharField(max_length=100)

    outcome = models.CharField(
        max_length=20,
        choices=Outcome.choices,
        default=Outcome.SUCCESS,
    )

    details = models.JSONField(
        default=dict,
        blank=True,
    )

    correlation_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["journey", "created_at"],
                name="ob_log_journey_created_idx",
            ),
            models.Index(
                fields=["event_type", "created_at"],
                name="ob_log_event_created_idx",
            ),
            models.Index(
                fields=["outcome", "created_at"],
                name="ob_log_outcome_created_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.event_type} - {self.outcome} "
            f"({self.created_at})"
        )

class DocumentRetentionPolicy(models.Model):
    """Defines retention and end-of-retention actions for HR documents."""

    class RetentionBasis(models.TextChoices):
        UPLOAD_DATE = "UPLOAD_DATE", "Upload date"
        VERIFICATION_DATE = "VERIFICATION_DATE", "Verification date"
        EXPIRATION_DATE = "EXPIRATION_DATE", "Document expiration date"

    class Action(models.TextChoices):
        ARCHIVE = "ARCHIVE", "Archive document"
        DELETE = "DELETE", "Delete document"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(
        max_length=150,
        unique=True,
    )

    document_type = models.CharField(
        max_length=30,
        choices=HRDocument.DocumentType.choices,
        db_index=True,
    )

    retention_days = models.PositiveIntegerField()

    retention_basis = models.CharField(
        max_length=30,
        choices=RetentionBasis.choices,
        default=RetentionBasis.UPLOAD_DATE,
    )

    action = models.CharField(
        max_length=10,
        choices=Action.choices,
        default=Action.ARCHIVE,
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["document_type", "name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(retention_days__gt=0),
                name="retention_days_positive",
            ),
            models.UniqueConstraint(
                fields=["document_type"],
                condition=models.Q(is_active=True),
                name="one_active_retention_policy_per_type",
            ),
        ]
        indexes = [
            models.Index(
                fields=["document_type", "is_active"],
                name="retention_type_active_idx",
            ),
        ]

    def clean(self):
        super().clean()

        if self.retention_days is not None and self.retention_days <= 0:
            raise ValidationError({
                "retention_days": (
                    "Retention duration must be greater than zero."
                )
            })

        if self.is_active and self.document_type:
            conflicting_policies = type(self).objects.filter(
                document_type=self.document_type,
                is_active=True,
            )

            if self.pk:
                conflicting_policies = conflicting_policies.exclude(
                    pk=self.pk,
                )

            if conflicting_policies.exists():
                raise ValidationError({
                    "document_type": (
                        "Only one active retention policy is allowed "
                        "per document type."
                    )
                })

    def __str__(self):
        return (
            f"{self.name} ({self.document_type}, "
            f"{self.retention_days} days, {self.action})"
        )

class DocumentRetentionExecution(models.Model):
    """Durable audit record for a document retention run."""

    class Status(models.TextChoices):
        RUNNING = "RUNNING", "Running"
        SUCCESS = "SUCCESS", "Success"
        FAILURE = "FAILURE", "Failure"
        DRY_RUN = "DRY_RUN", "Dry run"
        SKIPPED = "SKIPPED", "Skipped"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    started_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    finished_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        db_index=True,
    )

    processed_count = models.PositiveIntegerField(default=0)
    archived_count = models.PositiveIntegerField(default=0)
    would_archive_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)

    error_message = models.TextField(blank=True)

    duration_ms = models.PositiveBigIntegerField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(
                fields=["status", "started_at"],
                name="ret_exec_status_started_idx",
            ),
        ]

    def __str__(self):
        return f"{self.status} - {self.started_at}"

class DocumentAccessLog(models.Model):
    """Audit trail for access to sensitive HR documents."""

    class Action(models.TextChoices):
        VIEW = "VIEW", "View"
        DOWNLOAD = "DOWNLOAD", "Download"
        CREATE = "CREATE", "Create"
        UPDATE = "UPDATE", "Update"
        VERIFY = "VERIFY", "Verify"
        REJECT = "REJECT", "Reject"
        ARCHIVE = "ARCHIVE", "Archive"
        CREATE_VERSION = "CREATE_VERSION", "Create version"
        ACCESS_DENIED = "ACCESS_DENIED", "Access denied"

    document = models.ForeignKey(
        "employees.HRDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="access_logs",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="document_access_logs",
    )

    action = models.CharField(
        max_length=30,
        choices=Action.choices,
        db_index=True,
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
    )

    user_agent = models.TextField(blank=True)

    request_path = models.CharField(
        max_length=500,
        blank=True,
    )

    details = models.TextField(blank=True)

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["document", "created_at"],
                name="doc_access_doc_created_idx",
            ),
            models.Index(
                fields=["user", "created_at"],
                name="doc_access_user_created_idx",
            ),
            models.Index(
                fields=["action", "created_at"],
                name="doc_access_action_created_idx",
            ),
        ]

    def __str__(self):
        return f"{self.action} - {self.created_at}"

class NotificationJob(models.Model):
    """Durable, retryable notification queue."""

    class NotificationType(models.TextChoices):
        TASK_ASSIGNED = "TASK_ASSIGNED", "Task assigned"
        TASK_OVERDUE = "TASK_OVERDUE", "Task overdue"
        DOCUMENT_EXPIRING = "DOCUMENT_EXPIRING", "Document expiring"
        TASK_COMPLETED = "TASK_COMPLETED", "Task completed"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        db_index=True,
    )

    idempotency_key = models.CharField(
        max_length=255,
        unique=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=5)

    next_attempt_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    correlation_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
    )

    payload = models.JSONField(default=dict)

    last_error = models.CharField(
        max_length=500,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(max_attempts__gt=0),
                name="notification_max_attempts_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(attempts__lte=models.F("max_attempts")),
                name="notification_attempts_within_limit",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "next_attempt_at"],
                name="notif_status_next_idx",
            ),
            models.Index(
                fields=["notification_type", "created_at"],
                name="notif_type_created_idx",
            ),
        ]

    def __str__(self):
        return f"{self.notification_type} - {self.status}"


class NotificationSchedulerState(models.Model):
    """Persisted state for the notification scheduler."""

    name = models.CharField(
        max_length=50,
        primary_key=True,
        default="notification_scheduler",
        editable=False,
    )

    last_daily_enqueue_date = models.DateField(
        null=True,
        blank=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return (
            f"{self.name} - "
            f"{self.last_daily_enqueue_date or 'Never'}"
        )
