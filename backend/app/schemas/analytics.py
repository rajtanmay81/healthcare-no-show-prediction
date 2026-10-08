from datetime import date, time

from pydantic import BaseModel, Field

NO_SHOW_RATE_DEFINITION = "no_shows / (completed + no_shows); cancelled and upcoming appointments are excluded"


class AnalyticsPeriod(BaseModel):
    date_from: date | None
    date_to: date | None
    department_id: int | None = None
    department_name: str | None = None


class StatusCounts(BaseModel):
    total: int = 0
    scheduled: int = 0
    confirmed: int = 0
    completed: int = 0
    cancelled: int = 0
    no_show: int = 0


class Overview(BaseModel):
    period: AnalyticsPeriod
    total_appointments: int
    status_counts: StatusCounts
    completed: int
    cancelled: int
    no_shows: int
    upcoming: int
    high_risk_upcoming: int
    no_show_rate: float | None = Field(None, description=NO_SHOW_RATE_DEFINITION)
    cancellation_rate: float | None = Field(None, description="cancelled / total")
    no_show_rate_definition: str = NO_SHOW_RATE_DEFINITION


class DepartmentStats(BaseModel):
    department_id: int
    department_name: str
    total_appointments: int
    completed: int
    no_shows: int
    cancelled: int
    upcoming: int
    no_show_rate: float | None
    cancellation_rate: float | None
    avg_booking_lead_days: float | None
    high_risk_upcoming: int
    avg_predicted_risk_upcoming: float | None


class TrendPoint(BaseModel):
    period: date
    total: int
    completed: int
    no_shows: int
    cancelled: int
    no_show_rate: float | None


class NoShowTrends(BaseModel):
    granularity: str
    period: AnalyticsPeriod
    points: list[TrendPoint]


class DayOfWeekStat(BaseModel):
    day: str
    day_index: int
    total: int
    no_shows: int
    no_show_rate: float | None


class RiskBucket(BaseModel):
    risk_level: str
    count: int


class ProbabilityBucket(BaseModel):
    bucket: str
    count: int


class RiskDistribution(BaseModel):
    days_ahead: int
    scored_upcoming: int
    unscored_upcoming: int
    by_level: list[RiskBucket]
    histogram: list[ProbabilityBucket]


class HighRiskAppointment(BaseModel):
    appointment_id: int
    patient_id: int
    patient_name: str
    department_name: str
    doctor_name: str
    appointment_date: date
    appointment_time: time
    status: str
    no_show_probability: float
    risk_level: str
    top_factor: str | None
