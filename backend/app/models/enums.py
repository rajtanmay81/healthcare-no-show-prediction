"""Enumerations shared by models, schemas and services."""

from enum import StrEnum


class AppointmentStatus(StrEnum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


# Statuses whose outcome is final; they feed the model's historical features.
TERMINAL_STATUSES = frozenset(
    {AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW}
)
UPCOMING_STATUSES = frozenset({AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED})

# Allowed state machine transitions.
ALLOWED_TRANSITIONS: dict[AppointmentStatus, frozenset[AppointmentStatus]] = {
    AppointmentStatus.SCHEDULED: frozenset(
        {AppointmentStatus.CONFIRMED, AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW}
    ),
    AppointmentStatus.CONFIRMED: frozenset(
        {AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW}
    ),
    AppointmentStatus.COMPLETED: frozenset(),
    AppointmentStatus.CANCELLED: frozenset(),
    AppointmentStatus.NO_SHOW: frozenset(),
}


class VisitStatus(StrEnum):
    ATTENDED = "attended"
    MISSED = "missed"


class Gender(StrEnum):
    FEMALE = "female"
    MALE = "male"
    OTHER = "other"
    UNDISCLOSED = "undisclosed"


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    DOCTOR = "DOCTOR"
    STAFF = "STAFF"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


def sql_in(values: type[StrEnum]) -> str:
    """Render an enum as a SQL ``IN (...)`` list for check constraints."""
    return ", ".join(f"'{v.value}'" for v in values)
