from fastapi import APIRouter

from app.core.dependencies import AdminOrStaff, DbSession
from app.schemas.ai import (
    ChatRequest,
    ChatResponse,
    DepartmentSummaryRequest,
    DepartmentSummaryResponse,
    ExplainPredictionRequest,
    ExplainPredictionResponse,
    ReminderRequest,
    ReminderResponse,
)
from app.services.ai_service import AIService

router = APIRouter(prefix="/ai", tags=["AI Assistant"])


@router.post("/explain-prediction", response_model=ExplainPredictionResponse)
def explain_prediction(payload: ExplainPredictionRequest, db: DbSession, _: AdminOrStaff) -> ExplainPredictionResponse:
    """Plain-language explanation of the model factors behind a prediction (never the 'actual reason')."""
    return AIService(db).explain_prediction(payload.appointment_id, payload.refresh)


@router.post("/generate-reminder", response_model=ReminderResponse)
def generate_reminder(payload: ReminderRequest, db: DbSession, _: AdminOrStaff) -> ReminderResponse:
    """Draft an SMS / email / WhatsApp reminder. Risk information is never included in patient messages."""
    return AIService(db).generate_reminder(payload.appointment_id, payload.channel, payload.tone, payload.request_confirmation)


@router.post("/department-summary", response_model=DepartmentSummaryResponse)
def department_summary(payload: DepartmentSummaryRequest, db: DbSession, _: AdminOrStaff) -> DepartmentSummaryResponse:
    """Statistics are computed in PostgreSQL first; the LLM only summarises them."""
    return AIService(db).department_summary(payload)


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: DbSession, _: AdminOrStaff) -> ChatResponse:
    """Natural-language analytics: question -> query plan -> SQL facts -> grounded answer."""
    return AIService(db).chat(payload.question)
