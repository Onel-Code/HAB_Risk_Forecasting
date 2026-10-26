"""Research prototype API for a next-month algal bloom occurrence demo.

This code does not validate bloom toxicity or establish model reliability.
The model is an exploratory Lake Okeechobee model; do not present its
outputs as a validated warning service for Laguna de Bay.
"""

from datetime import datetime, timedelta
from functools import lru_cache
import logging
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, FiniteFloat
from xgboost import XGBClassifier

logger = logging.getLogger(__name__)

app = FastAPI(title="Algal Bloom Forecasting API", version="0.2.0")

MODEL_PATH = Path(__file__).resolve().parent / "models" / "xgb_fusion_exploratory.json"
FEATURES = [
    "temperature_c_median",
    "pH_median",
    "DO_mg_l_median",
    "insitu_chl_a_ug_l_median",
    "satellite_chl_monthly_median",
]
THRESHOLD = 0.5
MODEL_STATUS = "EXPERIMENTAL_NOT_VALIDATED"
MODEL_DATASET = "Lake Okeechobee practice model"
WARNING = "Research demonstration only. Not validated for operational bloom warnings."


class PredictionInput(BaseModel):
    # This date determines the target month, but is NOT a trained model feature.
    month: str
    temperature_c_median: FiniteFloat
    pH_median: FiniteFloat
    DO_mg_l_median: FiniteFloat
    insitu_chl_a_ug_l_median: FiniteFloat
    satellite_chl_monthly_median: FiniteFloat


class HistoricalCase(PredictionInput):
    case_id: str = Field(min_length=1, max_length=120)
    # Must come from actual historical evidence or an explicitly stated proxy.
    actual_bloom: Literal[0, 1]
    label_type: Literal["verified", "proxy"]


class EvaluationRequest(BaseModel):
    cases: list[HistoricalCase] = Field(min_length=10, max_length=10)


@lru_cache(maxsize=1)
def load_model():
    model = XGBClassifier()
    model.load_model(str(MODEL_PATH))
    return model


def forecast_month(month: str) -> str:
    """Compute the next month, requiring YYYY-MM rather than a loose date."""
    try:
        if len(month) != 7 or month[4] != "-" or not (month[:4] + month[5:]).isdigit():
            raise ValueError("Invalid month")
        current = datetime.strptime(month, "%Y-%m")
        if current.strftime("%Y-%m") != month:
            raise ValueError("Invalid month")
        nxt = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
        return nxt.strftime("%Y-%m")
    except (ValueError, OverflowError):
        raise HTTPException(status_code=422, detail="Use a valid YYYY-MM for month") from None


def predict_probabilities(records: list[PredictionInput]) -> list[float]:
    """Run one batched model inference while preserving Colab feature order."""
    frame = pd.DataFrame(
        [{field: getattr(item, field) for field in FEATURES} for item in records],
        columns=FEATURES,
    )
    try:
        probabilities = load_model().predict_proba(frame)[:, 1]
        return [float(value) for value in probabilities]
    except Exception:
        logger.exception("Experimental model could not produce predictions")
        raise HTTPException(status_code=503, detail="Experimental model unavailable") from None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_available": MODEL_PATH.is_file(),
        "model_status": "experimental",
        "requires_in_situ_chlorophyll_a": True,
        "month_is_model_feature": False,
    }


@app.post("/predict")
def predict(data: PredictionInput):
    target_month = forecast_month(data.month)
    probability = predict_probabilities([data])[0]
    return {
        "forecast_month": target_month,
        "bloom_probability": round(probability, 4),
        "prediction": "BLOOM" if probability >= THRESHOLD else "NO_BLOOM",
        "threshold": THRESHOLD,
        "model_status": MODEL_STATUS,
        "dataset": MODEL_DATASET,
        "warning": WARNING,
    }


@app.post("/evaluate")
def evaluate(request: EvaluationRequest):
    """Score EXACTLY ten supplied historical cases against supplied actual/proxy labels.

    The endpoint cannot verify whether records were held out during training,
    nor can it independently confirm any supplied outcome label.
    """
    cases = request.cases
    identifiers = [item.case_id for item in cases]
    if len(set(identifiers)) != len(identifiers):
        raise HTTPException(status_code=422, detail="case_id must be unique for all ten cases")

    target_months = [forecast_month(item.month) for item in cases]
    probabilities = predict_probabilities(cases)

    results = []
    tp = tn = fp = fn = 0
    for item, target, probability in zip(cases, target_months, probabilities):
        predicted = int(probability >= THRESHOLD)
        actual = item.actual_bloom
        tp += int(predicted == 1 and actual == 1)
        tn += int(predicted == 0 and actual == 0)
        fp += int(predicted == 1 and actual == 0)
        fn += int(predicted == 0 and actual == 1)
        results.append({
            "case_id": item.case_id,
            "observation_month": item.month,
            "forecast_month": target,
            "bloom_probability": round(probability, 4),
            "prediction": "BLOOM" if predicted else "NO_BLOOM",
            "actual": "BLOOM" if actual else "NO_BLOOM",
            "label_type": item.label_type,
            "correct": predicted == actual,
        })

    correct = tp + tn
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    proxy_present = any(item.label_type == "proxy" for item in cases)

    return {
        "cases_evaluated": 10,
        "correct_count": correct,
        "score_out_of_10": f"{correct}/10",
        "accuracy_against_supplied_labels": round(correct / 10, 4),
        "score_type": "PROXY_LABEL_AGREEMENT" if proxy_present else "REPORTED_HISTORICAL_ACCURACY",
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "confusion_matrix": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
        "always_bloom_baseline_accuracy": round((tp + fn) / 10, 4),
        "test_set_separation_verified": False,
        "model_status": MODEL_STATUS,
        "dataset": MODEL_DATASET,
        "warning": (
            WARNING
            + " Historical labels are supplied by the user and not verified by this API. "
            + "Training/test separation is not verified by this API. "
            + ("At least one label is a proxy, so do not describe this score as validated accuracy."
               if proxy_present else "Confirm the outcomes and untouched test split before reporting accuracy.")
        ),
        "results": results,
    }



from backend.auto_forecast import (
    preview as hab_auto_preview,
    run_forecast as hab_auto_run
)

app.add_api_route(
    "/auto-forecast/{month}",
    hab_auto_preview,
    methods=["GET"],
    tags=["Automated forecast"]
)

app.add_api_route(
    "/auto-forecast/{month}",
    hab_auto_run,
    methods=["POST"],
    tags=["Automated forecast"]
)

# Isolated technical test: does not create real monitoring/forecast records.
from backend.demo_pipeline import replay_preview, run_replay
app.add_api_route('/auto-forecast/demo/{month}', replay_preview, methods=['GET'], tags=['Pipeline simulation'])
app.add_api_route('/auto-forecast/demo/{month}', run_replay, methods=['POST'], tags=['Pipeline simulation'])

# PROTECTED_ESP32_DEVICE_INGEST_V1
from backend.insitu_ingest import ingest_device_reading
app.add_api_route(
    '/api/insitu/reading', ingest_device_reading, methods=['POST'],
    tags=['In-situ hardware ingestion'])
