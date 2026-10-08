"""SHAP-based explanations for individual predictions.

Contributions are computed on the transformed (scaled / one-hot) feature space and then
aggregated back to the original, human-meaningful features. They describe *what the model
relied on*, not *why a patient will actually miss an appointment*.

* Logistic Regression -> ``shap.LinearExplainer`` (log-odds units)
* Random Forest       -> ``shap.TreeExplainer``   (probability units)
* XGBoost             -> XGBoost's native TreeSHAP (``pred_contribs=True``, log-odds units),
                         mathematically identical to ``shap.TreeExplainer`` and version-robust.
"""

from __future__ import annotations

import calendar
import logging
import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd
import shap
import xgboost as xgb
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from app.ml.preprocessing import FEATURE_COLUMNS, transformed_to_original

logger = logging.getLogger(__name__)

MODEL_FACTORS_DISCLAIMER = (
    "These are model factors: the historical and appointment-related signals the model relied on most "
    "for this score. They are statistical associations, not the actual reason a patient may miss an appointment."
)

FEATURE_LABELS: dict[str, str] = {
    "age": "Patient age",
    "age_group": "Age group",
    "department": "Department",
    "day_of_week": "Day of week",
    "appointment_hour": "Appointment hour",
    "booking_lead_days": "Booking lead time",
    "previous_appointments": "Previous appointments (any outcome)",
    "previous_no_shows": "Previous no-shows",
    "previous_cancellations": "Previous cancellations",
    "prior_no_show_rate": "Prior no-show rate",
    "prior_cancellation_rate": "Prior cancellation rate",
    "previous_attendance_rate": "Previous attendance rate",
    "days_since_last_appointment": "Days since last appointment",
    "is_first_appointment": "First appointment",
    "is_weekend": "Weekend appointment",
    "is_morning": "Morning appointment",
    "appointment_month": "Appointment month",
}


@dataclass(frozen=True)
class FactorContribution:
    feature: str
    label: str
    value: Any
    display_value: str
    contribution: float
    direction: str  # "increases_risk" | "decreases_risk"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def format_feature_value(feature: str, value: Any, row: pd.Series | None = None) -> str:
    """Human-readable value, e.g. ``25 days`` or ``20%``."""
    no_history = row is not None and int(row.get("previous_appointments", 0) or 0) == 0
    if feature in {"prior_no_show_rate", "prior_cancellation_rate", "previous_attendance_rate"}:
        return "no prior history" if _is_missing(value) or no_history else f"{float(value):.0%}"
    if _is_missing(value):
        return "first visit" if feature == "days_since_last_appointment" else "unknown"
    if feature in {"booking_lead_days", "days_since_last_appointment"}:
        return f"{int(value)} day{'s' if int(value) != 1 else ''}"
    if feature == "age":
        return f"{int(value)} years"
    if feature == "appointment_hour":
        return f"{int(value):02d}:00-{int(value):02d}:59"
    if feature == "appointment_month":
        return calendar.month_name[int(value)]
    if feature in {"is_first_appointment", "is_weekend", "is_morning"}:
        return "Yes" if int(value) else "No"
    if isinstance(value, (int, np.integer)) or (isinstance(value, float) and float(value).is_integer()):
        return str(int(value))
    return str(value)


def _to_python(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if _is_missing(value):
        return None
    return value


class ShapExplainer:
    def __init__(self, pipeline: Pipeline, background: np.ndarray | None = None) -> None:
        self.pipeline = pipeline
        self.preprocessor = pipeline.named_steps["preprocess"]
        self.model = pipeline.named_steps["model"]
        self.transformed_names = list(self.preprocessor.get_feature_names_out())
        self.original_of = [transformed_to_original(n) for n in self.transformed_names]
        self._explainer: Any = None
        if isinstance(self.model, LogisticRegression):
            if background is None:
                raise ValueError("LogisticRegression explanations require a background sample")
            masker = shap.maskers.Independent(background, max_samples=len(background))
            self._explainer = shap.LinearExplainer(self.model, masker)
        elif not isinstance(self.model, xgb.XGBClassifier):
            self._explainer = shap.TreeExplainer(self.model)

    def _transformed_contributions(self, x_transformed: np.ndarray) -> np.ndarray:
        if isinstance(self.model, xgb.XGBClassifier):
            contribs = self.model.get_booster().predict(xgb.DMatrix(x_transformed), pred_contribs=True)
            return np.asarray(contribs)[:, :-1]  # drop bias column
        values = self._explainer.shap_values(x_transformed)
        if isinstance(values, list):  # older SHAP: one array per class
            values = values[1]
        values = np.asarray(values)
        if values.ndim == 3:  # (n, features, classes)
            values = values[:, :, 1]
        return values

    def aggregated_contributions(self, features: pd.DataFrame) -> pd.DataFrame:
        """SHAP values per *original* feature (one-hot columns summed back together)."""
        x_t = self.preprocessor.transform(features[FEATURE_COLUMNS])
        contribs = self._transformed_contributions(np.asarray(x_t, dtype=float))
        frame = pd.DataFrame(contribs, columns=self.transformed_names)
        return frame.T.groupby(self.original_of).sum().T[FEATURE_COLUMNS]

    def explain_row(self, features: pd.DataFrame, top_k: int = 5) -> list[FactorContribution]:
        if len(features) != 1:
            raise ValueError("explain_row expects exactly one row")
        row = features.iloc[0]
        contribs = self.aggregated_contributions(features).iloc[0]
        ordered = contribs.reindex(contribs.abs().sort_values(ascending=False).index)
        factors = []
        for feature, value in ordered.head(top_k).items():
            if abs(value) < 1e-6:
                continue
            raw = row[feature]
            factors.append(
                FactorContribution(
                    feature=str(feature),
                    label=FEATURE_LABELS.get(str(feature), str(feature)),
                    value=_to_python(raw),
                    display_value=format_feature_value(str(feature), raw, row),
                    contribution=round(float(value), 4),
                    direction="increases_risk" if value > 0 else "decreases_risk",
                )
            )
        return factors

    def global_importance(self, features: pd.DataFrame) -> list[dict[str, float | str]]:
        mean_abs = self.aggregated_contributions(features).abs().mean().sort_values(ascending=False)
        return [
            {"feature": f, "label": FEATURE_LABELS.get(f, f), "mean_abs_shap": round(float(v), 4)}
            for f, v in mean_abs.items()
        ]
