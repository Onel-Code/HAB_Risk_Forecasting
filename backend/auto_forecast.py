"""Firestore-based on-demand monthly forecast for existing XGBoost API."""
import json
import math
import os
import re
from functools import lru_cache

import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix='/auto-forecast', tags=['Automated forecast'])
SENSOR_FEATURES = (
    'temperature_c_median', 'pH_median',
    'DO_mg_l_median', 'insitu_chl_a_ug_l_median'
)
SAT_FEATURE = 'satellite_chl_monthly_median'

@lru_cache(maxsize=1)
def get_database():
    key = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON')
    if not key:
        raise HTTPException(503, 'FIREBASE_SERVICE_ACCOUNT_JSON unavailable')
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(json.loads(key)))
    return firestore.client()

def find_month(month):
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', month):
        raise HTTPException(422, 'Use YYYY-MM')
    db = get_database()
    sensor = db.collection('insitu_monthly').document(month).get()
    insitu = sensor.to_dict() if sensor.exists else {}
    sat_ref = db.collection('satellite_monthly').document(month + '_laguna_test_point').get()
    if sat_ref.exists:
        satellite = sat_ref.to_dict() or {}
    else:
        matches = list(db.collection('satellite_monthly').where('month', '==', month).limit(10).stream())
        satellite = next((doc.to_dict() for doc in matches
            if (doc.to_dict() or {}).get('validAcquisitions', 0) > 0), {})
    inputs = {'month': month}
    missing = []
    for key in SENSOR_FEATURES:
        value = insitu.get(key)
        if value is None or isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
            missing.append(key)
        else:
            inputs[key] = float(value)
    chl = satellite.get(SAT_FEATURE)
    if (not isinstance(chl, (float, int)) or isinstance(chl, bool)
            or not math.isfinite(chl) or satellite.get('validAcquisitions', 0) < 1):
        missing.append(SAT_FEATURE)
    else:
        inputs[SAT_FEATURE] = float(chl)
    if insitu.get('isSimulated') or str(insitu.get('source', '')).lower().startswith(('demo', 'simulat')):
        raise HTTPException(409, 'Demo sensor data cannot be used as real inputs')
    return db, {'month': month, 'ready': not missing, 'inputs': inputs,
        'missing': missing, 'sensor_record_found': sensor.exists,
        'satellite_record_found': bool(satellite),
        'note': 'Lake Okeechobee exploratory model; not validated for Laguna de Bay'}

@router.get('/{month}')
def preview(month: str):
    _, info = find_month(month)
    return info

@router.post('/{month}')
def run_forecast(month: str):
    db, info = find_month(month)
    if not info['ready']:
        raise HTTPException(409, {'missing': info['missing'],
            'message': 'Cannot forecast: genuine monthly inputs are missing'})
    from backend.ml_api import PredictionInput, predict
    result = predict(PredictionInput(**info['inputs']))
    db.collection('forecasts').document(month + '_exploratory').set({
        **result, 'observation_month': month, 'inputs': info['inputs'],
        'source': 'Firestore monthly sensor + satellite fusion',
        'createdAt': firestore.SERVER_TIMESTAMP,
        'validationStatus': 'EXPERIMENTAL_NOT_VALIDATED',
    })
    return {'saved': True, **result}
