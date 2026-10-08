from datetime import date, time
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String, Time, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import AppointmentStatus, sql_in

if TYPE_CHECKING:
    from app.models.appointment_status_history import AppointmentStatusHistory
    from app.models.department import Department
    from app.models.doctor import Doctor
    from app.models.patient import Patient
    from app.models.prediction import AppointmentPrediction
    from app.models.visit_history import VisitHistory


class Appointment(TimestampMixin, Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint(f"status IN ({sql_in(AppointmentStatus)})", name="status_valid"),
        CheckConstraint("booking_date <= appointment_date", name="booking_before_appointment"),
        Index("ix_appointments_patient_date", "patient_id", "appointment_date"),
        Index("ix_appointments_date_status", "appointment_date", "status"),
        # A doctor cannot hold two active appointments in the same slot.
        Index(
            "uq_appointments_doctor_slot_active",
            "doctor_id",
            "appointment_date",
            "appointment_time",
            unique=True,
            postgresql_where=text("status <> 'cancelled'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    appointment_date: Mapped[date] = mapped_column(Date, nullable=False)
    appointment_time: Mapped[time] = mapped_column(Time, nullable=False)
    booking_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=AppointmentStatus.SCHEDULED)

    patient: Mapped["Patient"] = relationship(back_populates="appointments")
    doctor: Mapped["Doctor"] = relationship(back_populates="appointments")
    department: Mapped["Department"] = relationship(back_populates="appointments")
    status_history: Mapped[list["AppointmentStatusHistory"]] = relationship(
        back_populates="appointment", order_by="AppointmentStatusHistory.changed_at", cascade="all, delete-orphan"
    )
    visit: Mapped["VisitHistory | None"] = relationship(back_populates="appointment", uselist=False)
    predictions: Mapped[list["AppointmentPrediction"]] = relationship(
        back_populates="appointment", order_by="AppointmentPrediction.created_at.desc()", cascade="all, delete-orphan"
    )
