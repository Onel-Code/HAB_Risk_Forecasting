import React, { useEffect, useState } from 'react';

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
