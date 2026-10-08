"""GenAI admin assistant.

Grounding contract
------------------
1. Every number is computed by the backend (SQL analytics / the ML model) *before* the LLM is called.
2. The LLM receives those facts as JSON and may only phrase them.
3. Every LLM answer is checked: if it contains a number that does not appear in the facts,
   the answer is discarded and a deterministic template built from the same facts is returned.
4. Without a configured provider the assistant still works, using the templates.
5. Patient names and contact details are never sent to the LLM, except a first name for reminders.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, time
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.ml.predict import NoShowPredictor
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.department_repository import DepartmentRepository
from app.schemas.ai import (
    AIMeta,
    ChatResponse,
    DepartmentSummaryRequest,
    DepartmentSummaryResponse,
    ExplainPredictionResponse,
    ReminderChannel,
    ReminderResponse,
    ReminderTone,
)
from app.schemas.analytics import NO_SHOW_RATE_DEFINITION, Overview
from app.services.analytics_service import AnalyticsService
from app.services.llm_client import LLMClient, LLMError, get_llm_client
from app.services.nl_query import Intent, Period, PeriodName, QueryPlan, plan_query, resolve_period
from app.services.prediction_service import PredictionService

logger = logging.getLogger(__name__)

_NUMBER = re.compile(r"(?<![A-Za-z])\d[\d,]*(?:\.\d+)?")
_FORBIDDEN_IN_REMINDER = re.compile(r"\b(risk|no[- ]?show|probability|predict|model|missed)\b", re.IGNORECASE)
SMS_MAX_CHARS = 320
# Rankings ignore departments with fewer attended/missed outcomes than this (a 1/1 = 100% rate is noise).
MIN_RANKING_SAMPLE = 10


# ---------------------------------------------------------------------------- helpers
def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _collect_allowed_numbers(obj: Any, allowed: set[float]) -> None:
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        v = float(obj)
        allowed.update({v, round(v), round(v, 1), round(v, 2)})
        if 0 <= v <= 1:
            allowed.update({round(v * 100), round(v * 100, 1), round(v * 100, 2)})
        return
    if isinstance(obj, str):
        for token in _NUMBER.findall(obj):
            allowed.add(float(token.replace(",", "")))
        return
    if isinstance(obj, dict):
        for key, value in obj.items():
            _collect_allowed_numbers(key, allowed)
            _collect_allowed_numbers(value, allowed)
        return
    if isinstance(obj, (list, tuple)):
        for item in obj:
            _collect_allowed_numbers(item, allowed)


def find_ungrounded_numbers(text: str, facts: dict[str, Any]) -> list[str]:
    """Numbers in ``text`` that cannot be traced back to ``facts`` (small counting words 0-10 allowed)."""
    allowed: set[float] = set(float(i) for i in range(11))
    _collect_allowed_numbers(facts, allowed)
    ungrounded = []
    for token in _NUMBER.findall(text):
        value = float(token.replace(",", "").rstrip("."))
        if not any(abs(value - a) <= 0.051 for a in allowed):
            ungrounded.append(token)
    return ungrounded


def _overview_facts(o: Overview, label: str) -> dict[str, Any]:
    return {
        "period": label,
        "total_appointments": o.total_appointments,
        "completed": o.completed,
        "no_shows": o.no_shows,
        "cancelled": o.cancelled,
        "scheduled": o.status_counts.scheduled,
        "confirmed": o.status_counts.confirmed,
        "no_show_rate": o.no_show_rate,
        "no_show_rate_percent": pct(o.no_show_rate),
        "cancellation_rate": o.cancellation_rate,
        "upcoming_appointments": o.upcoming,
        "high_risk_upcoming": o.high_risk_upcoming,
    }


def _format_time(t: time) -> str:
    return t.strftime("%I:%M %p").lstrip("0")


def _relative_day(day: date, today: date) -> str:
    delta = (day - today).days
    if delta == 0:
        return "today"
    if delta == 1:
        return "tomorrow"
    if delta > 1:
        return f"in {delta} days"
    return f"{-delta} days ago"


GROUNDING_RULES = """Rules you must follow:
- Use ONLY the facts in the JSON provided. Never invent, estimate, extrapolate or round numbers differently.
- If the facts do not answer the question, say so plainly instead of guessing.
- Rates in the JSON are fractions (0.237 means 23.7%). Prefer the *_percent fields when present.
- The no-show rate is defined as: {definition}.
- Model outputs are statistical risk estimates. Never claim to know why a specific patient will miss an appointment.
- Do not mention patient names or contact details.
- Write plain text (no markdown headings or tables), concise and professional."""


class AIService:
    def __init__(self, db: Session, llm: LLMClient | None = None, use_default_llm: bool = True) -> None:
        self.db = db
        self.settings = get_settings()
        self.llm = llm if llm is not None else (get_llm_client() if use_default_llm else None)
        self.analytics = AnalyticsService(db)
        self.appointments = AppointmentRepository(db)
        self.departments = DepartmentRepository(db)

    # ------------------------------------------------------------------ core narration
    def _system(self, task: str) -> str:
        rules = GROUNDING_RULES.format(definition=NO_SHOW_RATE_DEFINITION)
        return f"You are an assistant for administrators at {self.settings.HOSPITAL_NAME}. {task}\n\n{rules}"

    def _meta(self, llm_used: bool, grounding: str) -> AIMeta:
        return AIMeta(
            llm_used=llm_used,
            provider=self.llm.provider if (self.llm and llm_used) else "template",
            model=self.llm.model if (self.llm and llm_used) else None,
            grounding_check=grounding,
        )

    def _narrate(self, task: str, request: str, facts: dict[str, Any], fallback: str) -> tuple[str, AIMeta]:
        if self.llm is None:
            return fallback, self._meta(False, "not_applicable")
        prompt = f"{request}\n\nFACTS (JSON):\n{json.dumps(facts, indent=2, default=str)}"
        try:
            text = self.llm.generate(self._system(task), prompt)
        except LLMError as exc:
            logger.warning("LLM call failed (%s); using template fallback", exc)
            return fallback, self._meta(False, "fallback_used")
        ungrounded = find_ungrounded_numbers(text, facts)
        if ungrounded:
            logger.warning("LLM answer contained ungrounded numbers %s; using template fallback", ungrounded)
            return fallback, self._meta(False, "fallback_used")
        return text, self._meta(True, "passed")

    # ------------------------------------------------------------------ 1. prediction explanation
    def explain_prediction(self, appointment_id: int, refresh: bool = False) -> ExplainPredictionResponse:
        appt = self.appointments.get_detailed(appointment_id)
        if appt is None:
            raise NotFoundError("Appointment", appointment_id)
        predictions = PredictionService(self.db)
        prediction = predictions.predict(appointment_id) if refresh else predictions.get_or_predict(appointment_id)

        increasing = [f for f in prediction.factors if f.direction == "increases_risk"]
        decreasing = [f for f in prediction.factors if f.direction == "decreases_risk"]
        facts = {
            "appointment": {
                "department": appt.department.name,
                "date": appt.appointment_date.isoformat(),
                "time": appt.appointment_time.strftime("%H:%M"),
                "status": appt.status,
            },
            "prediction": {
                "no_show_probability": prediction.no_show_probability,
                "no_show_probability_percent": pct(prediction.no_show_probability),
                "risk_level": prediction.risk_level,
                "risk_bands": {
                    "LOW": f"below {pct(self.settings.RISK_LOW_MAX)}",
                    "MEDIUM": f"{pct(self.settings.RISK_LOW_MAX)} to {pct(self.settings.RISK_MEDIUM_MAX)}",
                    "HIGH": f"{pct(self.settings.RISK_MEDIUM_MAX)} and above",
                },
                "model": prediction.model_name,
            },
            "model_factors_increasing_risk": [{"factor": f.label, "value": f.display_value} for f in increasing],
            "model_factors_decreasing_risk": [{"factor": f.label, "value": f.display_value} for f in decreasing],
        }

        def factor_text(items: list[Any]) -> str:
            return "; ".join(f"{f.label}: {f.display_value}" for f in items)

        fallback_parts = [
            f"The model estimates a {pct(prediction.no_show_probability)} no-show probability for this "
            f"{appt.department.name} appointment, which is {prediction.risk_level} risk."
        ]
        if increasing:
            lead = (
                "The model predicts a higher no-show risk based primarily on these historical and appointment-related factors"
                if prediction.risk_level != "LOW"
                else "Factors the model associated with somewhat higher risk"
            )
            fallback_parts.append(f"{lead}: {factor_text(increasing)}.")
        if decreasing:
            fallback_parts.append(f"Factors pulling the estimate down: {factor_text(decreasing)}.")
        fallback_parts.append("These are model factors, not the actual reason a patient may miss an appointment.")
        if prediction.risk_level != "LOW":
            fallback_parts.append("Consider sending a reminder and asking the patient to confirm or reschedule.")
        fallback = " ".join(fallback_parts)

        explanation, meta = self._narrate(
            "Explain a no-show risk prediction to a hospital administrator.",
            "Explain why the model scored this appointment the way it did, in under 130 words. Use only the listed "
            "model factors (do not add any other factor), and describe them as the signals the model relied on - "
            'e.g. "The model predicts a higher no-show risk based primarily on these historical and '
            'appointment-related factors". State clearly that these are not the actual reasons the patient may '
            "miss the appointment. End with one or two practical follow-up actions (such as a reminder or a "
            "confirmation call) if the risk is MEDIUM or HIGH.",
            facts,
            fallback,
        )
        return ExplainPredictionResponse(
            appointment_id=appointment_id,
            explanation=explanation,
            prediction=prediction,
            disclaimer=NoShowPredictor.disclaimer(),
            meta=meta,
        )

    # ------------------------------------------------------------------ 2. reminders
    def generate_reminder(
        self, appointment_id: int, channel: ReminderChannel, tone: ReminderTone, request_confirmation: bool
    ) -> ReminderResponse:
        appt = self.appointments.get_detailed(appointment_id)
        if appt is None:
            raise NotFoundError("Appointment", appointment_id)
        today = date.today()
        first_name = appt.patient.name.split()[0]
        date_text = f"{appt.appointment_date:%A}, {appt.appointment_date.day} {appt.appointment_date:%B %Y}"
        time_text = _format_time(appt.appointment_time)
        relative = _relative_day(appt.appointment_date, today)
        hospital, phone = self.settings.HOSPITAL_NAME, self.settings.HOSPITAL_PHONE
        facts = {
            "patient_first_name": first_name,
            "department": appt.department.name,
            "doctor": appt.doctor.name,
            "date": date_text,
            "time": time_text,
            "when": relative,
            "hospital_name": hospital,
            "hospital_phone": phone,
            "channel": channel.value,
            "tone": tone.value,
            "ask_patient_to_confirm": request_confirmation,
        }
        subject, fallback = self._reminder_template(facts, channel, tone, request_confirmation)
        limits = {
            ReminderChannel.SMS: f"a single SMS of at most {SMS_MAX_CHARS - 20} characters",
            ReminderChannel.WHATSAPP: "a short WhatsApp message (2-4 short lines; at most one emoji if the tone is friendly)",
            ReminderChannel.EMAIL: 'an email: first line "Subject: <subject>", then a blank line, then a short body with a sign-off from the hospital',
        }

        message, meta = fallback, self._meta(False, "not_applicable")
        if self.llm is not None:
            system = (
                f"You write patient appointment reminders for {hospital}. Use only the details provided. "
                "Never mention risk, predictions, no-show history, diagnoses or any medical information. "
                "Do not invent phone numbers, addresses, links or instructions not in the details. Output only the message text."
            )
            prompt = (
                f"Write {limits[channel]} in a {tone.value} tone reminding the patient of this appointment. "
                + ("Ask them to confirm, or to call to reschedule if needed. " if request_confirmation else "")
                + f"\n\nDETAILS (JSON):\n{json.dumps(facts, indent=2)}"
            )
            try:
                candidate = self.llm.generate(system, prompt)
                ok, reason = self._validate_reminder(candidate, facts, channel)
                if ok:
                    message, meta = candidate, self._meta(True, "passed")
                else:
                    logger.warning("LLM reminder rejected (%s); using template", reason)
                    meta = self._meta(False, "fallback_used")
            except LLMError as exc:
                logger.warning("LLM call failed (%s); using template reminder", exc)
                meta = self._meta(False, "fallback_used")

        if channel == ReminderChannel.EMAIL and message.lower().startswith("subject:"):
            first, _, rest = message.partition("\n")
            subject, message = first.split(":", 1)[1].strip(), rest.strip()
        return ReminderResponse(
            appointment_id=appointment_id,
            channel=channel,
            tone=tone,
            subject=subject if channel == ReminderChannel.EMAIL else None,
            message=message,
            character_count=len(message),
            meta=meta,
        )

    @staticmethod
    def _validate_reminder(text: str, facts: dict[str, Any], channel: ReminderChannel) -> tuple[bool, str]:
        if facts["time"].lower() not in text.lower().replace(" ", " "):
            return False, "missing appointment time"
        if facts["department"].lower() not in text.lower() and facts["doctor"].lower() not in text.lower():
            return False, "missing department/doctor"
        if _FORBIDDEN_IN_REMINDER.search(text):
            return False, "mentions risk/prediction"
        if channel == ReminderChannel.SMS and len(text) > SMS_MAX_CHARS:
            return False, "SMS too long"
        if find_ungrounded_numbers(text, facts):
            return False, "contains numbers not in the appointment details"
        return True, "ok"

    @staticmethod
    def _reminder_template(
        f: dict[str, Any], channel: ReminderChannel, tone: ReminderTone, confirm: bool
    ) -> tuple[str | None, str]:
        when = f["when"] if f["when"] in ("today", "tomorrow") else f"on {f['date']}"
        confirm_line = (
            f"Please confirm your attendance, or call {f['hospital_phone']} if you need to reschedule."
            if confirm
            else f"If you need to reschedule, please call {f['hospital_phone']}."
        )
        subject = f"Appointment reminder: {f['department']} {when} at {f['time']}"
        if tone == ReminderTone.FRIENDLY:
            greeting = f"Hi {f['patient_first_name']}!"
            core = (
                f"Just a friendly reminder that you have an appointment with {f['doctor']} in {f['department']} "
                f"{when} at {f['time']}" + (f" ({f['date']})" if f["when"] in ("today", "tomorrow") else "") + "."
            )
            closing = f"See you soon, {f['hospital_name']}"
        else:
            greeting = f"Hello {f['patient_first_name']},"
            core = (
                f"This is a reminder from {f['hospital_name']} that you have an appointment with the {f['department']} "
                f"department ({f['doctor']}) {when} at {f['time']}"
                + (f", {f['date']}" if f["when"] in ("today", "tomorrow") else "")
                + "."
            )
            closing = f"Kind regards,\n{f['hospital_name']}"

        if channel == ReminderChannel.SMS:
            return None, f"{greeting} {core} {confirm_line}"
        if channel == ReminderChannel.WHATSAPP:
            return None, f"{greeting}\n{core}\n{confirm_line}"
        return subject, f"{greeting}\n\n{core}\n\n{confirm_line}\n\n{closing}"

    # ------------------------------------------------------------------ 3. department summary
    def department_summary(self, req: DepartmentSummaryRequest) -> DepartmentSummaryResponse:
        if req.period == PeriodName.CUSTOM:
            period = Period(PeriodName.CUSTOM, req.date_from, req.date_to, f"{req.date_from:%d %b %Y} - {req.date_to:%d %b %Y}")
        else:
            period = resolve_period(req.period)
        dept_name = None
        if req.department_id:
            dept = self.departments.get(req.department_id)
            if dept is None:
                raise NotFoundError("Department", req.department_id)
            dept_name = dept.name

        scope = self.analytics.overview(period.date_from, period.date_to, req.department_id)
        facts: dict[str, Any] = {"scope": dept_name or "All departments", **_overview_facts(scope, period.label)}
        if req.department_id:
            hospital = self.analytics.overview(period.date_from, period.date_to, None)
            facts["hospital_wide_no_show_rate"] = hospital.no_show_rate
            facts["hospital_wide_no_show_rate_percent"] = pct(hospital.no_show_rate)
        else:
            facts["departments"] = self._department_table(period)

        fallback = self._summary_template(facts, dept_name)
        summary, meta = self._narrate(
            "Summarise appointment performance for a hospital administrator.",
            "Write a 3-5 sentence performance summary of these statistics: volume, completed, no-shows, "
            "cancellations, the no-show rate (compared with the hospital-wide rate or other departments where "
            "available) and upcoming high-risk appointments. Finish with one operational suggestion.",
            facts,
            fallback,
        )
        return DepartmentSummaryResponse(
            summary=summary,
            period_label=period.label,
            date_from=period.date_from,
            date_to=period.date_to,
            department_name=dept_name,
            statistics=facts,
            meta=meta,
        )

    def _department_table(self, period: Period) -> list[dict[str, Any]]:
        rows = self.analytics.departments_stats(period.date_from, period.date_to)
        return [
            {
                "department": d.department_name,
                "appointments": d.total_appointments,
                "no_shows": d.no_shows,
                "attended_or_missed": d.completed + d.no_shows,
                "cancelled": d.cancelled,
                "no_show_rate": d.no_show_rate,
                "no_show_rate_percent": pct(d.no_show_rate),
                "high_risk_upcoming": d.high_risk_upcoming,
            }
            for d in sorted(rows, key=lambda d: -(d.no_show_rate or -1))
        ]

    @staticmethod
    def _summary_template(facts: dict[str, Any], dept_name: str | None) -> str:
        scope = dept_name or "the hospital"
        if facts["total_appointments"] == 0:
            return f"There are no appointments recorded for {scope} in {facts['period']}."
        parts = [
            f"For {facts['period']}, {scope} had {facts['total_appointments']} appointments: "
            f"{facts['completed']} completed, {facts['no_shows']} no-shows and {facts['cancelled']} cancelled"
            + (f", with {facts['scheduled'] + facts['confirmed']} still scheduled or confirmed." if facts["scheduled"] + facts["confirmed"] else ".")
        ]
        if facts["no_show_rate"] is not None:
            line = f"The no-show rate was {facts['no_show_rate_percent']}"
            if "hospital_wide_no_show_rate_percent" in facts:
                line += f" versus {facts['hospital_wide_no_show_rate_percent']} hospital-wide"
            parts.append(line + ".")
        else:
            parts.append("No attended or missed outcomes have been recorded yet, so a no-show rate is not available.")
        depts = [
            d for d in facts.get("departments", [])
            if d["no_show_rate"] is not None and d["attended_or_missed"] >= MIN_RANKING_SAMPLE
        ]
        if len(depts) > 1:
            parts.append(
                f"{depts[0]['department']} had the highest no-show rate ({depts[0]['no_show_rate_percent']} of "
                f"{depts[0]['attended_or_missed']}) and {depts[-1]['department']} the lowest "
                f"({depts[-1]['no_show_rate_percent']} of {depts[-1]['attended_or_missed']})."
            )
        elif facts.get("departments"):
            parts.append("Department volumes are too small in this period for a meaningful ranking.")
        if facts["high_risk_upcoming"]:
            parts.append(
                f"{facts['high_risk_upcoming']} upcoming appointments are flagged HIGH risk; prioritise reminders "
                "and confirmation calls for them."
            )
        return " ".join(parts)

    # ------------------------------------------------------------------ 4. natural-language analytics
    def chat(self, question: str) -> ChatResponse:
        departments = {d.name: d.id for d in self.departments.list_all()}
        plan = plan_query(question, departments)
        facts, fallback = self._answer_facts(plan)
        facts = {"question_interpreted_as": plan.intent.value, "period": plan.period.label, **facts}
        answer, meta = self._narrate(
            "Answer an administrator's analytics question.",
            f"QUESTION: {question}\n\nAnswer the question directly in 1-4 sentences using the facts below.",
            facts,
            fallback,
        )
        return ChatResponse(
            question=question,
            answer=answer,
            intent=plan.intent.value,
            period_label=plan.period.label,
            department_name=plan.department_name,
            data=facts,
            meta=meta,
        )

    def _answer_facts(self, plan: QueryPlan) -> tuple[dict[str, Any], str]:
        p = plan.period
        label = p.label
        if plan.intent == Intent.DEPARTMENT_RANKING:
            table = [
                d for d in self._department_table(p)
                if d["no_show_rate"] is not None and d["attended_or_missed"] >= MIN_RANKING_SAMPLE
            ]
            if not table:
                return {"departments": [], "min_sample": MIN_RANKING_SAMPLE}, (
                    f"Not enough attended or missed appointments for {label} to rank departments "
                    f"(each needs at least {MIN_RANKING_SAMPLE})."
                )
            ordered = table if plan.ranking == "highest" else list(reversed(table))
            top = ordered[0]
            text = (
                f"For {label}, {top['department']} has the {plan.ranking} no-show rate at {top['no_show_rate_percent']} "
                f"({top['no_shows']} no-shows). "
                f"Next: " + ", ".join(f"{d['department']} ({d['no_show_rate_percent']})" for d in ordered[1:3]) + "."
            )
            return {"ranking": plan.ranking, "min_sample_per_department": MIN_RANKING_SAMPLE, "departments_sorted": ordered}, text

        if plan.intent == Intent.DEPARTMENT_RATE and plan.department_id:
            dept = self.analytics.overview(p.date_from, p.date_to, plan.department_id)
            hospital = self.analytics.overview(p.date_from, p.date_to, None)
            facts = {
                "department": plan.department_name,
                **_overview_facts(dept, label),
                "hospital_wide_no_show_rate": hospital.no_show_rate,
                "hospital_wide_no_show_rate_percent": pct(hospital.no_show_rate),
            }
            if dept.no_show_rate is None:
                return facts, f"{plan.department_name} has no attended or missed appointments recorded for {label}."
            text = (
                f"The no-show rate for {plan.department_name} for {label} is {pct(dept.no_show_rate)} "
                f"({dept.no_shows} no-shows out of {dept.completed + dept.no_shows} attended or missed appointments), "
                f"compared with {pct(hospital.no_show_rate)} hospital-wide."
            )
            return facts, text

        if plan.intent == Intent.DAY_OF_WEEK:
            days = [d for d in self.analytics.day_of_week(p.date_from, p.date_to, plan.department_id) if d.total]
            if not days:
                return {"days": []}, f"No attended or missed appointments were recorded for {label}."
            rows = [
                {"day": d.day, "no_shows": d.no_shows, "attended_or_missed": d.total, "no_show_rate": d.no_show_rate, "no_show_rate_percent": pct(d.no_show_rate)}
                for d in days
            ]
            by_count = max(rows, key=lambda r: r["no_shows"])
            by_rate = max(rows, key=lambda r: r["no_show_rate"] or 0)
            text = (
                f"For {label}, {by_count['day']} has the most no-shows ({by_count['no_shows']}). "
                f"By rate, {by_rate['day']} is highest at {by_rate['no_show_rate_percent']}."
            )
            if by_count["day"] != by_rate["day"]:
                text += f" {by_count['day']} also has the most appointments, which drives its higher count."
            return {"by_day": rows, "most_no_shows": by_count["day"], "highest_rate": by_rate["day"]}, text

        if plan.intent == Intent.TRENDS:
            span = (p.date_to - p.date_from).days if p.date_from and p.date_to else 9999
            granularity = "day" if span <= 7 else ("week" if span <= 62 else "month")
            trends = self.analytics.no_show_trends(granularity, p.date_from, p.date_to, plan.department_id)
            overview = self.analytics.overview(p.date_from, p.date_to, plan.department_id)
            points = [
                {"period_start": t.period.isoformat(), "appointments": t.total, "no_shows": t.no_shows, "cancelled": t.cancelled, "no_show_rate_percent": pct(t.no_show_rate)}
                for t in trends.points
            ]
            facts = {"scope": plan.department_name or "All departments", "granularity": granularity, **_overview_facts(overview, label), "series": points}
            rated = [t for t in trends.points if t.no_show_rate is not None]
            text = self._summary_template(_overview_facts(overview, label), plan.department_name)
            if len(rated) >= 2:
                hi = max(rated, key=lambda t: t.no_show_rate or 0)
                lo = min(rated, key=lambda t: t.no_show_rate or 0)
                text += (
                    f" By {granularity}, the no-show rate ranged from {pct(lo.no_show_rate)} ({lo.period:%d %b %Y}) "
                    f"to {pct(hi.no_show_rate)} ({hi.period:%d %b %Y})."
                )
            return facts, text

        if plan.intent == Intent.HIGH_RISK:
            items = self.analytics.high_risk_upcoming(days_ahead=14, department_id=plan.department_id, limit=10)
            rows = [
                {"appointment_id": i.appointment_id, "department": i.department_name, "date": i.appointment_date.isoformat(), "time": i.appointment_time.strftime("%H:%M"), "no_show_probability_percent": pct(i.no_show_probability), "top_model_factor": i.top_factor}
                for i in items
            ]
            if not rows:
                return {"high_risk_appointments": []}, "There are no HIGH-risk appointments in the next 14 days."
            text = f"There are {len(rows)} HIGH-risk appointments in the next 14 days" + (" (showing the top 10)" if len(rows) == 10 else "") + ". "
            text += "The highest is appointment #{appointment_id} in {department} on {date} at {time} ({no_show_probability_percent}).".format(**rows[0])
            return {"window_days": 14, "high_risk_appointments": rows}, text

        if plan.intent == Intent.CANCELLATIONS:
            overview = self.analytics.overview(p.date_from, p.date_to, plan.department_id)
            depts = self.analytics.departments_stats(p.date_from, p.date_to)
            by_dept = sorted(
                ({"department": d.department_name, "cancelled": d.cancelled, "cancellation_rate_percent": pct(d.cancellation_rate)} for d in depts),
                key=lambda d: -d["cancelled"],
            )
            text = (
                f"For {label}, {overview.cancelled} of {overview.total_appointments} appointments were cancelled "
                f"({pct(overview.cancellation_rate)})."
            )
            if not plan.department_id and by_dept and by_dept[0]["cancelled"]:
                text += f" {by_dept[0]['department']} had the most cancellations ({by_dept[0]['cancelled']})."
            return {**_overview_facts(overview, label), "cancellations_by_department": by_dept}, text

        if plan.intent == Intent.MODEL_PERFORMANCE:
            info = PredictionService(self.db).model_info()
            if not info.metrics:
                return {"model_loaded": info.loaded}, "No model evaluation metrics are available yet."
            selected = info.metrics["selected_model"]
            comparison = {
                name: {k: m["test"][k] for k in ("no_show_recall", "no_show_precision", "no_show_f1", "roc_auc", "accuracy")}
                for name, m in info.metrics["models"].items()
            }
            t = comparison[selected]
            text = (
                f"The active model is {selected} (version {info.model_version}). On the held-out test set it has "
                f"no-show recall {pct(t['no_show_recall'])}, precision {pct(t['no_show_precision'])}, "
                f"F1 {t['no_show_f1']:.3f} and ROC-AUC {t['roc_auc']:.3f}."
            )
            return {"selected_model": selected, "model_version": info.model_version, "test_metrics": comparison, "synthetic_training_data": info.metrics.get("synthetic_data")}, text

        # OVERVIEW / NO_SHOW_COUNT
        overview = self.analytics.overview(p.date_from, p.date_to, plan.department_id)
        facts = {"scope": plan.department_name or "All departments", **_overview_facts(overview, label)}
        scope = plan.department_name or "the hospital"
        if plan.intent == Intent.NO_SHOW_COUNT:
            text = f"{overview.no_shows} appointments were missed (no-shows) at {scope} for {label}"
            text += f", a no-show rate of {pct(overview.no_show_rate)}." if overview.no_show_rate is not None else "."
            if not plan.department_id:
                facts["no_shows_by_department"] = [
                    {"department": d["department"], "no_shows": d["no_shows"]} for d in self._department_table(p)
                ]
            return facts, text
        return facts, self._summary_template(facts, plan.department_name)

