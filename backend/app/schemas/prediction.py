from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FactorRead(BaseModel):
    feature: str
    label: str
    value: Any
    display_value: str
    contribution: float = Field(..., description="SHAP contribution (sign = direction of effect on risk)")
    direction: str


class PredictionRead(BaseModel):
    appointment_id: int
    no_show_probability: float = Field(..., ge=0, le=1)
    risk_level: str
    flagged_by_model: bool = Field(..., description="Probability is at/above the model's tuned decision threshold")
    top_factors: list[str]
    factors: list[FactorRead]
    explanation_note: str
    model_name: str
    model_version: str
    predicted_at: datetime


class BatchPredictionRequest(BaseModel):
    days_ahead: int = Field(14, ge=0, le=90, description="Score upcoming appointments within this many days")


class BatchPredictionResult(BaseModel):
    scored: int
    risk_counts: dict[str, int]
    model_version: str


class ModelInfo(BaseModel):
    loaded: bool
    model_name: str | None
    model_version: str | None
    decision_threshold: float | None
    risk_thresholds: dict[str, float]
    metrics: dict[str, Any] | None


class RetrainRequest(BaseModel):
    source: str = Field("db", pattern="^(db|csv)$", description="Train from live PostgreSQL history or the synthetic CSV")


class RetrainStatus(BaseModel):
    state: str
    detail: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    model_version: str | None = None
