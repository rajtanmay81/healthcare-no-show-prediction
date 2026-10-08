"""Exploratory data analysis on the (synthetic) appointment dataset.

Prints and saves a JSON summary of the relationships that motivate the engineered features.

Usage:
    python -m app.ml.eda [--data data/appointments.csv]
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import pandas as pd

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.ml.preprocessing import OUTCOME_STATUSES, engineer_features

logger = logging.getLogger(__name__)


def _rate_by(frame: pd.DataFrame, column: str) -> dict[str, dict[str, float]]:
    grouped = frame.groupby(column, observed=True)["no_show"].agg(["mean", "count"])
    return {str(k): {"no_show_rate": round(float(v["mean"]), 4), "n": int(v["count"])} for k, v in grouped.iterrows()}


def run_eda(raw: pd.DataFrame) -> dict[str, object]:
    feats = engineer_features(raw)
    labelled = feats[feats["status"].isin(OUTCOME_STATUSES)].copy()
    labelled["no_show"] = (labelled["status"] == "no_show").astype(int)
    labelled["lead_bucket"] = pd.cut(labelled["booking_lead_days"], [-1, 2, 7, 21, 60, 10_000], labels=["0-2", "3-7", "8-21", "22-60", "60+"])
    labelled["prev_no_show_bucket"] = labelled["previous_no_shows"].clip(upper=3).astype(str).replace({"3": "3+"})
    labelled["prev_cancel_bucket"] = labelled["previous_cancellations"].clip(upper=2).astype(str).replace({"2": "2+"})

    return {
        "rows": int(len(raw)),
        "unique_patients": int(raw["patient_id"].nunique()),
        "status_counts": raw["status"].value_counts().to_dict(),
        "labelled_rows": int(len(labelled)),
        "overall_no_show_rate": round(float(labelled["no_show"].mean()), 4),
        "by_department": _rate_by(labelled, "department"),
        "by_day_of_week": _rate_by(labelled, "day_of_week"),
        "by_age_group": _rate_by(labelled, "age_group"),
        "by_booking_lead_days": _rate_by(labelled, "lead_bucket"),
        "by_previous_no_shows": _rate_by(labelled, "prev_no_show_bucket"),
        "by_previous_cancellations": _rate_by(labelled, "prev_cancel_bucket"),
        "missing_values": {k: int(v) for k, v in feats.isna().sum().items() if v},
    }


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=settings.dataset_path)
    parser.add_argument("--out", type=Path, default=settings.MODEL_DIR / "eda_summary.json")
    args = parser.parse_args()
    configure_logging()

    summary = run_eda(pd.read_csv(args.data))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2))
    for key in ("overall_no_show_rate", "by_previous_no_shows", "by_booking_lead_days", "by_previous_cancellations", "by_department"):
        logger.info("%s: %s", key, summary[key])
    logger.info("EDA summary written to %s", args.out)


if __name__ == "__main__":
    main()
