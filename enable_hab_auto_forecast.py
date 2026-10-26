"""Apply to existing HAB_Risk_Forecasting repository from its root."""
from pathlib import Path
import re
import shutil

root = Path.cwd()
api = root / 'backend' / 'ml_api.py'
new_backend = root / 'backend' / 'auto_forecast.py'
page = root / 'frontend' / 'src' / 'pages' / 'Forecast.jsx'
original = root / 'frontend' / 'src' / 'pages' / 'ForecastOriginal.jsx'
manual = root / 'frontend' / 'src' / 'pages' / 'ForecastExperimentPanel.jsx'
component = root / 'frontend' / 'src' / 'pages' / 'AutoForecastPanel.jsx'
config = root / 'frontend' / 'vite.config.js'
for path in (api, page, original, manual, config):
    if not path.is_file():
        raise SystemExit(f'Expected existing file missing: {path}')

backend_code = '''"""Firestore-based on-demand monthly forecast for existing XGBoost API."""
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
    if not re.fullmatch(r'\\d{4}-(0[1-9]|1[0-2])', month):
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
'''

frontend_code = '''import React, { useEffect, useState } from 'react';

const LABELS = {
  temperature_c_median: 'Water temperature',
  pH_median: 'pH',
  DO_mg_l_median: 'Dissolved oxygen',
  insitu_chl_a_ug_l_median: 'In-situ chlorophyll-a (LLDA or verified source)',
  satellite_chl_monthly_median: 'Satellite monthly chlorophyll-a',
};

export default function AutoForecastPanel() {
  const [month, setMonth] = useState('2024-01');
  const [status, setStatus] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let ignore = false;
    setStatus(null);
    setResult(null);
    setError('');
    fetch(`/auto-forecast/${month}`)
      .then(async res => {
        const data = await res.json();
        if (!res.ok) throw new Error(JSON.stringify(data.detail || data));
        return data;
      })
      .then(data => { if (!ignore) setStatus(data); })
      .catch(e => { if (!ignore) setError(e.message); });
    return () => { ignore = true; };
  }, [month]);

  async function generate() {
    setBusy(true);
    setError('');
    try {
      const response = await fetch(`/auto-forecast/${month}`, { method: 'POST' });
      const data = await response.json();
      if (!response.ok) throw new Error(JSON.stringify(data.detail || data));
      setResult(data);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  return <section style={{background:'#fff',padding:20,borderRadius:12,
    border:'1px solid #d6e4d9',marginBottom:18}}>
    <h2 style={{marginTop:0}}>Automated Monthly Forecast</h2>
    <p>Reads monthly records from Firestore. No fabricated measurements.</p>
    <label>Observation month{' '}
      <input type="month" value={month} onChange={e => setMonth(e.target.value)} />
    </label>
    {!status && !error && <p>Checking monthly inputs...</p>}
    {status && <div style={{marginTop:12}}>
      <p><strong>{status.ready ? 'All inputs available' : 'Waiting for missing records'}</strong></p>
      <div>Sensor record: {status.sensor_record_found ? 'found' : 'missing'} ·
        Satellite monthly record: {status.satellite_record_found ? 'found' : 'missing'}</div>
      <ul>{Object.entries(status.inputs).filter(([k]) => k !== 'month')
        .map(([key, value]) => <li key={key}>{LABELS[key]}: {value}</li>)}</ul>
      {status.missing.length > 0 && <p>
        Missing: {status.missing.map(k => LABELS[k] || k).join(', ')}
      </p>}
      <button type="button" disabled={!status.ready || busy}
        onClick={generate} style={{padding:'10px 16px',borderRadius:7,
        background:'#146c46',color:'#fff',border:0,
        opacity:status.ready ? 1 : .55}}>
        {busy ? 'Forecasting...' : 'Generate & Save Forecast'}
      </button>
    </div>}
    {error && <p style={{color:'#a11'}}>Error: {error}</p>}
    {result && <div style={{padding:12,marginTop:12,background:'#eaf4ed'}}>
      <strong>Forecast for {result.forecast_month}</strong>
      <p style={{fontSize:24,margin:'8px 0'}}>
        {(result.bloom_probability*100).toFixed(1)}% · {result.prediction}
      </p>
      <small>Saved to Firestore · {result.model_status} · {result.dataset}</small>
    </div>}
    <p style={{fontSize:12,color:'#6d5240'}}>
      Experimental Lake Okeechobee model, not a validated Laguna de Bay warning.
    </p>
  </section>;
}
'''

wrapper = '''import React from 'react';
import Original from './ForecastOriginal.jsx';
import ForecastExperimentPanel from './ForecastExperimentPanel.jsx';
import AutoForecastPanel from './AutoForecastPanel.jsx';
export default function Forecast() {
  return <><AutoForecastPanel />
    <details style={{marginBottom:20}}><summary>Manual experimental test</summary>
      <ForecastExperimentPanel />
    </details>
    <Original />
  </>;
}
'''

cfg = config.read_text()
if "'/auto-forecast'" not in cfg and '"/auto-forecast"' not in cfg:
    proxy_entry = "'/auto-forecast': 'http://127.0.0.1:8000',"
    if re.search(r'proxy\s*:\s*\{', cfg):
        cfg = re.sub(r'(proxy\s*:\s*\{)', lambda m: m.group(1) + ' ' + proxy_entry, cfg, count=1)
    elif re.search(r'server\s*:\s*\{', cfg):
        cfg = re.sub(r'(server\s*:\s*\{)', lambda m: m.group(1) + ' proxy: {' + proxy_entry + '},', cfg, count=1)
    elif 'defineConfig({' in cfg:
        cfg = cfg.replace('defineConfig({', 'defineConfig({\n server: { proxy: {' + proxy_entry + '} },', 1)
    else:
        raise SystemExit('Unknown Vite config; refusing to modify files')

api_text = api.read_text()
if 'from backend.auto_forecast import router as auto_router' not in api_text:
    api_text += '\nfrom backend.auto_forecast import router as auto_router\napp.include_router(auto_router)\n'

compile(backend_code, str(new_backend), 'exec')
compile(api_text, str(api), 'exec')
for file in (api, page, config):
    shutil.copy2(file, str(file) + '.before_auto_forecast.bak')

new_backend.write_text(backend_code)
component.write_text(frontend_code)
page.write_text(wrapper)
api.write_text(api_text)
config.write_text(cfg)
print('AUTO FORECAST INSTALLED. Firestore monthly fusion and forecast saving wired.')
print('Existing ForecastOriginal and manual form preserved.')
print('Restart FastAPI and Vite, then open the existing Forecast page.')
