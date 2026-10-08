"""Feature engineering shared by training and online inference.

Leakage rules
-------------
* A row's features only use information that exists *before* that appointment takes place:
  the appointment's own schedule (department, date, time, booking date), the patient's age,
  and outcomes of the patient's **strictly earlier** appointments.
* The row's own outcome (status) is never used as a feature.
* Upcoming (scheduled/confirmed) appointments never contribute to history counts because
  their outcome is not known yet.

The same ``engineer_features`` function is used offline (CSV / DB export) and online
(a patient's appointment history pulled from PostgreSQL), which guarantees train/serve parity.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

TARGET = "no_show"
RAW_COLUMNS = [
    "appointment_id",
    "patient_id",
    "date_of_birth",
    "department",
    "appointment_date",
    "appointment_time",
    "booking_date",
    "status",
]
OUTCOME_STATUSES = ("completed", "no_show")  # rows usable as labelled training examples
HISTORY_STATUSES = ("completed", "no_show", "cancelled")  # outcomes known after the fact

AGE_BINS = [-1, 17, 34, 49, 64, 200]
AGE_LABELS = ["0-17", "18-34", "35-49", "50-64", "65+"]
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAYS_SINCE_CAP = 730

NUMERIC_FEATURES = [
    "age",
    "appointment_hour",
    "booking_lead_days",
    "previous_appointments",
    "previous_no_shows",
    "previous_cancellations",
    "prior_no_show_rate",
    "prior_cancellation_rate",
    "previous_attendance_rate",
    "days_since_last_appointment",
    "is_first_appointment",
    "is_weekend",
    "is_morning",
    "appointment_month",
]
CATEGORICAL_FEATURES = ["department", "day_of_week", "age_group"]
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def normalize_raw(raw: pd.DataFrame) -> pd.DataFrame:
    """Validate required columns and coerce dtypes."""
    missing = set(RAW_COLUMNS) - set(raw.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    df = raw[RAW_COLUMNS].copy()
    df["date_of_birth"] = pd.to_datetime(df["date_of_birth"])
    df["appointment_date"] = pd.to_datetime(df["appointment_date"])
    df["booking_date"] = pd.to_datetime(df["booking_date"])
    df["appointment_time"] = df["appointment_time"].astype(str).str.slice(0, 5)
    df["status"] = df["status"].astype(str).str.lower()
    df["department"] = df["department"].astype(str)
    df["appointment_datetime"] = pd.to_datetime(
        df["appointment_date"].dt.strftime("%Y-%m-%d") + " " + df["appointment_time"], format="%Y-%m-%d %H:%M"
    )
    return df


def engineer_features(raw: pd.DataFrame) -> pd.DataFrame:
    """Return one row per appointment with model features plus id/status/datetime columns."""
    df = normalize_raw(raw).sort_values(["patient_id", "appointment_datetime", "appointment_id"]).reset_index(drop=True)
    # --- appointment-level (known at booking time) ---
    age_days = (df["appointment_date"] - df["date_of_birth"]).dt.days
    df["age"] = (age_days / 365.25).clip(lower=0).astype(int)
    df["age_group"] = pd.cut(df["age"], bins=AGE_BINS, labels=AGE_LABELS).astype(str)
    df["day_of_week"] = df["appointment_date"].dt.dayofweek.map(dict(enumerate(DAY_NAMES))).astype(str)
    df["appointment_hour"] = df["appointment_datetime"].dt.hour
    df["booking_lead_days"] = (df["appointment_date"] - df["booking_date"]).dt.days.clip(lower=0)
    df["is_weekend"] = (df["appointment_date"].dt.dayofweek >= 5).astype(int)
    df["is_morning"] = (df["appointment_hour"] < 12).astype(int)
    df["appointment_month"] = df["appointment_date"].dt.month

    # --- patient history (strictly earlier appointments with a known outcome) ---
    is_no_show = (df["status"] == "no_show").astype(int)
    is_cancel = (df["status"] == "cancelled").astype(int)
    is_done = (df["status"] == "completed").astype(int)

    def _prior_sum(flag: pd.Series) -> pd.Series:
        return flag.groupby(df["patient_id"], sort=False).cumsum() - flag

    df["previous_no_shows"] = _prior_sum(is_no_show)
    df["previous_cancellations"] = _prior_sum(is_cancel)
    prev_completed = _prior_sum(is_done)
    df["previous_appointments"] = df["previous_no_shows"] + df["previous_cancellations"] + prev_completed
    attended_or_missed = prev_completed + df["previous_no_shows"]

    has_history = df["previous_appointments"] > 0
    df["is_first_appointment"] = (~has_history).astype(int)
    # Undefined for first-time patients -> NaN; imputed inside the model pipeline.
    df["prior_no_show_rate"] = np.where(has_history, df["previous_no_shows"] / df["previous_appointments"].clip(lower=1), np.nan)
    df["prior_cancellation_rate"] = np.where(
        has_history, df["previous_cancellations"] / df["previous_appointments"].clip(lower=1), np.nan
    )
    df["previous_attendance_rate"] = np.where(
        attended_or_missed > 0, prev_completed / attended_or_missed.clip(lower=1), np.nan
    )

    known_dt = df["appointment_datetime"].where(df["status"].isin(HISTORY_STATUSES))
    last_known = known_dt.groupby(df["patient_id"], sort=False).transform(lambda s: s.shift(1).ffill())
    days_since = (df["appointment_datetime"] - last_known).dt.days
    df["days_since_last_appointment"] = days_since.clip(lower=0, upper=DAYS_SINCE_CAP)

    return df


def build_training_frame(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """Features/labels for appointments with a final attended/missed outcome.

    Cancelled and upcoming appointments are *not* training rows (their target is undefined),
    but cancellations still contribute to the history features of later rows.
    """
    feats = engineer_features(raw)
    labelled = feats[feats["status"].isin(OUTCOME_STATUSES)].sort_values("appointment_datetime").reset_index(drop=True)
    y = (labelled["status"] == "no_show").astype(int).rename(TARGET)
    meta = labelled[["appointment_id", "patient_id", "appointment_datetime", "status"]]
    return labelled[FEATURE_COLUMNS], y, meta


def build_preprocessor() -> ColumnTransformer:
    numeric = Pipeline(
        steps=[
            ("impute", SimpleImputer(strategy="median", add_indicator=False)),
            ("scale", StandardScaler()),
        ]
    )
    categorical = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    return ColumnTransformer(
        transformers=[("num", numeric, NUMERIC_FEATURES), ("cat", categorical, CATEGORICAL_FEATURES)],
        verbose_feature_names_out=True,
    )


def transformed_to_original(transformed_name: str) -> str:
    """Map a ColumnTransformer output name (e.g. ``cat__department_Cardiology``) to its source feature."""
    prefix, _, rest = transformed_name.partition("__")
    if prefix == "num":
        return rest
    for feature in CATEGORICAL_FEATURES:
        if rest.startswith(f"{feature}_"):
            return feature
    return rest
