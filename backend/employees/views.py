from rest_framework import viewsets

from accounts.security import create_security_event

from .models import EmployeeProfile
from .permissions import EmployeeProfilePermission
from .serializers import EmployeeProfileSerializer


class EmployeeProfileViewSet(viewsets.ModelViewSet):
    """API endpoint for managing employee profiles."""

    serializer_class = EmployeeProfileSerializer
    permission_classes = (
        EmployeeProfilePermission,
    )

    def perform_create(self, serializer):
        """Create an employee and record the security event."""

        employee = serializer.save()

        create_security_event(
            request=self.request,
            event_type="EMPLOYEE_CREATED",
            details=(
                f"Employee {employee.employee_id} created."
            ),
        )

    def perform_update(self, serializer):
        """Update an employee and record the security event."""

        employee = serializer.save()

        create_security_event(
            request=self.request,
            event_type="EMPLOYEE_UPDATED",
            details=(
                f"Employee {employee.employee_id} updated."
            ),
        )

    def perform_destroy(self, instance):
        """Delete an employee and record the security event."""

        employee_id = instance.employee_id

        create_security_event(
            request=self.request,
            event_type="EMPLOYEE_DELETED",
            details=(
                f"Employee {employee_id} deleted."
            ),
        )

        instance.delete()
        
    def get_queryset(self):
        """Restrict employees to their own profile."""

        user = self.request.user

        if user.role == "EMPLOYEE":
            return EmployeeProfile.objects.filter(
                user=user
            )

        return EmployeeProfile.objects.all()
