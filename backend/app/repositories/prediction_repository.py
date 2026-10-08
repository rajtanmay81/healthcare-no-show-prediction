from sqlalchemy import select

from app.models import AppointmentPrediction
from app.repositories.base import BaseRepository


class PredictionRepository(BaseRepository[AppointmentPrediction]):
    model = AppointmentPrediction

    def latest_for_appointment(self, appointment_id: int) -> AppointmentPrediction | None:
        stmt = (
            select(AppointmentPrediction)
            .where(AppointmentPrediction.appointment_id == appointment_id)
            .order_by(AppointmentPrediction.created_at.desc(), AppointmentPrediction.id.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)
