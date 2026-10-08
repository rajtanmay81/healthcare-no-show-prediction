"""Computes hospital KPIs from PostgreSQL. The GenAI assistant only ever narrates these numbers."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.models.enums import RiskLevel
from app.ml.predict import classify_risk
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.department_repository import DepartmentRepository
from app.schemas.analytics import (
    AnalyticsPeriod,
    DayOfWeekStat,
    DepartmentStats,
    HighRiskAppointment,
    NoShowTrends,
    Overview,
    ProbabilityBucket,
    RiskBucket,
    RiskDistribution,
    StatusCounts,
    TrendPoint,
)

logger = logging.getLogger(__name__)
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
GRANULARITIES = {"day", "week", "month"}


def rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


class AnalyticsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = AnalyticsRepository(db)
        self.departments = DepartmentRepository(db)

    def _period(self, date_from: date | None, date_to: date | None, department_id: int | None) -> AnalyticsPeriod:
        if date_from and date_to and date_from > date_to:
            raise BusinessRuleError("date_from must be on or before date_to")
        name = None
        if department_id:
            dept = self.departments.get(department_id)
            if dept is None:
                raise NotFoundError("Department", department_id)
            name = dept.name
        return AnalyticsPeriod(date_from=date_from, date_to=date_to, department_id=department_id, department_name=name)

    def overview(self, date_from: date | None = None, date_to: date | None = None, department_id: int | None = None) -> Overview:
        period = self._period(date_from, date_to, department_id)
        row = self.repo.status_counts(date_from, date_to, department_id)
        counts = StatusCounts(**row._mapping)
        today = date.today()
        upcoming, high_risk = self.repo.upcoming_counts(max(today, date_from) if date_from else today, date_to, department_id)
        return Overview(
            period=period,
            total_appointments=counts.total,
            status_counts=counts,
            completed=counts.completed,
            cancelled=counts.cancelled,
            no_shows=counts.no_show,
            upcoming=upcoming,
            high_risk_upcoming=high_risk,
            no_show_rate=rate(counts.no_show, counts.completed + counts.no_show),
            cancellation_rate=rate(counts.cancelled, counts.total),
        )

    def departments_stats(self, date_from: date | None = None, date_to: date | None = None) -> list[DepartmentStats]:
        self._period(date_from, date_to, None)
        rows = self.repo.by_department(date_from, date_to, date.today())
        return [
            DepartmentStats(
                department_id=r.id,
                department_name=r.name,
                total_appointments=r.total,
                completed=r.completed,
                no_shows=r.no_show,
                cancelled=r.cancelled,
                upcoming=r.upcoming,
                no_show_rate=rate(r.no_show, r.completed + r.no_show),
                cancellation_rate=rate(r.cancelled, r.total),
                avg_booking_lead_days=round(float(r.avg_lead), 1) if r.avg_lead is not None else None,
                high_risk_upcoming=r.high_risk,
                avg_predicted_risk_upcoming=round(float(r.avg_risk), 4) if r.avg_risk is not None else None,
            )
            for r in rows
        ]

    def no_show_trends(
        self,
        granularity: str = "month",
        date_from: date | None = None,
        date_to: date | None = None,
        department_id: int | None = None,
    ) -> NoShowTrends:
        if granularity not in GRANULARITIES:
            raise BusinessRuleError(f"granularity must be one of {sorted(GRANULARITIES)}")
        period = self._period(date_from, date_to, department_id)
        rows = self.repo.trends(granularity, date_from, date_to, department_id)
        points = [
            TrendPoint(
                period=r.bucket,
                total=r.total,
                completed=r.completed,
                no_shows=r.no_show,
                cancelled=r.cancelled,
                no_show_rate=rate(r.no_show, r.completed + r.no_show),
            )
            for r in rows
        ]
        return NoShowTrends(granularity=granularity, period=period, points=points)

    def day_of_week(
        self, date_from: date | None = None, date_to: date | None = None, department_id: int | None = None
    ) -> list[DayOfWeekStat]:
        self._period(date_from, date_to, department_id)
        rows = {int(r.dow): r for r in self.repo.by_day_of_week(date_from, date_to, department_id)}
        stats = []
        for idx, name in enumerate(DAY_NAMES, start=1):
            r = rows.get(idx)
            outcomes, no_shows = (int(r.outcomes), int(r.no_show)) if r else (0, 0)
            stats.append(DayOfWeekStat(day=name, day_index=idx, total=outcomes, no_shows=no_shows, no_show_rate=rate(no_shows, outcomes)))
        return stats

    def risk_distribution(self, days_ahead: int = 30, department_id: int | None = None) -> RiskDistribution:
        today = date.today()
        rows = self.repo.upcoming_with_predictions(today, today + timedelta(days=days_ahead), department_id)
        scored = [r for r in rows if r.no_show_probability is not None]
        by_level = {level.value: 0 for level in RiskLevel}
        edges = [i / 10 for i in range(11)]
        hist = [0] * 10
        for r in scored:
            by_level[classify_risk(r.no_show_probability).value] += 1
            hist[min(int(r.no_show_probability * 10), 9)] += 1
        return RiskDistribution(
            days_ahead=days_ahead,
            scored_upcoming=len(scored),
            unscored_upcoming=len(rows) - len(scored),
            by_level=[RiskBucket(risk_level=k, count=v) for k, v in by_level.items()],
            histogram=[
                ProbabilityBucket(bucket=f"{edges[i]:.0%}-{edges[i + 1]:.0%}", count=hist[i]) for i in range(10)
            ],
        )

    def high_risk_upcoming(
        self,
        days_ahead: int = 14,
        min_probability: float | None = None,
        department_id: int | None = None,
        limit: int = 20,
    ) -> list[HighRiskAppointment]:
        threshold = get_settings().RISK_MEDIUM_MAX if min_probability is None else min_probability
        today = date.today()
        rows = self.repo.high_risk_upcoming(today, today + timedelta(days=days_ahead), threshold, department_id, limit)
        items = []
        for r in rows:
            top = next((f for f in (r.factors or []) if f.get("direction") == "increases_risk"), None)
            items.append(
                HighRiskAppointment(
                    appointment_id=r.id,
                    patient_id=r.patient_id,
                    patient_name=r.patient_name,
                    department_name=r.department_name,
                    doctor_name=r.doctor_name,
                    appointment_date=r.appointment_date,
                    appointment_time=r.appointment_time,
                    status=r.status,
                    no_show_probability=r.no_show_probability,
                    risk_level=classify_risk(r.no_show_probability).value,
                    top_factor=f"{top['label']}: {top['display_value']}" if top else None,
                )
            )
        return items
