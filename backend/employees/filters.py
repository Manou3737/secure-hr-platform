
import django_filters

from employees.models import DocumentAccessLog


class DocumentAccessLogFilter(django_filters.FilterSet):
    """Filter document audit logs by action, user, document, and date range."""

    action = django_filters.ChoiceFilter(
        choices=DocumentAccessLog.Action.choices,
    )
    user = django_filters.NumberFilter(field_name="user_id")
    document = django_filters.UUIDFilter(field_name="document_id")
    created_after = django_filters.IsoDateTimeFilter(
        field_name="created_at",
        lookup_expr="gte",
    )
    created_before = django_filters.IsoDateTimeFilter(
        field_name="created_at",
        lookup_expr="lte",
    )

    class Meta:
        model = DocumentAccessLog
        fields = (
            "action",
            "user",
            "document",
            "created_after",
            "created_before",
        )
