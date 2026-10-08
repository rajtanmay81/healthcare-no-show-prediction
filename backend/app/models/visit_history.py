from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin
from app.models.enums import VisitStatus, sql_in

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.patient import Patient


class VisitHistory(CreatedAtMixin, Base):
    """Outcome record written when an appointment is closed as completed or no-show."""

    __tablename__ = "visit_history"
    __table_args__ = (CheckConstraint(f"visit_status IN ({sql_in(VisitStatus)})", name="visit_status_valid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    appointment_id: Mapped[int] = mapped_column(
        ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    visit_date: Mapped[date] = mapped_column(Date, nullable=False)
    visit_status: Mapped[str] = mapped_column(String(20), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    patient: Mapped["Patient"] = relationship(back_populates="visits")
    appointment: Mapped["Appointment"] = relationship(back_populates="visit")
