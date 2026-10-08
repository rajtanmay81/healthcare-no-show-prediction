from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin
from app.models.enums import RiskLevel, sql_in

if TYPE_CHECKING:
    from app.models.appointment import Appointment


class AppointmentPrediction(CreatedAtMixin, Base):
    """Every model score is persisted so predictions are auditable and reusable by analytics."""

    __tablename__ = "appointment_predictions"
    __table_args__ = (
        CheckConstraint(f"risk_level IN ({sql_in(RiskLevel)})", name="risk_level_valid"),
        CheckConstraint("no_show_probability >= 0 AND no_show_probability <= 1", name="probability_range"),
        Index("ix_predictions_appointment_created", "appointment_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False)
    no_show_probability: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False)
    model_name: Mapped[str] = mapped_column(String(50), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    factors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    features: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    appointment: Mapped["Appointment"] = relationship(back_populates="predictions")
