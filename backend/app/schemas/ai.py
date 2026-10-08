from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.prediction import PredictionRead
from app.services.nl_query import PeriodName


class ReminderChannel(StrEnum):
    SMS = "sms"
    EMAIL = "email"
    WHATSAPP = "whatsapp"


class ReminderTone(StrEnum):
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"


class AIMeta(BaseModel):
    llm_used: bool = Field(..., description="False when the grounded template fallback produced the text")
    provider: str
    model: str | None
    grounding_check: str = Field(..., description="passed | fallback_used | not_applicable")


class ExplainPredictionRequest(BaseModel):
    appointment_id: int = Field(..., gt=0)
    refresh: bool = Field(False, description="Re-score the appointment before explaining")


class ExplainPredictionResponse(BaseModel):
    appointment_id: int
    explanation: str
    prediction: PredictionRead
    disclaimer: str
    meta: AIMeta


class ReminderRequest(BaseModel):
    appointment_id: int = Field(..., gt=0)
    channel: ReminderChannel = ReminderChannel.SMS
    tone: ReminderTone = ReminderTone.PROFESSIONAL
    request_confirmation: bool = True


class ReminderResponse(BaseModel):
    appointment_id: int
    channel: ReminderChannel
    tone: ReminderTone
    subject: str | None
    message: str
    character_count: int
    meta: AIMeta


class DepartmentSummaryRequest(BaseModel):
    department_id: int | None = Field(None, gt=0, description="Omit for a hospital-wide summary")
    period: PeriodName = PeriodName.TODAY
    date_from: date | None = None
    date_to: date | None = None

    @model_validator(mode="after")
    def _custom_range(self) -> "DepartmentSummaryRequest":
        if self.period == PeriodName.CUSTOM:
            if not (self.date_from and self.date_to):
                raise ValueError("date_from and date_to are required for a custom period")
            if self.date_from > self.date_to:
                raise ValueError("date_from must be on or before date_to")
        return self


class DepartmentSummaryResponse(BaseModel):
    summary: str
    period_label: str
    date_from: date | None
    date_to: date | None
    department_name: str | None
    statistics: dict[str, Any]
    meta: AIMeta


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)

    @field_validator("question")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("question is too short")
        return value


class ChatResponse(BaseModel):
    question: str
    answer: str
    intent: str
    period_label: str
    department_name: str | None
    data: dict[str, Any] = Field(..., description="The computed facts the answer is grounded on")
    meta: AIMeta
