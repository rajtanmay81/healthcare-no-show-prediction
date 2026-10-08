"""Evaluation metrics focused on the positive (no-show) class."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def classification_metrics(y_true: np.ndarray, proba: np.ndarray, threshold: float) -> dict[str, object]:
    y_pred = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "threshold": round(float(threshold), 3),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, proba)), 4),
        "pr_auc": round(float(average_precision_score(y_true, proba)), 4),
        "brier_score": round(float(brier_score_loss(y_true, proba)), 4),
        # Positive class = no-show
        "no_show_precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "no_show_recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "no_show_f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "attended_precision": round(float(precision_score(y_true, y_pred, pos_label=0, zero_division=0)), 4),
        "attended_recall": round(float(recall_score(y_true, y_pred, pos_label=0, zero_division=0)), 4),
        "macro_f1": round(float(f1_score(y_true, y_pred, average="macro", zero_division=0)), 4),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def best_f1_threshold(y_true: np.ndarray, proba: np.ndarray) -> float:
    """Decision threshold maximising no-show F1 (tuned on validation data only)."""
    grid = np.arange(0.10, 0.81, 0.01)
    scores = [f1_score(y_true, (proba >= t).astype(int), zero_division=0) for t in grid]
    return float(grid[int(np.argmax(scores))])


def calibration_table(y_true: np.ndarray, proba: np.ndarray, bins: int = 10) -> list[dict[str, float]]:
    """Mean predicted vs observed no-show rate per probability decile."""
    edges = np.linspace(0, 1, bins + 1)
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        mask = (proba >= lo) & (proba < hi if hi < 1 else proba <= hi)
        if mask.sum() == 0:
            continue
        rows.append(
            {
                "bin": f"{lo:.1f}-{hi:.1f}",
                "n": int(mask.sum()),
                "mean_predicted": round(float(proba[mask].mean()), 4),
                "observed_rate": round(float(y_true[mask].mean()), 4),
            }
        )
    return rows
