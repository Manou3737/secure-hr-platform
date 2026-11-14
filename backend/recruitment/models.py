from django.db import models

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower

from employees.models import Department, Position


class JobPosting(models.Model):
    """Represents a job opening published by the organization."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        OPEN = "OPEN", "Open"
        CLOSED = "CLOSED", "Closed"
        CANCELLED = "CANCELLED", "Cancelled"

    class EmploymentType(models.TextChoices):
        FULL_TIME = "FULL_TIME", "Full-time"
        PART_TIME = "PART_TIME", "Part-time"
        CONTRACT = "CONTRACT", "Contract"
        TEMPORARY = "TEMPORARY", "Temporary"
        INTERNSHIP = "INTERNSHIP", "Internship"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    title = models.CharField(max_length=150)

    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="job_postings",
    )

    position = models.ForeignKey(
        Position,
        on_delete=models.PROTECT,
        related_name="job_postings",
    )

    description = models.TextField()

    responsibilities = models.TextField(blank=True)

    qualifications = models.TextField(blank=True)

    employment_type = models.CharField(
        max_length=20,
        choices=EmploymentType.choices,
    )

    location = models.CharField(max_length=255, blank=True)

    salary_min = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    salary_max = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    application_deadline = models.DateField(
        null=True,
        blank=True,
    )

    published_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_job_postings",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["department", "status"],
                name="recruit_job_dept_status_idx",
            ),
            models.Index(
                fields=["status", "application_deadline"],
                name="recruit_job_deadline_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(salary_min__isnull=True)
                    | Q(salary_max__isnull=True)
                    | Q(salary_max__gte=F("salary_min"))
                ),
                name="recruit_salary_range_valid",
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.position_id
            and self.department_id
            and self.position.department_id != self.department_id
        ):
            raise ValidationError({
                "position": (
                    "The selected position must belong "
                    "to the selected department."
                )
            })

        if (
            self.application_deadline
            and self.published_at
            and self.application_deadline < self.published_at.date()
        ):
            raise ValidationError({
                "application_deadline": (
                    "The application deadline cannot precede "
                    "the publication date."
                )
            })

    def __str__(self):
        return self.title

class Candidate(models.Model):
    """Stores a department-specific external job applicant profile."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="candidate_profiles",
    )

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(max_length=255)
    phone = models.CharField(max_length=30, blank=True)
    linkedin_url = models.URLField(blank=True)
    portfolio_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        constraints = [
            models.UniqueConstraint(
                "department",
                Lower("email"),
                name="recruit_cand_dept_email_ci_uniq",
            ),
        ]

    def clean_fields(self, exclude=None):
        if self.email:
            self.email = self.email.strip().lower()
        super().clean_fields(exclude=exclude)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class JobApplication(models.Model):
    """Represents a candidate's application for a job posting."""

    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "Submitted"
        SCREENING = "SCREENING", "Screening"
        INTERVIEW = "INTERVIEW", "Interview"
        OFFER = "OFFER", "Offer"
        HIRED = "HIRED", "Hired"
        REJECTED = "REJECTED", "Rejected"
        WITHDRAWN = "WITHDRAWN", "Withdrawn"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.PROTECT,
        related_name="applications",
    )

    job_posting = models.ForeignKey(
        JobPosting,
        on_delete=models.PROTECT,
        related_name="applications",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SUBMITTED,
        db_index=True,
    )

    cover_letter = models.TextField(blank=True)

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_recruitment_applications",
    )

    privacy_consent = models.BooleanField(default=False)

    privacy_consent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    applied_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-applied_at"]
        indexes = [
            models.Index(
                fields=["job_posting", "status"],
                name="recruit_app_job_status_idx",
            ),
            models.Index(
                fields=["status", "applied_at"],
                name="recruit_app_status_date_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["candidate", "job_posting"],
                name="recruit_candidate_job_unique",
            ),
        ]

    def clean(self):
        super().clean()

        if self.privacy_consent and not self.privacy_consent_at:
            raise ValidationError({
                "privacy_consent_at": (
                    "The consent timestamp is required "
                    "when privacy consent is granted."
                )
            })

        if not self.privacy_consent and self.privacy_consent_at:
            raise ValidationError({
                "privacy_consent_at": (
                    "A consent timestamp cannot exist "
                    "without privacy consent."
                )
            })
        if (
            self.candidate_id
            and self.job_posting_id
            and self.candidate.department_id
            != self.job_posting.department_id
        ):
            raise ValidationError({
                "candidate": (
                    "The candidate profile must belong "
                    "to the job posting's department."
                )
            })
    def __str__(self):
        return (
            f"{self.candidate} - "
            f"{self.job_posting.title}"
        )


class ApplicationStatusHistory(models.Model):
    """Records every status transition of a job application."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    application = models.ForeignKey(
        JobApplication,
        on_delete=models.PROTECT,
        related_name="status_history",
    )

    previous_status = models.CharField(
        max_length=20,
        choices=JobApplication.Status.choices,
        blank=True,
    )

    new_status = models.CharField(
        max_length=20,
        choices=JobApplication.Status.choices,
    )

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recruitment_status_changes",
    )

    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["application", "created_at"],
                name="recruit_history_app_date_idx",
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.previous_status
            and self.previous_status == self.new_status
        ):
            raise ValidationError({
                "new_status": (
                    "The new status must differ "
                    "from the previous status."
                )
            })

    def __str__(self):
        return (
            f"{self.application_id}: "
            f"{self.previous_status or 'INITIAL'} "
            f"-> {self.new_status}"
        )
