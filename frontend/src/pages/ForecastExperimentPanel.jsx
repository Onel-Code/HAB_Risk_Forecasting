
import React, { useEffect, useState } from 'react';
import { collection, getDocs } from 'firebase/firestore';
import { db } from '../firebase';

const fields = [
  ['temperature_c_median', 'Water temperature (°C)'],
  ['pH_median', 'pH'],
  ['DO_mg_l_median', 'Dissolved oxygen (mg/L)'],
  ['insitu_chl_a_ug_l_median', 'In-situ chlorophyll-a (µg/L)'],
  ['satellite_chl_monthly_median', 'Satellite chlorophyll-a (µg/L)'],
];

export default function ForecastExperimentPanel() {
  const [values, setValues] = useState({
    month: '2024-01',
    temperature_c_median: '',
    pH_median: '',
    DO_mg_l_median: '',
    insitu_chl_a_ug_l_median: '',
    satellite_chl_monthly_median: '',
  });
  const [satellite, setSatellite] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getDocs(collection(db, 'satellite_monthly'))
      .then(snapshot => {
        const rows = snapshot.docs
          .map(doc => ({ id: doc.id, ...doc.data() }))
          .filter(row =>
            row.month &&
            row.satellite_chl_monthly_median != null
          );
        setSatellite(rows);
      })
      .catch(err => {
        console.warn('Monthly satellite lookup:', err.message);
      });
  }, []);

  const update = (key, value) => {
    setValues(prev => ({ ...prev, [key]: value }));
    setResult(null);
  };

  const useSatellite = (row) => {
    setValues(prev => ({
      ...prev,
      month: row.month,
      satellite_chl_monthly_median:
        String(row.satellite_chl_monthly_median),
    }));
    setResult(null);
  };

  async function forecast(e) {
    e.preventDefault();
    setLoading(true);
    setError('');
    setResult(null);

    try {
      const payload = { month: values.month };
      for (const [key] of fields) {
        if (values[key].trim() === '') {
          throw new Error('Complete all five measurements.');
        }
        payload[key] = Number(values[key]);
        if (!Number.isFinite(payload[key])) {
          throw new Error('Measurements must be numbers.');
        }
      }

      const response = await fetch('/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(
          typeof data.detail === 'string'
            ? data.detail
            : JSON.stringify(data.detail || data)
        );
      }
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const card = {
    background: '#fff',
    border: '1px solid #d7e3dc',
    borderRadius: 14,
    padding: 22,
    marginBottom: 20,
  };
  const input = {
    padding: '10px 12px',
    border: '1px solid #cad5d0',
    borderRadius: 8,
    width: '100%',
    boxSizing: 'border-box',
  };

  return (
    <section style={card}>
      <h2 style={{ marginTop: 0 }}>Next-Month Bloom Forecast</h2>
      <p>
        Experimental XGBoost model trained on Lake Okeechobee data.
        Not validated for Laguna de Bay or HAB toxicity.
      </p>

      {satellite.length > 0 && (
        <div style={{ marginBottom: 18, padding: 12,
                      background: '#edf6f0', borderRadius: 8 }}>
          <strong>Real satellite monthly records</strong>
          {satellite.map(row => (
            <div key={row.id} style={{ marginTop: 8 }}>
              {row.month}: {row.satellite_chl_monthly_median} µg/L
              {' '}
              <button type="button"
                onClick={() => useSatellite(row)}>
                Use satellite value
              </button>
            </div>
          ))}
        </div>
      )}

      <form onSubmit={forecast}>
        <label style={{ display: 'block', marginBottom: 14 }}>
          Observation month
          <input type="month" required style={input}
            value={values.month}
            onChange={e => update('month', e.target.value)} />
        </label>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
          gap: 14
        }}>
          {fields.map(([key, label]) => (
            <label key={key}>
              <span style={{ display: 'block', marginBottom: 5 }}>
                {label}
              </span>
              <input type="number" step="any" required
                style={input}
                value={values[key]}
                onChange={e => update(key, e.target.value)} />
            </label>
          ))}
        </div>

        <button type="submit" disabled={loading}
          style={{
            marginTop: 20, padding: '12px 20px',
            background: '#176c49', color: '#fff',
            border: 0, borderRadius: 8, cursor: 'pointer'
          }}>
          {loading ? 'Running XGBoost...' : 'Generate Forecast'}
        </button>
      </form>

      {error && (
        <p style={{ color: '#b42318' }}>Error: {error}</p>
      )}

      {result && (
        <div style={{
          marginTop: 20, padding: 18,
          background: '#edf6f0', borderRadius: 10
        }}>
          <h3>Forecast for {result.forecast_month}</h3>
          <div style={{ fontSize: 32, fontWeight: 700 }}>
            {(result.bloom_probability * 100).toFixed(1)}%
          </div>
          <p>Predicted class: <b>{result.prediction}</b></p>
          <small>
            {result.model_status} · {result.dataset}
            <br />{result.warning}
          </small>
        </div>
      )}
    </section>
  );
}
