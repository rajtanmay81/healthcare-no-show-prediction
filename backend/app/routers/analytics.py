from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.dependencies import AnyRole, DbSession
from app.schemas.analytics import (
    DayOfWeekStat,
    DepartmentStats,
    HighRiskAppointment,
    NoShowTrends,
    Overview,
    RiskDistribution,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/overview", response_model=Overview)
def overview(
    db: DbSession, _: AnyRole, date_from: date | None = None, date_to: date | None = None, department_id: int | None = None
) -> Overview:
    return AnalyticsService(db).overview(date_from, date_to, department_id)


@router.get("/departments", response_model=list[DepartmentStats])
def departments(db: DbSession, _: AnyRole, date_from: date | None = None, date_to: date | None = None) -> list[DepartmentStats]:
    return AnalyticsService(db).departments_stats(date_from, date_to)


@router.get("/no-show-trends", response_model=NoShowTrends)
def no_show_trends(
    db: DbSession,
    _: AnyRole,
    granularity: Annotated[str, Query(pattern="^(day|week|month)$")] = "month",
    date_from: date | None = None,
    date_to: date | None = None,
    department_id: int | None = None,
) -> NoShowTrends:
    return AnalyticsService(db).no_show_trends(granularity, date_from, date_to, department_id)


@router.get("/day-of-week", response_model=list[DayOfWeekStat])
def day_of_week(
    db: DbSession, _: AnyRole, date_from: date | None = None, date_to: date | None = None, department_id: int | None = None
) -> list[DayOfWeekStat]:
    return AnalyticsService(db).day_of_week(date_from, date_to, department_id)


@router.get("/risk-distribution", response_model=RiskDistribution)
def risk_distribution(
    db: DbSession, _: AnyRole, days_ahead: Annotated[int, Query(ge=0, le=180)] = 30, department_id: int | None = None
) -> RiskDistribution:
    return AnalyticsService(db).risk_distribution(days_ahead, department_id)


@router.get("/high-risk-upcoming", response_model=list[HighRiskAppointment])
def high_risk_upcoming(
    db: DbSession,
    _: AnyRole,
    days_ahead: Annotated[int, Query(ge=0, le=180)] = 14,
    min_probability: Annotated[float | None, Query(ge=0, le=1)] = None,
    department_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
) -> list[HighRiskAppointment]:
    return AnalyticsService(db).high_risk_upcoming(days_ahead, min_probability, department_id, limit)
