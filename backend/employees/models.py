from django.conf import settings
from django.db import models
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
