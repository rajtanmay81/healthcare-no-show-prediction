"""Online inference: load the persisted model bundle and score feature rows."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from app.core.config import get_settings
from app.core.exceptions import ModelNotAvailableError
from app.ml.explain import MODEL_FACTORS_DISCLAIMER, FactorContribution, ShapExplainer
from app.ml.preprocessing import FEATURE_COLUMNS
from app.models.enums import RiskLevel

logger = logging.getLogger(__name__)


def classify_risk(probability: float, low_max: float | None = None, medium_max: float | None = None) -> RiskLevel:
    """Map a probability to LOW / MEDIUM / HIGH using configurable upper bounds."""
    settings = get_settings()
    low_max = settings.RISK_LOW_MAX if low_max is None else low_max
    medium_max = settings.RISK_MEDIUM_MAX if medium_max is None else medium_max
    if not 0.0 <= probability <= 1.0:
        raise ValueError(f"probability must be within [0, 1], got {probability}")
    if probability < low_max:
        return RiskLevel.LOW
    if probability < medium_max:
        return RiskLevel.MEDIUM
    return RiskLevel.HIGH


@dataclass(frozen=True)
class PredictionResult:
    no_show_probability: float
    risk_level: RiskLevel
    flagged_by_model: bool  # probability >= tuned decision threshold
    factors: list[FactorContribution]
    features: dict[str, Any]


class NoShowPredictor:
    """Thread-safe, lazily loaded wrapper around the persisted sklearn pipeline."""

    def __init__(self, model_path: Path) -> None:
        self.model_path = model_path
        self._lock = threading.Lock()
        self._bundle: dict[str, Any] | None = None
        self._explainer: ShapExplainer | None = None
        self._load_if_present()

    def _load_if_present(self) -> None:
        if not self.model_path.exists():
            return
        try:
            bundle = joblib.load(self.model_path)
            explainer = ShapExplainer(bundle["pipeline"], bundle.get("background"))
        except Exception:  # noqa: BLE001 - a corrupt artefact must not crash the API
            logger.exception("Failed to load model from %s", self.model_path)
            return
        with self._lock:
            self._bundle, self._explainer = bundle, explainer

    def reload(self) -> None:
        self._load_if_present()
        logger.info("Model reloaded: %s %s", self.model_name, self.model_version)

    @property
    def is_loaded(self) -> bool:
        return self._bundle is not None

    @property
    def model_name(self) -> str | None:
        return self._bundle["model_name"] if self._bundle else None

    @property
    def model_version(self) -> str | None:
        return self._bundle["model_version"] if self._bundle else None

    @property
    def decision_threshold(self) -> float | None:
        return self._bundle["decision_threshold"] if self._bundle else None

    def _require(self) -> tuple[dict[str, Any], ShapExplainer]:
        with self._lock:
            if self._bundle is None or self._explainer is None:
                raise ModelNotAvailableError("No trained model is available. Train one with `python -m app.ml.train`.")
            return self._bundle, self._explainer

    def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
        bundle, _ = self._require()
        return bundle["pipeline"].predict_proba(features[FEATURE_COLUMNS])[:, 1]

    def predict_one(self, features: pd.DataFrame, top_k: int = 5) -> PredictionResult:
        bundle, explainer = self._require()
        proba = float(self.predict_proba(features)[0])
        factors = explainer.explain_row(features, top_k=top_k)
        row = features[FEATURE_COLUMNS].iloc[0]
        return PredictionResult(
            no_show_probability=round(proba, 4),
            risk_level=classify_risk(proba),
            flagged_by_model=proba >= bundle["decision_threshold"],
            factors=factors,
            features={k: (None if pd.isna(v) else (v.item() if hasattr(v, "item") else v)) for k, v in row.items()},
        )

    @staticmethod
    def disclaimer() -> str:
        return MODEL_FACTORS_DISCLAIMER


_predictor: NoShowPredictor | None = None
_predictor_lock = threading.Lock()


def get_predictor() -> NoShowPredictor:
    global _predictor
    if _predictor is None:
        with _predictor_lock:
            if _predictor is None:
                _predictor = NoShowPredictor(get_settings().model_path)
    return _predictor
