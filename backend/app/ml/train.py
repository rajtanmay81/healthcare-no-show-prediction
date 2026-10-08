"""Train, compare and persist the no-show model.

Protocol
--------
1. Build leakage-free features (see ``preprocessing.py``).
2. **Temporal split** on appointment datetime: oldest 70% train, next 15% validation,
   most recent 15% test. This mimics deployment (train on the past, predict the future).
3. For each model family (Logistic Regression baseline, Random Forest, XGBoost) pick the best
   hyper-parameters by validation ROC-AUC, then tune the decision threshold that maximises
   **no-show F1** on validation.
4. Select the family with the best validation no-show F1 (ROC-AUC as tie-breaker) - never accuracy,
   because a model that predicts "everyone attends" is ~76% accurate and useless.
5. Refit every family on train+validation and report metrics on the untouched test set.
6. Persist the selected pipeline (preprocessing + model), threshold and metadata with joblib.

Usage:
    python -m app.ml.train                 # train from data/appointments.csv
    python -m app.ml.train --source db     # retrain from live PostgreSQL history
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
import xgboost as xgb
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.ml.dataset import load_csv, load_from_database
from app.ml.evaluate import best_f1_threshold, calibration_table, classification_metrics
from app.ml.explain import ShapExplainer
from app.ml.preprocessing import (
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    NUMERIC_FEATURES,
    build_preprocessor,
    build_training_frame,
)

logger = logging.getLogger(__name__)
RANDOM_STATE = 42
MIN_TRAINING_ROWS = 500


@dataclass
class Candidate:
    family: str
    display_name: str
    estimator: Any
    params: dict[str, Any]


def candidate_grid() -> list[Candidate]:
    grid: list[Candidate] = []
    for c in (0.1, 1.0):
        grid.append(
            Candidate("logistic_regression", "Logistic Regression", LogisticRegression(C=c, max_iter=2000), {"C": c})
        )
    for depth, leaf in ((6, 20), (8, 10), (14, 5)):
        grid.append(
            Candidate(
                "random_forest",
                "Random Forest",
                RandomForestClassifier(
                    n_estimators=300, max_depth=depth, min_samples_leaf=leaf, n_jobs=-1, random_state=RANDOM_STATE
                ),
                {"n_estimators": 300, "max_depth": depth, "min_samples_leaf": leaf},
            )
        )
    for depth, n_est, lr in ((2, 400, 0.03), (3, 400, 0.05), (5, 300, 0.05)):
        grid.append(
            Candidate(
                "xgboost",
                "XGBoost",
                xgb.XGBClassifier(
                    n_estimators=n_est,
                    max_depth=depth,
                    learning_rate=lr,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    min_child_weight=5,
                    reg_lambda=1.0,
                    eval_metric="logloss",
                    n_jobs=-1,
                    random_state=RANDOM_STATE,
                ),
                {"n_estimators": n_est, "max_depth": depth, "learning_rate": lr},
            )
        )
    return grid


def make_pipeline(estimator: Any) -> Pipeline:
    return Pipeline([("preprocess", build_preprocessor()), ("model", clone(estimator))])


def temporal_split(
    X: pd.DataFrame, y: pd.Series, meta: pd.DataFrame, train_frac: float = 0.70, val_frac: float = 0.15
) -> dict[str, tuple[pd.DataFrame, pd.Series, pd.DataFrame]]:
    # Rows are already sorted by appointment_datetime in build_training_frame.
    n = len(X)
    i_train, i_val = int(n * train_frac), int(n * (train_frac + val_frac))
    parts = {"train": slice(0, i_train), "validation": slice(i_train, i_val), "test": slice(i_val, n)}
    return {k: (X.iloc[s], y.iloc[s], meta.iloc[s]) for k, s in parts.items()}


def _period(meta: pd.DataFrame) -> dict[str, str]:
    return {
        "from": meta["appointment_datetime"].min().strftime("%Y-%m-%d"),
        "to": meta["appointment_datetime"].max().strftime("%Y-%m-%d"),
    }


def train(raw: pd.DataFrame, source: str, model_dir: Path) -> dict[str, Any]:
    X, y, meta = build_training_frame(raw)
    if len(X) < MIN_TRAINING_ROWS:
        raise ValueError(f"Need at least {MIN_TRAINING_ROWS} labelled appointments to train, got {len(X)}")
    split = temporal_split(X, y, meta)
    X_tr, y_tr, m_tr = split["train"]
    X_va, y_va, m_va = split["validation"]
    X_te, y_te, m_te = split["test"]
    logger.info("Split sizes: train=%d validation=%d test=%d (positive rate %.3f)", len(X_tr), len(X_va), len(X_te), y.mean())

    # --- 1) hyper-parameter selection per family on validation ---
    best_per_family: dict[str, dict[str, Any]] = {}
    tuning_log: list[dict[str, Any]] = []
    for cand in candidate_grid():
        pipe = make_pipeline(cand.estimator).fit(X_tr, y_tr)
        proba_va = pipe.predict_proba(X_va)[:, 1]
        auc = roc_auc_score(y_va, proba_va)
        tuning_log.append({"model": cand.family, "params": cand.params, "validation_roc_auc": round(float(auc), 4)})
        logger.info("%-20s %-60s val ROC-AUC=%.4f", cand.family, cand.params, auc)
        if cand.family not in best_per_family or auc > best_per_family[cand.family]["val_auc"]:
            best_per_family[cand.family] = {"candidate": cand, "val_auc": auc, "proba_va": proba_va}

    # --- 2) threshold tuning + validation metrics ---
    results: dict[str, dict[str, Any]] = {}
    for family, info in best_per_family.items():
        threshold = best_f1_threshold(y_va.to_numpy(), info["proba_va"])
        results[family] = {
            "display_name": info["candidate"].display_name,
            "params": info["candidate"].params,
            "decision_threshold": round(threshold, 3),
            "validation": classification_metrics(y_va.to_numpy(), info["proba_va"], threshold),
        }

    selected = max(
        results, key=lambda f: (results[f]["validation"]["no_show_f1"], results[f]["validation"]["roc_auc"])
    )
    logger.info("Selected model family: %s", selected)

    # --- 3) refit on train+validation, evaluate on held-out test ---
    X_fit, y_fit = pd.concat([X_tr, X_va]), pd.concat([y_tr, y_va])
    fitted: dict[str, Pipeline] = {}
    for family, info in best_per_family.items():
        pipe = make_pipeline(info["candidate"].estimator).fit(X_fit, y_fit)
        fitted[family] = pipe
        proba_te = pipe.predict_proba(X_te)[:, 1]
        thr = results[family]["decision_threshold"]
        results[family]["test"] = classification_metrics(y_te.to_numpy(), proba_te, thr)
        results[family]["test_at_0_5"] = classification_metrics(y_te.to_numpy(), proba_te, 0.5)
        if family == selected:
            results[family]["calibration"] = calibration_table(y_te.to_numpy(), proba_te)
        logger.info(
            "TEST %-20s thr=%.2f F1=%.4f recall=%.4f precision=%.4f AUC=%.4f acc=%.4f",
            family,
            thr,
            results[family]["test"]["no_show_f1"],
            results[family]["test"]["no_show_recall"],
            results[family]["test"]["no_show_precision"],
            results[family]["test"]["roc_auc"],
            results[family]["test"]["accuracy"],
        )

    # --- 4) explainability artefacts ---
    final = fitted[selected]
    rng = np.random.default_rng(RANDOM_STATE)
    background_idx = rng.choice(len(X_fit), size=min(300, len(X_fit)), replace=False)
    background = np.asarray(final.named_steps["preprocess"].transform(X_fit.iloc[background_idx]), dtype=float)
    explainer = ShapExplainer(final, background)
    sample_te = X_te.sample(n=min(1000, len(X_te)), random_state=RANDOM_STATE)
    global_importance = explainer.global_importance(sample_te)

    # --- 5) persist ---
    version = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    trained_at = datetime.now(UTC).isoformat()
    bundle = {
        "pipeline": final,
        "model_name": selected,
        "display_name": results[selected]["display_name"],
        "model_version": version,
        "trained_at": trained_at,
        "decision_threshold": results[selected]["decision_threshold"],
        "feature_columns": FEATURE_COLUMNS,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "background": background,
        "sklearn_version": sklearn.__version__,
        "xgboost_version": xgb.__version__,
    }
    metrics = {
        "model_version": version,
        "trained_at": trained_at,
        "data_source": source,
        "synthetic_data": source == "csv",
        "selected_model": selected,
        "selection_criterion": "highest validation no-show F1 (tie-break: validation ROC-AUC)",
        "split_strategy": "temporal 70/15/15 by appointment datetime; final models refit on train+validation",
        "dataset": {
            "raw_rows": int(len(raw)),
            "labelled_rows": int(len(X)),
            "unique_patients": int(raw["patient_id"].nunique()),
            "no_show_rate": round(float(y.mean()), 4),
            "splits": {
                "train": {"rows": len(X_tr), "no_show_rate": round(float(y_tr.mean()), 4), **_period(m_tr)},
                "validation": {"rows": len(X_va), "no_show_rate": round(float(y_va.mean()), 4), **_period(m_va)},
                "test": {"rows": len(X_te), "no_show_rate": round(float(y_te.mean()), 4), **_period(m_te)},
            },
        },
        "models": results,
        "hyperparameter_search": tuning_log,
        "global_feature_importance": global_importance,
        "features": {"numeric": NUMERIC_FEATURES, "categorical": CATEGORICAL_FEATURES},
    }
    model_dir.mkdir(parents=True, exist_ok=True)
    tmp_model = model_dir / "no_show_model.pkl.tmp"
    joblib.dump(bundle, tmp_model)
    tmp_model.replace(model_dir / "no_show_model.pkl")  # atomic swap so the API never loads a half-written file
    (model_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))
    logger.info("Saved model %s (%s) to %s", selected, version, model_dir)
    return metrics


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Train the appointment no-show model")
    parser.add_argument("--source", choices=["csv", "db"], default="csv")
    parser.add_argument("--data", type=Path, default=settings.dataset_path)
    parser.add_argument("--model-dir", type=Path, default=settings.MODEL_DIR)
    args = parser.parse_args()
    configure_logging(settings.LOG_LEVEL)

    if args.source == "db":
        from app.db.database import SessionLocal

        with SessionLocal() as db:
            raw = load_from_database(db)
    else:
        raw = load_csv(args.data)
    metrics = train(raw, args.source, args.model_dir)
    sel = metrics["models"][metrics["selected_model"]]["test"]
    logger.info("Selected %s | test no-show F1=%.4f ROC-AUC=%.4f", metrics["selected_model"], sel["no_show_f1"], sel["roc_auc"])


if __name__ == "__main__":
    main()
