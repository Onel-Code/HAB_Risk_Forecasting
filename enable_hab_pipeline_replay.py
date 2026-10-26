"""Add a clearly labeled, reproducible sensor/satellite/XGBoost replay to an existing HAB React/FastAPI app.
Run from the HAB_Risk_Forecasting repository root. Never writes to production sensor or forecast collections.
"""
from pathlib import Path
import shutil

root = Path.cwd()
api = root / 'backend/ml_api.py'
backend = root / 'backend/demo_pipeline.py'
forecast = root / 'frontend/src/pages/Forecast.jsx'
panel = root / 'frontend/src/pages/DemoPipelinePanel.jsx'
auto = root / 'backend/auto_forecast.py'
for path in (api, forecast, auto):
    if not path.is_file():
        raise SystemExit(f'Expected existing project file not found: {path}')

api_source = api.read_text()
forecast_source = forecast.read_text()
if 'DemoPipelinePanel' not in forecast_source and '<AutoForecastPanel />' not in forecast_source:
    raise SystemExit('Existing Forecast.jsx differs from installed version; no files changed.')

backend_source = '''"""Explicitly simulated monthly pipeline replay. NEVER interpretable as real Laguna forecasts."""
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
    if not re.fullmatch(r'\\d{4}-(0[1-9]|1[0-2])', month):
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
'''

component_source = '''import React, { useEffect, useState } from 'react';

export default function DemoPipelinePanel() {
  const [month, setMonth] = useState('2024-01');
  const [availability, setAvailability] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setResult(null);
    setError('');
    setAvailability(null);
    fetch(`/auto-forecast/demo/${month}`)
      .then(async res => {
        const data = await res.json();
        if (!res.ok) throw new Error(JSON.stringify(data.detail || data));
        return data;
      })
      .then(data => { if (active) setAvailability(data); })
      .catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [month]);

  async function runReplay() {
    setBusy(true); setError(''); setResult(null);
    try {
      const response = await fetch(`/auto-forecast/demo/${month}`, { method: 'POST' });
      const data = await response.json();
      if (!response.ok) throw new Error(JSON.stringify(data.detail || data));
      setResult(data);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  return <section style={{background:'#fff',padding:20,borderRadius:12,
    border:'1px solid #d6e4d9',marginBottom:18}}>
    <h2 style={{marginTop:0}}>Pipeline Replay: Technical Proof</h2>
    <p><strong>SIMULATION MODE.</strong> Replays seven synthetic sensor readings,
      combines their monthly medians with a genuine Sentinel-3 satellite monthly
      value, runs the existing experimental XGBoost model, and saves traceable
      results in separate <code>demo_*</code> Firestore collections.</p>
    <label>Observation month{' '}
      <input type="month" value={month} onChange={e => setMonth(e.target.value)} />
    </label>
    {availability && <p>
      Real satellite monthly record: <strong>{availability.satellite_monthly_available
        ? `${availability.satellite_chl_monthly_median} µg/L` : 'Unavailable'}</strong>
    </p>}
    {error && <p style={{color:'#aa1822'}}>Error: {error}</p>}
    <button onClick={runReplay} type="button" disabled={busy || !availability?.satellite_monthly_available}
      style={{background:'#176c49',color:'white',border:0,borderRadius:8,
        padding:'11px 17px',opacity:busy || !availability?.satellite_monthly_available ? .5 : 1}}>
      {busy ? 'Running pipeline...' : 'Run labeled simulation & save results'}
    </button>
    {result && <div style={{background:'#fff5e6',padding:14,borderRadius:8,marginTop:14}}>
      <strong>TECHNICAL DEMO ONLY: NOT A REAL LAGUNA FORECAST</strong>
      <p>Replayed {result.simulated_reading_count} synthetic sensor readings →
        monthly medians → real Laguna satellite feature → experimental XGBoost.</p>
      <p>Forecast period: <strong>{result.forecast_month}</strong></p>
      <p style={{fontSize:24,fontWeight:700}}>
        {(result.bloom_probability*100).toFixed(1)}% · {result.prediction}
      </p>
      <p>Saved as <code>demo_sensor_readings</code>, <code>demo_fused_monthly</code>,
        and <code>demo_forecasts</code> in Firestore.</p>
      <small>No scientific accuracy or Laguna prediction validity established by this replay.
        The in-situ chlorophyll value is an independently simulated lab input, not an ESP32 sensor.
      </small>
    </div>}
  </section>;
}
'''

if 'demo_pipeline' not in api_source:
    api_source += '''\n# Isolated technical test: does not create real monitoring/forecast records.\nfrom backend.demo_pipeline import replay_preview, run_replay\napp.add_api_route('/auto-forecast/demo/{month}', replay_preview, methods=['GET'], tags=['Pipeline simulation'])\napp.add_api_route('/auto-forecast/demo/{month}', run_replay, methods=['POST'], tags=['Pipeline simulation'])\n'''
if 'DemoPipelinePanel' not in forecast_source:
    forecast_source = forecast_source.replace("import AutoForecastPanel from './AutoForecastPanel.jsx';", "import AutoForecastPanel from './AutoForecastPanel.jsx';\nimport DemoPipelinePanel from './DemoPipelinePanel.jsx';")
    if "import DemoPipelinePanel from './DemoPipelinePanel.jsx';" not in forecast_source:
        forecast_source = "import DemoPipelinePanel from './DemoPipelinePanel.jsx';\n" + forecast_source
    forecast_source = forecast_source.replace('<AutoForecastPanel />', '<AutoForecastPanel />\n    <DemoPipelinePanel />', 1)

compile(backend_source, str(backend), 'exec')
compile(api_source, str(api), 'exec')
if 'DemoPipelinePanel' not in forecast_source:
    raise SystemExit('Failed to inject replay component. No changes made.')

for file in (api, forecast):
    shutil.copy2(file, str(file) + '.before_pipeline_replay.bak')
backend.write_text(backend_source)
panel.write_text(component_source)
api.write_text(api_source)
forecast.write_text(forecast_source)
print('PIPELINE REPLAY INSTALLED: a labeled simulation button was added to the existing Forecast page.')
print('No production Firestore collections are changed by the installer.')
print('Restart FastAPI with --reload and Vite; refresh Forecast, choose 2024-01 and click replay.')
