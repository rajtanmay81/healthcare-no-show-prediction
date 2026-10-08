import logging

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models import Patient, User
from app.models.enums import UserRole
from app.repositories.patient_repository import PatientRepository
from app.schemas.common import Page
from app.schemas.patient import PatientCreate, PatientDetail, PatientRead, PatientStats, PatientUpdate

logger = logging.getLogger(__name__)


def mask_contact(patient: PatientRead, viewer: User) -> PatientRead:
    """Doctors do not need patient contact details for clinical scheduling; mask them."""
    if viewer.role != UserRole.DOCTOR:
        return patient
    phone = f"***{patient.phone[-3:]}" if patient.phone else None
    email = f"{patient.email[0]}***@{patient.email.split('@')[-1]}" if patient.email else None
    return patient.model_copy(update={"phone": phone, "email": email})


class PatientService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = PatientRepository(db)

    def _get_or_404(self, patient_id: int) -> Patient:
        patient = self.repo.get(patient_id)
        if patient is None:
            raise NotFoundError("Patient", patient_id)
        return patient

    def create(self, payload: PatientCreate) -> PatientRead:
        if payload.email and self.repo.get_by_email(payload.email):
            raise ConflictError("A patient with this email already exists")
        patient = self.repo.add(Patient(**payload.model_dump()))
        self.db.commit()
        logger.info("Created patient id=%s", patient.id)
        return PatientRead.model_validate(patient)

    def list(self, search: str | None, limit: int, offset: int, viewer: User) -> Page[PatientRead]:
        rows, total = self.repo.list(search, limit, offset)
        items = [mask_contact(PatientRead.model_validate(p), viewer) for p in rows]
        return Page(items=items, total=total, limit=limit, offset=offset)

    def get(self, patient_id: int, viewer: User) -> PatientDetail:
        patient = self._get_or_404(patient_id)
        base = mask_contact(PatientRead.model_validate(patient), viewer)
        return PatientDetail(**base.model_dump(), stats=PatientStats(**self.repo.appointment_stats(patient_id)))

    def update(self, patient_id: int, payload: PatientUpdate) -> PatientRead:
        patient = self._get_or_404(patient_id)
        values = payload.model_dump(exclude_unset=True)
        if values.get("email") and values["email"] != patient.email:
            existing = self.repo.get_by_email(values["email"])
            if existing and existing.id != patient_id:
                raise ConflictError("A patient with this email already exists")
        self.repo.update(patient, values)
        self.db.commit()
        self.db.refresh(patient)
        logger.info("Updated patient id=%s fields=%s", patient_id, sorted(values))
        return PatientRead.model_validate(patient)

    def delete(self, patient_id: int) -> None:
        patient = self._get_or_404(patient_id)
        if self.repo.has_appointments(patient_id):
            raise ConflictError(
                "Patient has appointment history and cannot be deleted; historical records are kept for auditing"
            )
        self.repo.delete(patient)
        self.db.commit()
        logger.info("Deleted patient id=%s", patient_id)
