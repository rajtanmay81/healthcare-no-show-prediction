import logging
from datetime import date, datetime, time

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError, PermissionDeniedError
from app.models import Appointment, AppointmentStatusHistory, User, VisitHistory
from app.models.enums import (
    ALLOWED_TRANSITIONS,
    UPCOMING_STATUSES,
    AppointmentStatus,
    UserRole,
    VisitStatus,
)
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.doctor_repository import DoctorRepository
from app.repositories.patient_repository import PatientRepository
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentDetail,
    AppointmentRead,
    AppointmentStatusUpdate,
    AppointmentUpdate,
    LatestPrediction,
    StatusHistoryRead,
)
from app.schemas.common import Page

logger = logging.getLogger(__name__)

OPENING_TIME = time(8, 0)
CLOSING_TIME = time(18, 0)


def to_appointment_read(appt: Appointment) -> AppointmentRead:
    latest = appt.predictions[0] if appt.predictions else None
    return AppointmentRead(
        id=appt.id,
        patient_id=appt.patient_id,
        patient_name=appt.patient.name if appt.patient else None,
        doctor_id=appt.doctor_id,
        doctor_name=appt.doctor.name if appt.doctor else None,
        department_id=appt.department_id,
        department_name=appt.department.name if appt.department else None,
        appointment_date=appt.appointment_date,
        appointment_time=appt.appointment_time,
        booking_date=appt.booking_date,
        status=appt.status,
        created_at=appt.created_at,
        updated_at=appt.updated_at,
        latest_prediction=(
            LatestPrediction(
                no_show_probability=latest.no_show_probability,
                risk_level=latest.risk_level,
                created_at=latest.created_at,
            )
            if latest
            else None
        ),
    )


class AppointmentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = AppointmentRepository(db)
        self.patients = PatientRepository(db)
        self.doctors = DoctorRepository(db)

    # ------------------------------------------------------------------ helpers
    def _get_or_404(self, appointment_id: int) -> Appointment:
        appt = self.repo.get_detailed(appointment_id)
        if appt is None:
            raise NotFoundError("Appointment", appointment_id)
        return appt

    @staticmethod
    def _validate_slot(day: date, slot: time) -> None:
        if not OPENING_TIME <= slot < CLOSING_TIME:
            raise BusinessRuleError(f"Appointments must be between {OPENING_TIME:%H:%M} and {CLOSING_TIME:%H:%M}")
        if slot.minute % 15 or slot.second:
            raise BusinessRuleError("Appointment time must be aligned to a 15-minute slot")
        if datetime.combine(day, slot) < datetime.now():
            raise BusinessRuleError("Appointments cannot be booked in the past")

    def _ensure_slot_free(self, doctor_id: int, day: date, slot: time, exclude_id: int | None = None) -> None:
        if self.repo.find_slot_conflict(doctor_id, day, slot, exclude_id):
            raise ConflictError(f"Doctor {doctor_id} already has an appointment on {day} at {slot:%H:%M}")

    @staticmethod
    def _check_doctor_scope(appt: Appointment, user: User) -> None:
        if user.role == UserRole.DOCTOR and user.doctor_id and appt.doctor_id != user.doctor_id:
            raise PermissionDeniedError("Doctors can only access their own appointments")

    def _record_status(self, appt: Appointment, old: str | None, new: str, user: User) -> None:
        self.repo.add_status_history(
            AppointmentStatusHistory(appointment_id=appt.id, old_status=old, new_status=new, changed_by=user.email)
        )

    def _try_predict(self, appointment_id: int) -> None:
        """Score a new/rescheduled appointment. Booking must never fail because the model is unavailable."""
        if not get_settings().AUTO_PREDICT_ON_BOOKING:
            return
        try:
            from app.services.prediction_service import PredictionService

            PredictionService(self.db).predict(appointment_id)
        except Exception:  # noqa: BLE001 - prediction is best-effort here
            self.db.rollback()
            logger.warning("Automatic prediction failed for appointment %s", appointment_id, exc_info=True)

    # ------------------------------------------------------------------ commands
    def create(self, payload: AppointmentCreate, user: User) -> AppointmentDetail:
        if self.patients.get(payload.patient_id) is None:
            raise NotFoundError("Patient", payload.patient_id)
        doctor = self.doctors.get(payload.doctor_id)
        if doctor is None:
            raise NotFoundError("Doctor", payload.doctor_id)
        self._validate_slot(payload.appointment_date, payload.appointment_time)
        self._ensure_slot_free(doctor.id, payload.appointment_date, payload.appointment_time)

        appt = Appointment(
            patient_id=payload.patient_id,
            doctor_id=doctor.id,
            department_id=doctor.department_id,  # department is derived from the doctor
            appointment_date=payload.appointment_date,
            appointment_time=payload.appointment_time,
            booking_date=payload.booking_date or date.today(),
            status=AppointmentStatus.SCHEDULED,
        )
        try:
            self.repo.add(appt)
            self._record_status(appt, None, AppointmentStatus.SCHEDULED, user)
            self.db.commit()
        except IntegrityError as exc:  # race on the unique slot index
            self.db.rollback()
            raise ConflictError("That slot was just booked by someone else") from exc
        logger.info("Booked appointment id=%s patient=%s doctor=%s", appt.id, appt.patient_id, appt.doctor_id)

        self._try_predict(appt.id)
        return self.get(appt.id, user)

    def update(self, appointment_id: int, payload: AppointmentUpdate, user: User) -> AppointmentDetail:
        appt = self._get_or_404(appointment_id)
        if appt.status not in UPCOMING_STATUSES:
            raise BusinessRuleError(f"Only upcoming appointments can be rescheduled (current status: {appt.status})")
        values = payload.model_dump(exclude_unset=True, exclude_none=True)
        if not values:
            raise BusinessRuleError("No changes supplied")

        doctor_id = values.get("doctor_id", appt.doctor_id)
        day = values.get("appointment_date", appt.appointment_date)
        slot = values.get("appointment_time", appt.appointment_time)
        doctor = self.doctors.get(doctor_id)
        if doctor is None:
            raise NotFoundError("Doctor", doctor_id)
        if day < appt.booking_date:
            raise BusinessRuleError("appointment_date cannot be before booking_date")
        self._validate_slot(day, slot)
        self._ensure_slot_free(doctor_id, day, slot, exclude_id=appt.id)

        self.repo.update(
            appt,
            {"doctor_id": doctor_id, "department_id": doctor.department_id, "appointment_date": day, "appointment_time": slot},
        )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("That slot was just booked by someone else") from exc
        logger.info("Rescheduled appointment id=%s by %s", appointment_id, user.email)
        self._try_predict(appointment_id)  # lead time / department may have changed
        return self.get(appointment_id, user)

    def change_status(self, appointment_id: int, payload: AppointmentStatusUpdate, user: User) -> AppointmentDetail:
        appt = self._get_or_404(appointment_id)
        self._check_doctor_scope(appt, user)
        current = AppointmentStatus(appt.status)
        new = payload.status
        if new == current:
            raise BusinessRuleError(f"Appointment is already {current.value}")
        if new not in ALLOWED_TRANSITIONS[current]:
            raise BusinessRuleError(f"Invalid status transition: {current.value} -> {new.value}")
        if new in (AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW) and appt.appointment_date > date.today():
            raise BusinessRuleError("An appointment can only be marked completed/no-show on or after its date")
        if user.role == UserRole.DOCTOR and new not in (AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW):
            raise PermissionDeniedError("Doctors can only record attendance (completed / no_show)")

        appt.status = new
        self._record_status(appt, current, new, user)
        if new in (AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW):
            # Closed outcomes become visit history -> future training data and history features.
            self.repo.add_visit(
                VisitHistory(
                    patient_id=appt.patient_id,
                    appointment_id=appt.id,
                    visit_date=appt.appointment_date,
                    visit_status=VisitStatus.ATTENDED if new == AppointmentStatus.COMPLETED else VisitStatus.MISSED,
                    notes=payload.notes,
                )
            )
        self.db.commit()
        logger.info("Appointment id=%s status %s -> %s by %s", appt.id, current, new, user.email)
        return self.get(appointment_id, user)

    # ------------------------------------------------------------------ queries
    def get(self, appointment_id: int, user: User) -> AppointmentDetail:
        self.db.expire_all()
        appt = self._get_or_404(appointment_id)
        self._check_doctor_scope(appt, user)
        base = to_appointment_read(appt)
        return AppointmentDetail(
            **base.model_dump(),
            status_history=[StatusHistoryRead.model_validate(h) for h in appt.status_history],
        )

    def list(
        self,
        user: User,
        *,
        status: AppointmentStatus | None = None,
        department_id: int | None = None,
        doctor_id: int | None = None,
        patient_id: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
        newest_first: bool = True,
    ) -> Page[AppointmentRead]:
        if user.role == UserRole.DOCTOR and user.doctor_id:
            doctor_id = user.doctor_id
        rows, total = self.repo.list(
            status=status,
            department_id=department_id,
            doctor_id=doctor_id,
            patient_id=patient_id,
            date_from=date_from,
            date_to=date_to,
            search=search,
            limit=limit,
            offset=offset,
            newest_first=newest_first,
        )
        return Page(items=[to_appointment_read(a) for a in rows], total=total, limit=limit, offset=offset)
