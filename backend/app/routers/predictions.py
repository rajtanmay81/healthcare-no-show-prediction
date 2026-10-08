from fastapi import APIRouter, status

from app.core.dependencies import AdminOnly, AdminOrStaff, AnyRole, DbSession
from app.core.exceptions import NotFoundError
from app.schemas.prediction import (
    BatchPredictionRequest,
    BatchPredictionResult,
    ModelInfo,
    PredictionRead,
    RetrainRequest,
    RetrainStatus,
)
from app.services.appointment_service import AppointmentService
from app.services.prediction_service import PredictionService, retrain_manager

router = APIRouter(tags=["Predictions"])


@router.post(
    "/appointments/{appointment_id}/predict-no-show",
    response_model=PredictionRead,
    summary="Score an appointment and explain the model factors",
)
def predict_no_show(appointment_id: int, db: DbSession, _: AdminOrStaff) -> PredictionRead:
    return PredictionService(db).predict(appointment_id)


@router.get("/appointments/{appointment_id}/prediction", response_model=PredictionRead, summary="Latest stored prediction")
def latest_prediction(appointment_id: int, db: DbSession, user: AnyRole) -> PredictionRead:
    AppointmentService(db).get(appointment_id, user)  # 404 / doctor-scope check
    prediction = PredictionService(db).latest(appointment_id)
    if prediction is None:
        raise NotFoundError("Prediction for appointment", appointment_id)
    return prediction


@router.post("/predictions/batch", response_model=BatchPredictionResult, summary="Score all upcoming appointments")
def batch_predict(payload: BatchPredictionRequest, db: DbSession, _: AdminOrStaff) -> BatchPredictionResult:
    return PredictionService(db).predict_upcoming(payload.days_ahead)


@router.get("/predictions/model", response_model=ModelInfo, summary="Active model, thresholds and evaluation metrics")
def model_info(db: DbSession, _: AnyRole) -> ModelInfo:
    return PredictionService(db).model_info()


@router.post(
    "/predictions/retrain",
    response_model=RetrainStatus,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retrain on the latest data (runs in background, hot-reloads the model)",
)
def retrain(payload: RetrainRequest, _: AdminOnly) -> RetrainStatus:
    return retrain_manager.start(payload.source)


@router.get("/predictions/retrain/status", response_model=RetrainStatus)
def retrain_status(_: AdminOnly) -> RetrainStatus:
    return retrain_manager.status
