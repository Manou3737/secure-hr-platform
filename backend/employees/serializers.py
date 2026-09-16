from rest_framework import serializers

from .models import EmployeeProfile


class EmployeeProfileSerializer(serializers.ModelSerializer):
    """Serialize employee HR profile data."""

    class Meta:
        model = EmployeeProfile
        fields = (
            "id",
            "user",
            "employee_id",
            "department",
            "job_title",
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
