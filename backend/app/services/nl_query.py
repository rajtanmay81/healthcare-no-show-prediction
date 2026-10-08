"""Deterministic natural-language query planner for the admin assistant.

The planner maps a question to an *intent*, a *period* and an optional *department* so that
the backend can compute the answer from PostgreSQL **before** the LLM is involved. The LLM
never decides which numbers exist - it only phrases the computed facts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum


class Intent(StrEnum):
    OVERVIEW = "overview"
    NO_SHOW_COUNT = "no_show_count"
    DEPARTMENT_RANKING = "department_ranking"
    DEPARTMENT_RATE = "department_rate"
    DAY_OF_WEEK = "day_of_week"
    TRENDS = "trends"
    HIGH_RISK = "high_risk"
    CANCELLATIONS = "cancellations"
    MODEL_PERFORMANCE = "model_performance"


class PeriodName(StrEnum):
    TODAY = "today"
    YESTERDAY = "yesterday"
    THIS_WEEK = "this_week"
    LAST_WEEK = "last_week"
    LAST_7_DAYS = "last_7_days"
    THIS_MONTH = "this_month"
    LAST_MONTH = "last_month"
    LAST_30_DAYS = "last_30_days"
    LAST_90_DAYS = "last_90_days"
    THIS_YEAR = "this_year"
    ALL_TIME = "all_time"
    CUSTOM = "custom"


@dataclass(frozen=True)
class Period:
    name: str
    date_from: date | None
    date_to: date | None
    label: str


@dataclass(frozen=True)
class QueryPlan:
    intent: Intent
    period: Period
    department_id: int | None
    department_name: str | None
    ranking: str  # "highest" | "lowest"


def resolve_period(name: PeriodName | str, today: date | None = None) -> Period:
    today = today or date.today()
    name = PeriodName(name)
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)
    if name == PeriodName.TODAY:
        return Period(name, today, today, f"today ({today:%d %b %Y})")
    if name == PeriodName.YESTERDAY:
        y = today - timedelta(days=1)
        return Period(name, y, y, f"yesterday ({y:%d %b %Y})")
    if name == PeriodName.THIS_WEEK:
        return Period(name, week_start, week_start + timedelta(days=6), f"this week ({week_start:%d %b} - {week_start + timedelta(days=6):%d %b %Y})")
    if name == PeriodName.LAST_WEEK:
        start = week_start - timedelta(days=7)
        return Period(name, start, start + timedelta(days=6), f"last week ({start:%d %b} - {start + timedelta(days=6):%d %b %Y})")
    if name == PeriodName.LAST_7_DAYS:
        return Period(name, today - timedelta(days=6), today, "the last 7 days")
    if name == PeriodName.THIS_MONTH:
        return Period(name, month_start, next_month - timedelta(days=1), f"this month ({today:%B %Y})")
    if name == PeriodName.LAST_MONTH:
        end = month_start - timedelta(days=1)
        return Period(name, end.replace(day=1), end, f"last month ({end:%B %Y})")
    if name == PeriodName.LAST_30_DAYS:
        return Period(name, today - timedelta(days=29), today, "the last 30 days")
    if name == PeriodName.LAST_90_DAYS:
        return Period(name, today - timedelta(days=89), today, "the last 90 days")
    if name == PeriodName.THIS_YEAR:
        return Period(name, today.replace(month=1, day=1), today.replace(month=12, day=31), f"this year ({today.year})")
    return Period(PeriodName.ALL_TIME, None, None, "all recorded appointments")


_LAST_N = re.compile(r"\b(?:last|past|previous)\s+(\d{1,3})\s+(day|week|month)s?\b")
_PERIOD_PATTERNS: list[tuple[re.Pattern[str], PeriodName]] = [
    (re.compile(r"\btoday'?s?\b"), PeriodName.TODAY),
    (re.compile(r"\byesterday'?s?\b"), PeriodName.YESTERDAY),
    (re.compile(r"\bthis week'?s?\b|\bcurrent week\b"), PeriodName.THIS_WEEK),
    (re.compile(r"\blast week'?s?\b|\bprevious week\b"), PeriodName.LAST_WEEK),
    (re.compile(r"\bthis month'?s?\b|\bcurrent month\b"), PeriodName.THIS_MONTH),
    (re.compile(r"\blast month'?s?\b|\bprevious month\b"), PeriodName.LAST_MONTH),
    (re.compile(r"\bthis year'?s?\b"), PeriodName.THIS_YEAR),
]

DEPARTMENT_ALIASES: dict[str, tuple[str, ...]] = {
    "General Medicine": ("general medicine", "general practice", "internal medicine", "gp"),
    "Cardiology": ("cardiology", "cardio", "cardiac", "heart"),
    "Dermatology": ("dermatology", "derma", "derm", "skin"),
    "Orthopedics": ("orthopedics", "orthopaedics", "ortho", "orthopedic", "bone"),
    "Neurology": ("neurology", "neuro"),
    "Pediatrics": ("pediatrics", "paediatrics", "pediatric", "paediatric", "children", "child"),
    "ENT": ("ent", "ear nose throat", "ear, nose and throat", "otolaryngology"),
    "Gynecology": ("gynecology", "gynaecology", "gyn", "gynae", "obgyn", "ob-gyn"),
}


def _parse_period(text: str, today: date, intent: Intent) -> Period:
    match = _LAST_N.search(text)
    if match:
        n, unit = int(match.group(1)), match.group(2)
        days = n * {"day": 1, "week": 7, "month": 30}[unit]
        return Period(PeriodName.CUSTOM, today - timedelta(days=days - 1), today, f"the last {n} {unit}{'s' if n != 1 else ''}")
    for pattern, name in _PERIOD_PATTERNS:
        if pattern.search(text):
            return resolve_period(name, today)
    if intent == Intent.TRENDS:
        start = (today.replace(day=1) - timedelta(days=365)).replace(day=1)
        return Period(PeriodName.CUSTOM, start, today, "the last 12 months")
    return resolve_period(PeriodName.ALL_TIME, today)


def _match_department(text: str, departments: dict[str, int]) -> tuple[int | None, str | None]:
    for name, dept_id in departments.items():
        aliases = DEPARTMENT_ALIASES.get(name, ()) + (name.lower(),)
        for alias in sorted(aliases, key=len, reverse=True):
            if re.search(rf"\b{re.escape(alias)}\b", text):
                return dept_id, name
    return None, None


def plan_query(question: str, departments: dict[str, int], today: date | None = None) -> QueryPlan:
    """Build a query plan. ``departments`` maps department name -> id (from the database)."""
    today = today or date.today()
    text = " ".join(question.lower().split())
    dept_id, dept_name = _match_department(text, departments)
    ranking = "lowest" if re.search(r"\b(lowest|least|best|fewest|minimum)\b", text) else "highest"
    mentions_no_show = bool(re.search(r"no[- ]?shows?|missed|miss|absent|did not (show|attend)|didn'?t (show|attend)", text))

    if re.search(r"\b(model|accuracy|recall|precision|roc|auc|f1|algorithm)\b", text):
        intent = Intent.MODEL_PERFORMANCE
    elif re.search(r"high[- ]risk|risky|at[- ]risk|likely to (miss|no[- ]?show)|upcoming risk", text):
        intent = Intent.HIGH_RISK
    elif re.search(r"\b(which|what) day\b|day of (the )?week|weekday|busiest day", text):
        intent = Intent.DAY_OF_WEEK
    elif dept_id is None and re.search(
        r"\b(which|what) (department|dept|specialty|clinic)|departments?\b.*\b(highest|lowest|most|least|worst|best|rank|compare)|by department|department[- ]wise|each department",
        text,
    ):
        intent = Intent.DEPARTMENT_RANKING
    elif re.search(r"\bcancel", text):
        intent = Intent.CANCELLATIONS
    elif re.search(r"trend|summar|overview|performance|how (are|is|did|were)|report|over time", text):
        intent = Intent.TRENDS
    elif dept_id is not None:
        intent = Intent.DEPARTMENT_RATE
    elif mentions_no_show and re.search(r"how many|number of|count|total", text):
        intent = Intent.NO_SHOW_COUNT
    else:
        intent = Intent.OVERVIEW

    period = _parse_period(text, today, intent)
    return QueryPlan(intent=intent, period=period, department_id=dept_id, department_name=dept_name, ranking=ranking)
