"""Bridges the database and the ML layer: builds features from live history, scores, explains, persists."""

from __future__ import annotations

import json
import logging
import threading
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.ml.predict import NoShowPredictor, classify_risk, get_predictor
from app.ml.preprocessing import FEATURE_COLUMNS, RAW_COLUMNS, engineer_features
from app.models import Appointment, AppointmentPrediction
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.prediction_repository import PredictionRepository
from app.schemas.prediction import (
    BatchPredictionResult,
    FactorRead,
    ModelInfo,
    PredictionRead,
    RetrainStatus,
)

logger = logging.getLogger(__name__)


def _appointments_to_raw(appointments: Sequence[Appointment]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "appointment_id": a.id,
                "patient_id": a.patient_id,
                "date_of_birth": a.patient.date_of_birth,
                "department": a.department.name,
                "appointment_date": a.appointment_date,
                "appointment_time": a.appointment_time.strftime("%H:%M"),
                "booking_date": a.booking_date,
                "status": a.status,
            }
            for a in appointments
        ],
        columns=RAW_COLUMNS,
    )


def to_prediction_read(record: AppointmentPrediction) -> PredictionRead:
    factors = [FactorRead(**f) for f in record.factors]
    return PredictionRead(
        appointment_id=record.appointment_id,
        no_show_probability=record.no_show_probability,
        risk_level=record.risk_level,
        flagged_by_model=bool(record.features.get("_flagged_by_model", False)),
        top_factors=[f"{f.label}: {f.display_value}" for f in factors[:3]],
        factors=factors,
        explanation_note=NoShowPredictor.disclaimer(),
        model_name=record.model_name,
        model_version=record.model_version,
        predicted_at=record.created_at,
    )


class PredictionService:
    def __init__(self, db: Session, predictor: NoShowPredictor | None = None) -> None:
        self.db = db
        self.appointments = AppointmentRepository(db)
        self.predictions = PredictionRepository(db)
        self.predictor = predictor or get_predictor()

    def build_features(self, targets: Sequence[Appointment]) -> pd.DataFrame:
        """Feature rows for target appointments using each patient's full history in the DB."""
        history = self.appointments.patient_appointments(sorted({a.patient_id for a in targets}))
        features = engineer_features(_appointments_to_raw(history))
        target_ids = {a.id for a in targets}
        return features[features["appointment_id"].isin(target_ids)].set_index("appointment_id")

    def _persist(self, appointment_id: int, features: pd.DataFrame) -> AppointmentPrediction:
        result = self.predictor.predict_one(features.loc[[appointment_id], FEATURE_COLUMNS])
        stored_features: dict[str, Any] = json.loads(json.dumps(result.features, default=str))
        stored_features["_flagged_by_model"] = result.flagged_by_model
        return self.predictions.add(
            AppointmentPrediction(
                appointment_id=appointment_id,
                no_show_probability=result.no_show_probability,
                risk_level=result.risk_level,
                model_name=self.predictor.model_name or "unknown",
                model_version=self.predictor.model_version or "unknown",
                factors=[f.as_dict() for f in result.factors],
                features=stored_features,
            )
        )

    def predict(self, appointment_id: int) -> PredictionRead:
        appt = self.appointments.get_detailed(appointment_id)
        if appt is None:
            raise NotFoundError("Appointment", appointment_id)
        features = self.build_features([appt])
        record = self._persist(appointment_id, features)
        self.db.commit()
        logger.info(
            "Predicted appointment %s: p=%.3f risk=%s", appointment_id, record.no_show_probability, record.risk_level
        )
        return to_prediction_read(record)

    def latest(self, appointment_id: int) -> PredictionRead | None:
        record = self.predictions.latest_for_appointment(appointment_id)
        return to_prediction_read(record) if record else None

    def get_or_predict(self, appointment_id: int) -> PredictionRead:
        return self.latest(appointment_id) or self.predict(appointment_id)

    def predict_upcoming(self, days_ahead: int) -> BatchPredictionResult:
        today = date.today()
        targets = self.appointments.upcoming(today, today + timedelta(days=days_ahead))
        if not targets:
            return BatchPredictionResult(scored=0, risk_counts={}, model_version=self.predictor.model_version or "")
        # Load relationships needed for feature construction in one go.
        detailed = self.appointments.patient_appointments(sorted({a.patient_id for a in targets}))
        features = engineer_features(_appointments_to_raw(detailed)).set_index("appointment_id")
        counts: Counter[str] = Counter()
        for appt in targets:
            record = self._persist(appt.id, features)
            counts[record.risk_level] += 1
        self.db.commit()
        logger.info("Batch-scored %d upcoming appointments: %s", len(targets), dict(counts))
        return BatchPredictionResult(
            scored=len(targets), risk_counts=dict(counts), model_version=self.predictor.model_version or ""
        )

    def model_info(self) -> ModelInfo:
        settings = get_settings()
        metrics = None
        if settings.metrics_path.exists():
            metrics = json.loads(settings.metrics_path.read_text())
        return ModelInfo(
            loaded=self.predictor.is_loaded,
            model_name=self.predictor.model_name,
            model_version=self.predictor.model_version,
            decision_threshold=self.predictor.decision_threshold,
            risk_thresholds={"low_max": settings.RISK_LOW_MAX, "medium_max": settings.RISK_MEDIUM_MAX},
            metrics=metrics,
        )


# ---------------------------------------------------------------------- retraining
class RetrainManager:
    """Runs one retraining job at a time in a background thread and hot-reloads the model."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.status = RetrainStatus(state="idle")

    def start(self, source: str) -> RetrainStatus:
        with self._lock:
            if self.status.state == "running":
                raise ConflictError("A retraining job is already running")
            self.status = RetrainStatus(state="running", started_at=datetime.now(UTC), detail=f"source={source}")
        threading.Thread(target=self._run, args=(source,), daemon=True, name="retrain").start()
        return self.status

    def _run(self, source: str) -> None:
        from app.db.database import SessionLocal
        from app.ml.dataset import load_csv, load_from_database
        from app.ml.train import train

        settings = get_settings()
        try:
            if source == "db":
                with SessionLocal() as db:
                    raw = load_from_database(db)
            else:
                raw = load_csv(settings.dataset_path)
            metrics = train(raw, source, settings.MODEL_DIR)
            get_predictor().reload()
            selected = metrics["selected_model"]
            self.status = RetrainStatus(
                state="succeeded",
                started_at=self.status.started_at,
                finished_at=datetime.now(UTC),
                model_version=metrics["model_version"],
                detail=f"selected={selected}, test no-show F1={metrics['models'][selected]['test']['no_show_f1']}",
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Retraining failed")
            self.status = RetrainStatus(
                state="failed", started_at=self.status.started_at, finished_at=datetime.now(UTC), detail=str(exc)
            )


retrain_manager = RetrainManager()

__all__ = ["PredictionService", "classify_risk", "retrain_manager", "to_prediction_read"]
