"""Synthetic hospital appointment data generator.

!!! THIS DATA IS ENTIRELY SYNTHETIC !!!
No real patients, doctors or hospital records are used. Names, contacts and outcomes are
randomly generated. The generator plants realistic, *probabilistic* (never deterministic)
relationships so the ML pipeline has something meaningful - but noisy - to learn:

* each patient has a hidden "reliability" trait -> past no-shows predict future no-shows
* longer booking lead time -> slightly higher no-show probability
* prior cancellations -> slightly higher no-show probability
* department, age group, weekday, hour and month have small effects
* Gaussian noise is added to every appointment's log-odds

Outputs (in ``data/``): appointments.csv, patients.csv, doctors.csv, departments.csv

Usage:
    python -m app.ml.generate_data --appointments 15000 --patients 4600 --seed 42
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from datetime import date, time, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from app.core.config import get_settings
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)

DEPARTMENTS: dict[str, tuple[str, float, list[str]]] = {
    # name: (description, no-show log-odds offset, specializations)
    "General Medicine": ("Primary care, check-ups and internal medicine", 0.10, ["Internal Medicine", "Family Medicine"]),
    "Cardiology": ("Heart and cardiovascular care", -0.20, ["Interventional Cardiology", "Electrophysiology"]),
    "Dermatology": ("Skin, hair and nail conditions", 0.30, ["Clinical Dermatology", "Cosmetic Dermatology"]),
    "Orthopedics": ("Bones, joints and musculoskeletal care", 0.00, ["Sports Medicine", "Joint Replacement"]),
    "Neurology": ("Brain and nervous system disorders", -0.15, ["Epilepsy", "Movement Disorders"]),
    "Pediatrics": ("Care for infants, children and adolescents", 0.05, ["General Pediatrics", "Neonatology"]),
    "ENT": ("Ear, nose and throat", 0.15, ["Otology", "Rhinology"]),
    "Gynecology": ("Women's reproductive health", -0.05, ["Obstetrics", "Reproductive Endocrinology"]),
}
DOCTORS_PER_DEPARTMENT = 3
SLOT_TIMES = [time(h, m) for h in range(9, 17) for m in (0, 30)]

FIRST_NAMES = (
    "Aarav Aditi Alex Amelia Ananya Anika Arjun Ava Benjamin Chloe Daniel David Diya Elena Emily Emma Ethan Farah "
    "Gabriel Grace Hannah Harper Isaac Isabella Ishaan Jack James Kabir Kavya Leah Liam Lucas Maya Meera Mia Mohammed "
    "Nathan Nina Noah Olivia Omar Priya Rahul Riya Rohan Sara Sofia Tanvi Thomas Uma Vihaan Vikram William Zara Zoe"
).split()
LAST_NAMES = (
    "Agarwal Brown Chen Clark Das Davis Evans Fernandez Garcia Gupta Hall Harris Iyer Jackson Johnson Joshi Khan Kim "
    "Kumar Lee Lewis Lopez Martin Mehta Miller Moore Nair Nguyen Patel Perez Reddy Roberts Rodriguez Sharma Singh "
    "Smith Taylor Thomas Thompson Verma Walker White Williams Wilson Wright Young"
).split()


@dataclass(frozen=True)
class GeneratorConfig:
    n_appointments: int = 15_000
    n_patients: int = 4_600
    history_days: int = 730
    future_days: int = 21
    seed: int = 42


def _sigmoid(x: float) -> float:
    return float(1.0 / (1.0 + np.exp(-x)))


def _age_effect(age: int) -> float:
    if age < 18:
        return 0.05
    if age < 31:
        return 0.35
    if age < 46:
        return 0.10
    if age < 65:
        return -0.10
    if age < 80:
        return -0.20
    return 0.10


_DOW_EFFECT = {0: 0.15, 1: 0.0, 2: -0.05, 3: 0.0, 4: 0.20, 5: 0.25, 6: 0.25}
_MONTH_EFFECT = {12: 0.20, 1: 0.10, 7: 0.10, 8: 0.10}


def _hour_effect(slot: time) -> float:
    if slot.hour < 10:
        return 0.10
    if slot.hour >= 15:
        return 0.15
    return 0.0


class SyntheticDataGenerator:
    def __init__(self, config: GeneratorConfig) -> None:
        self.cfg = config
        self.rng = np.random.default_rng(config.seed)
        self.today = date.today()

    # ------------------------------------------------------------------ reference data
    def _departments(self) -> pd.DataFrame:
        return pd.DataFrame(
            [{"department": name, "description": desc} for name, (desc, _, _) in DEPARTMENTS.items()]
        )

    def _doctors(self) -> pd.DataFrame:
        rows, doctor_id, used = [], 1, set()
        for dept, (_, _, specs) in DEPARTMENTS.items():
            for i in range(DOCTORS_PER_DEPARTMENT):
                while True:
                    first, last = self.rng.choice(FIRST_NAMES), self.rng.choice(LAST_NAMES)
                    if (first, last) not in used:
                        used.add((first, last))
                        break
                rows.append(
                    {
                        "doctor_id": doctor_id,
                        "doctor_name": f"Dr. {first} {last}",
                        "department": dept,
                        "specialization": specs[i % len(specs)],
                        "email": f"{first.lower()}.{last.lower()}.{doctor_id}@citygeneral.org",
                        "phone": f"+1-555-{2000 + doctor_id:04d}",
                    }
                )
                doctor_id += 1
        return pd.DataFrame(rows)

    def _patients(self) -> pd.DataFrame:
        n = self.cfg.n_patients
        # Age mixture: children, working-age adults and seniors.
        group = self.rng.choice(3, size=n, p=[0.17, 0.58, 0.25])
        ages = np.where(
            group == 0,
            self.rng.integers(0, 18, n),
            np.where(group == 1, self.rng.integers(18, 65, n), self.rng.integers(65, 95, n)),
        )
        genders = self.rng.choice(["female", "male", "other", "undisclosed"], size=n, p=[0.51, 0.46, 0.01, 0.02])
        rows = []
        for pid in range(1, n + 1):
            first, last = self.rng.choice(FIRST_NAMES), self.rng.choice(LAST_NAMES)
            dob = self.today - timedelta(days=int(ages[pid - 1] * 365.25 + self.rng.integers(0, 365)))
            rows.append(
                {
                    "patient_id": pid,
                    "name": f"{first} {last}",
                    "date_of_birth": dob,
                    "gender": genders[pid - 1],
                    "phone": f"+1-555-{self.rng.integers(100, 999)}-{self.rng.integers(1000, 9999)}",
                    "email": f"{first.lower()}.{last.lower()}{pid}@example.org",
                    # Hidden trait - NOT exported. Drives behaviour consistently across a patient's visits.
                    "hidden_reliability": self.rng.normal(0.0, 0.9),
                    "hidden_age": int(ages[pid - 1]),
                }
            )
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------ appointments
    def _appointment_counts(self) -> np.ndarray:
        n, target = self.cfg.n_patients, self.cfg.n_appointments
        # Over-dispersed visit counts: a few frequent visitors, many occasional ones.
        lam = self.rng.gamma(shape=1.3, scale=(target / n - 1) / 1.3, size=n)
        counts = 1 + self.rng.poisson(lam)
        # Nudge totals to hit the target exactly.
        while counts.sum() != target:
            idx = self.rng.integers(0, n)
            if counts.sum() > target and counts[idx] > 1:
                counts[idx] -= 1
            elif counts.sum() < target:
                counts[idx] += 1
        return counts

    def _primary_department(self, age: int, gender: str) -> str:
        if age < 16:
            return "Pediatrics"
        names = list(DEPARTMENTS)
        weights = np.array([0.24, 0.13, 0.12, 0.13, 0.09, 0.02, 0.12, 0.15 if gender == "female" else 0.0])
        return str(self.rng.choice(names, p=weights / weights.sum()))

    def _lead_days(self) -> int:
        bucket = self.rng.choice(3, p=[0.30, 0.50, 0.20])
        if bucket == 0:
            return int(self.rng.integers(0, 3))
        if bucket == 1:
            return int(self.rng.integers(3, 22))
        return int(self.rng.integers(22, 61))

    def _random_date(self) -> date:
        offset = int(self.rng.integers(-self.cfg.history_days, self.cfg.future_days + 1))
        day = self.today + timedelta(days=offset)
        if day.weekday() == 6:  # closed on Sundays
            day += timedelta(days=1)
        return day

    def generate(self) -> dict[str, pd.DataFrame]:
        departments = self._departments()
        doctors = self._doctors()
        patients = self._patients()
        doctors_by_dept = doctors.groupby("department")["doctor_id"].apply(list).to_dict()
        counts = self._appointment_counts()
        booked: set[tuple[int, date, time]] = set()
        rows: list[dict[str, object]] = []

        for p, n_appts in zip(patients.itertuples(index=False), counts, strict=True):
            primary = self._primary_department(p.hidden_age, p.gender)
            dates = sorted(self._random_date() for _ in range(n_appts))
            prev_ns = prev_cx = prev_done = 0
            for appt_date in dates:
                dept = primary if (primary == "Pediatrics" or self.rng.random() < 0.7) else str(
                    self.rng.choice([d for d in DEPARTMENTS if d != "Pediatrics"])
                )
                doctor_id, slot = self._book_slot(doctors_by_dept[dept], appt_date, booked)
                lead = self._lead_days()
                booking_date = appt_date - timedelta(days=lead)
                age = p.hidden_age - max(0, (self.today - appt_date).days) // 365

                if appt_date > self.today or (appt_date == self.today and self.rng.random() < 0.6):
                    status = "confirmed" if self.rng.random() < 0.35 else "scheduled"
                else:
                    status = self._simulate_outcome(p.hidden_reliability, dept, age, appt_date, slot, lead, prev_ns, prev_cx, prev_done)
                    prev_ns += status == "no_show"
                    prev_cx += status == "cancelled"
                    prev_done += status == "completed"

                rows.append(
                    {
                        "patient_id": p.patient_id,
                        "date_of_birth": p.date_of_birth,
                        "gender": p.gender,
                        "department": dept,
                        "doctor_id": doctor_id,
                        "appointment_date": appt_date,
                        "appointment_time": slot.strftime("%H:%M"),
                        "booking_date": booking_date,
                        "status": status,
                    }
                )

        appointments = pd.DataFrame(rows).sort_values(["appointment_date", "appointment_time", "doctor_id"])
        appointments.insert(0, "appointment_id", range(1, len(appointments) + 1))
        public_patients = patients.drop(columns=["hidden_reliability", "hidden_age"])
        return {
            "appointments": appointments.reset_index(drop=True),
            "patients": public_patients,
            "doctors": doctors,
            "departments": departments,
        }

    def _book_slot(self, doctor_ids: list[int], day: date, booked: set[tuple[int, date, time]]) -> tuple[int, time]:
        for _ in range(200):
            doctor_id = int(self.rng.choice(doctor_ids))
            slot = SLOT_TIMES[int(self.rng.integers(0, len(SLOT_TIMES)))]
            if (doctor_id, day, slot) not in booked:
                booked.add((doctor_id, day, slot))
                return doctor_id, slot
        raise RuntimeError(f"No free slot on {day}; reduce appointment volume")

    def _simulate_outcome(
        self,
        reliability: float,
        dept: str,
        age: int,
        day: date,
        slot: time,
        lead: int,
        prev_ns: int,
        prev_cx: int,
        prev_done: int,
    ) -> str:
        # Cancellation first: impatient / unreliable patients and long waits cancel more.
        p_cancel = _sigmoid(-2.7 + 0.30 * reliability + 0.015 * lead + self.rng.normal(0, 0.3))
        if self.rng.random() < p_cancel:
            return "cancelled"
        logit = (
            -2.30
            + 0.85 * reliability
            + DEPARTMENTS[dept][1]
            + 0.25 * np.log1p(lead)
            + _age_effect(age)
            + _DOW_EFFECT[day.weekday()]
            + _hour_effect(slot)
            + _MONTH_EFFECT.get(day.month, 0.0)
            + 0.30 * min(prev_ns, 4)
            + 0.12 * min(prev_cx, 3)
            - 0.05 * min(prev_done, 6)
            + self.rng.normal(0, 0.45)
        )
        return "no_show" if self.rng.random() < _sigmoid(logit) else "completed"


def save(frames: dict[str, pd.DataFrame], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in frames.items():
        path = out_dir / f"{name}.csv"
        frame.to_csv(path, index=False)
        logger.info("Wrote %s (%d rows)", path, len(frame))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate SYNTHETIC hospital appointment data")
    parser.add_argument("--appointments", type=int, default=15_000)
    parser.add_argument("--patients", type=int, default=4_600)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=get_settings().DATA_DIR)
    args = parser.parse_args()

    configure_logging()
    frames = SyntheticDataGenerator(
        GeneratorConfig(n_appointments=args.appointments, n_patients=args.patients, seed=args.seed)
    ).generate()
    save(frames, args.out)
    status_mix = frames["appointments"]["status"].value_counts(normalize=True).round(3).to_dict()
    logger.info("Status mix: %s", status_mix)


if __name__ == "__main__":
    main()
