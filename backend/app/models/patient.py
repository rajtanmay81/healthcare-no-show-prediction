from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import Gender, sql_in

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.visit_history import VisitHistory


class Patient(TimestampMixin, Base):
    """Only the minimum demographic/contact data needed for scheduling is stored."""

    __tablename__ = "patients"
    __table_args__ = (CheckConstraint(f"gender IN ({sql_in(Gender)})", name="gender_valid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[str] = mapped_column(String(20), nullable=False, default=Gender.UNDISCLOSED)
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(255), unique=True)

    appointments: Mapped[list["Appointment"]] = relationship(back_populates="patient")
    visits: Mapped[list["VisitHistory"]] = relationship(back_populates="patient")
