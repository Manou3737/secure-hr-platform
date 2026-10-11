from rest_framework import serializers

from .models import (
    LeaveRequest,
    Department,
    EmployeeProfile,
    PayPeriod,
    Payroll,
    PayrollRecord,
    Earning,
    Deduction,
    Payment,
    BankAccount,
    PerformanceReview,
    Position,
)


class EmployeeProfileSerializer(serializers.ModelSerializer):
    """Serialize employee HR profile data."""

    class Meta:
        model = EmployeeProfile
        fields = (
            "id",
            "user",
            "employee_id",
            "department",
            "position",
            "phone",
            "hire_date",
            "date_of_birth",
            "address",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
        )

    def validate_user(self, user):
        """Prevent multiple employee profiles for one user."""

        if EmployeeProfile.objects.filter(
            user=user
        ).exists():
            raise serializers.ValidationError(
                "This user already has an employee profile."
            )

        return user

class LeaveRequestSerializer(serializers.ModelSerializer):
    """Serialize employee leave requests."""

    class Meta:
        model = LeaveRequest
        fields = (
            "id",
            "employee",
            "leave_type",
            "start_date",
            "end_date",
            "reason",
            "status",
            "reviewed_by",
            "reviewed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "status",
            "reviewed_by",
            "reviewed_at",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        """Validate leave request dates."""

        start_date = attrs.get(
            "start_date",
        )
        end_date = attrs.get(
            "end_date",
        )

        if (
            start_date
            and end_date
            and start_date > end_date
        ):
            raise serializers.ValidationError(
                {
                    "end_date": (
                        "End date must be greater than "
                        "or equal to start date."
                    )
                }
            )

        return attrs

class BankAccountSerializer(serializers.ModelSerializer):
    """Serialize employee bank account data securely."""

    routing_number = serializers.CharField(
        write_only=True,
    )

    account_number = serializers.CharField(
        write_only=True,
    )

    masked_routing_number = serializers.SerializerMethodField()

    masked_account_number = serializers.SerializerMethodField()

    class Meta:
        model = BankAccount
        fields = (
            "id",
            "employee",
            "account_type",
            "routing_number",
            "account_number",
            "masked_routing_number",
            "masked_account_number",
            "last_four",
            "is_primary",
            "is_verified",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "masked_routing_number",
            "masked_account_number",
            "last_four",
            "is_verified",
            "created_at",
            "updated_at",
        )

    def get_masked_routing_number(self, obj):
        """Return only the last four digits of the routing number."""

        return f"*****{obj.routing_number[-4:]}"

    def get_masked_account_number(self, obj):
        """Return only the last four digits of the account number."""

        return f"****{obj.last_four}"

class PerformanceReviewSerializer(serializers.ModelSerializer):
    """Serialize employee performance review data."""

    class Meta:
        model = PerformanceReview
        fields = (
            "id",
            "employee",
            "reviewer",
            "review_period_start",
            "review_period_end",
            "score",
            "comments",
            "status",
            "submitted_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "reviewer",
            "status",
            "submitted_at",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        """Validate performance review data."""

        start_date = attrs.get("review_period_start")
        end_date = attrs.get("review_period_end")
        score = attrs.get("score")

        if (
            start_date
            and end_date
            and start_date > end_date
        ):
            raise serializers.ValidationError(
                {
                    "review_period_end": (
                        "Review period end date must be "
                        "greater than or equal to start date."
                    )
                }
            )

        if score is not None and (score < 0 or score > 5):
            raise serializers.ValidationError(
                {
                    "score": (
                        "Performance score must be between 0 and 5."
                    )
                }
            )

        return attrs
