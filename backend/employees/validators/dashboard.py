from datetime import date

from rest_framework import serializers


MIN_DAYS = 1
MAX_DAYS = 365

MIN_RECENT_LIMIT = 1
MAX_RECENT_LIMIT = 100


def validate_dashboard_days(value):
    """Validate the number of days used by dashboard metrics."""
    if not MIN_DAYS <= value <= MAX_DAYS:
        raise serializers.ValidationError(
            f"Ensure this value is between {MIN_DAYS} and {MAX_DAYS}."
        )

    return value


def validate_dashboard_recent_limit(value):
    """Validate the maximum number of recent records returned."""
    if not MIN_RECENT_LIMIT <= value <= MAX_RECENT_LIMIT:
        raise serializers.ValidationError(
            f"Ensure this value is between "
            f"{MIN_RECENT_LIMIT} and {MAX_RECENT_LIMIT}."
        )

    return value


def validate_dashboard_as_of(value):
    """Reject dashboard reference dates in the future."""
    if value is not None and value > date.today():
        raise serializers.ValidationError(
            "The reference date cannot be in the future."
        )

    return value
    
