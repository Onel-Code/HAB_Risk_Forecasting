# backend/ml_api.py

from pathlib import Path
from datetime import datetime, timedelta
from functools import lru_cache

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, FiniteFloat
from xgboost import XGBClassifier

app = FastAPI(
    title="Algal Bloom Forecasting API",
    version="0.1.0"
)

MODEL_PATH = (
    Path(__file__).resolve().parent
    / "models"
    / "xgb_fusion_exploratory.json"
)

FEATURES = [
    "temperature_c_median",
    "pH_median",
    "DO_mg_l_median",
    "insitu_chl_a_ug_l_median",
    "satellite_chl_monthly_median"
]


class PredictionInput(BaseModel):
    month: str
    temperature_c_median: FiniteFloat
    pH_median: FiniteFloat
    DO_mg_l_median: FiniteFloat
    insitu_chl_a_ug_l_median: FiniteFloat
    satellite_chl_monthly_median: FiniteFloat


@lru_cache(maxsize=1)
def load_model():
    model = XGBClassifier()
    model.load_model(str(MODEL_PATH))
    return model


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_available": MODEL_PATH.is_file(),
        "model_status": "experimental"
    }


@app.post("/predict")
def predict(data: PredictionInput):

    # Validate observation month
    try:
        if len(data.month) != 7:
            raise ValueError("Invalid month")

        current = datetime.strptime(data.month, "%Y-%m")
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="Use YYYY-MM for month"
        )

    # Calculate the next calendar month
    next_month = (
        current.replace(day=28)
        + timedelta(days=4)
    ).replace(day=1)

    # Preserve exact feature order used in Colab
    values = data.model_dump()
    X = pd.DataFrame([{
        feature: values[feature]
        for feature in FEATURES
    }])

    # Load model and generate probability
    try:
        model = load_model()
        probability = float(model.predict_proba(X)[0, 1])
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Experimental model unavailable"
        )

    prediction = (
        "BLOOM" if probability >= 0.5 else "NO_BLOOM"
    )

    return {
        "forecast_month": next_month.strftime("%Y-%m"),
        "bloom_probability": round(probability, 4),
        "prediction": prediction,
        "threshold": 0.5,
        "model_status": "EXPERIMENTAL_NOT_VALIDATED",
        "dataset": "Lake Okeechobee practice model",
        "warning": (
            "Research demonstration only. "
            "Not validated for operational bloom warnings."
        )
    }
