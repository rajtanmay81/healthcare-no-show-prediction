"""Import every model so SQLAlchemy metadata (and Alembic autogenerate) sees all tables."""

from app.models.appointment import Appointment
from app.models.appointment_status_history import AppointmentStatusHistory
from app.models.department import Department
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.prediction import AppointmentPrediction
from app.models.user import User
from app.models.visit_history import VisitHistory

__all__ = [
    "Appointment",
    "AppointmentPrediction",
    "AppointmentStatusHistory",
    "Department",
    "Doctor",
    "Patient",
    "User",
    "VisitHistory",
]
