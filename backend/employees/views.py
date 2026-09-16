from rest_framework import viewsets

from .models import EmployeeProfile
from .permissions import EmployeeProfilePermission
from .serializers import EmployeeProfileSerializer


class EmployeeProfileViewSet(viewsets.ModelViewSet):
    """API endpoint for managing employee profiles."""

    serializer_class = EmployeeProfileSerializer
    permission_classes = (
        EmployeeProfilePermission,
    )

    def get_queryset(self):
        """Restrict employees to their own profile."""

        user = self.request.user

        if user.role == "EMPLOYEE":
            return EmployeeProfile.objects.filter(
                user=user
            )

        return EmployeeProfile.objects.all()
