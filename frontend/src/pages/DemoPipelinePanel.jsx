import React, { useEffect, useState } from 'react';

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
