"""Explicitly simulated monthly pipeline replay. NEVER interpretable as real Laguna forecasts."""
import re
from statistics import median
from datetime import date
from fastapi import HTTPException
from firebase_admin import firestore

from backend.auto_forecast import find_month

# These are FIXTURES, not environmental observations. One value for a lab
# chlorophyll measurement is intentionally separate from IoT sensors.
SIMULATED_SENSOR_VALUES = (
    (28.1, 7.8, 5.8), (28.3, 7.9, 6.1), (28.0, 8.0, 5.9),
    (28.4, 7.9, 6.0), (27.9, 8.1, 6.2), (28.2, 8.0, 5.7),
    (28.5, 7.9, 6.1),
)
SIMULATED_LAB_CHL_A = 16.2


def _details(month):
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', month):
        raise HTTPException(422, 'Month must use YYYY-MM')
    db, info = find_month(month)
    chl = info['inputs'].get('satellite_chl_monthly_median')
    return db, info, chl


def replay_preview(month: str):
    _, info, chl = _details(month)
    return {
        'month': month,
        'satellite_monthly_available': chl is not None,
        'satellite_chl_monthly_median': chl,
        'simulation': True,
        'note': 'Only satellite data are observed. In-situ readings and lab chlorophyll for the replay are SYNTHETIC.'
    }


def run_replay(month: str):
    db, info, chl = _details(month)
    if chl is None:
        raise HTTPException(409, 'No eligible real satellite monthly chlorophyll for selected month')

    temps = [row[0] for row in SIMULATED_SENSOR_VALUES]
    phs = [row[1] for row in SIMULATED_SENSOR_VALUES]
    dissolved = [row[2] for row in SIMULATED_SENSOR_VALUES]

    inputs = {
        'month': month,
        'temperature_c_median': float(median(temps)),
        'pH_median': float(median(phs)),
        'DO_mg_l_median': float(median(dissolved)),
        'insitu_chl_a_ug_l_median': float(SIMULATED_LAB_CHL_A),
        'satellite_chl_monthly_median': float(chl),
    }

    # Invoke EXACTLY the saved experimental XGBoost /predict implementation.
    from backend.ml_api import PredictionInput, predict
    prediction = predict(PredictionInput(**inputs))

    lineage = {
        'satellite': 'REAL Sentinel-3 OLCI CHL_NN preliminary Laguna satellite_monthly record',
        'water_temperature': 'SIMULATED IoT test fixture',
        'pH': 'SIMULATED IoT test fixture',
        'dissolved_oxygen': 'SIMULATED IoT test fixture',
        'in_situ_chlorophyll': 'SIMULATED external lab test fixture; not a device sensor',
        'model': 'EXPERIMENTAL Lake Okeechobee model, not validated for Laguna',
    }
    test_id = month + '_PIPELINE_SIMULATION'
    batch = db.batch()
    for i, (temperature, ph, do) in enumerate(SIMULATED_SENSOR_VALUES):
        # The dates are test playback labels, NOT acquisition timestamps.
        reading_date = date(int(month[:4]), int(month[5:]), 2 + 4 * i).isoformat()
        ref = db.collection('demo_sensor_readings').document(f'{test_id}_{i+1:02d}')
        batch.set(ref, {
            'month': month, 'testDateLabel': reading_date,
            'temperatureC': temperature, 'pH': ph, 'dissolvedOxygenMgL': do,
            'isSimulated': True, 'source': 'Synthetic IoT monitoring test fixture',
            'dataUse': 'TECHNICAL_PIPELINE_DEMO_ONLY',
        })
    fused_ref = db.collection('demo_fused_monthly').document(test_id)
    batch.set(fused_ref, {
        'month': month, 'inputs': inputs, 'lineage': lineage,
        'isSimulated': True, 'status': 'MIXED_REAL_SATELLITE_AND_SYNTHETIC_INSITU',
        'validationStatus': 'EXPERIMENTAL_NOT_VALIDATED',
    })
    forecast_ref = db.collection('demo_forecasts').document(test_id)
    batch.set(forecast_ref, {
        'observation_month': month, **prediction,
        'inputs': inputs, 'lineage': lineage,
        'isSimulated': True, 'status': 'PIPELINE_SIMULATION_NOT_A_LAGUNA_FORECAST',
        'createdAt': firestore.SERVER_TIMESTAMP,
    })
    batch.commit()

    return {
        'saved': True, 'simulation': True,
        'forecast_collection': 'demo_forecasts',
        'month': month, 'inputs': inputs, 'lineage': lineage,
        'simulated_reading_count': len(SIMULATED_SENSOR_VALUES),
        **prediction,
        'warning': 'This proves software integration ONLY. Not a real Laguna forecast or an accuracy test.',
    }
