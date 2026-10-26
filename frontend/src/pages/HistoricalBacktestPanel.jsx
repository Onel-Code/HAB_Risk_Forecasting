import React, { useEffect, useState } from 'react';

const pct = (v) => `${(100 * Number(v || 0)).toFixed(1)}%`;
const yName = (v) => Number(v) === 1 ? 'BLOOM PROXY' : 'NO BLOOM PROXY';
const cell = { padding: '9px 11px', borderBottom: '1px solid #e6ece8', textAlign: 'left', verticalAlign: 'top' };

export default function HistoricalBacktestPanel() {
  const [report, setReport] = useState(null);
  const [station, setStation] = useState('17625');
  const [error, setError] = useState('');
  useEffect(() => {
    fetch('/historical_backtest_2021.json')
      .then(async r => {
        if (!r.ok) throw new Error('Historical report not installed. Run python backend/historical_backtest.py.');
        return await r.json();
      })
      .then(setReport)
      .catch(e => setError(e.message));
  }, []);
  const stations = Object.keys(report?.eight_month_by_station || {}).sort();
  const selectedStation = stations.includes(station) ? station : stations[0];
  const rows = report?.eight_month_by_station?.[selectedStation] || [];
  const hits = rows.filter(row => row.correct).length;
  return (
    <section style={{ background:'#fff', border:'1px solid #d8e3da', borderRadius:12,
                      padding:20, margin:'14px 0 20px' }}>
      <h2 style={{ marginTop:0 }}>8-Month Historical Verification</h2>
      <p style={{ fontSize:13, color:'#895500' }}>
        <b>REAL OKEECHOBEE HISTORICAL DATA, NOT LAGUNA SATELLITE-FUSION VALIDATION.</b>
        {' '}Separate XGBoost baseline uses monthly in-situ temperature, pH, DO,
        previous-month readings and their changes to predict next-month bloom-proxy occurrence.
        The label is based on next-month maximum observed chlorophyll-a ≥ 40 µg/L;
        it does not establish HAB toxins or confirmed harmful blooms.
      </p>
      {error && <p style={{ color:'#aa1822' }}>Error: {error}</p>}
      {!report && !error && <p>Loading reproducible historical backtest...</p>}
      {report && <>
        <div style={{ display:'flex', flexWrap:'wrap', gap:18, padding:'12px 0' }}>
          <div><b>{report.metrics.correct}/{report.metrics.total}</b><div style={{ fontSize:12 }}>Correct overall</div></div>
          <div><b>{pct(report.metrics.accuracy)}</b><div style={{ fontSize:12 }}>Model accuracy</div></div>
          <div><b>{pct(report.metrics.recall)}</b><div style={{ fontSize:12 }}>Positive recall</div></div>
          <div><b>{pct(report.always_no_bloom_baseline.accuracy)}</b><div style={{ fontSize:12 }}>Always NO_BLOOM baseline</div></div>
        </div>
        <p style={{ fontSize:12, color:'#895500' }}>
          Training: {report.training_examples} monthly pairs ending by 2020;
          unseen evaluation: {report.test_examples} monthly pairs in 2021.
          The model is <b>below the always-negative accuracy baseline</b> and needs improvement.
          Positive events in held-out data: {report.test_positives}.
        </p>
        <div style={{ display:'flex', alignItems:'center', gap:12, flexWrap:'wrap', marginTop:12 }}>
          <label htmlFor="historical-station"><b>Monitoring station</b></label>
          <select id="historical-station" value={selectedStation || ''}
            onChange={e => setStation(e.target.value)}
            style={{ padding:9, border:'1px solid #ccd8d0', borderRadius:8 }}>
            {stations.map(id => <option value={id} key={id}>{id}</option>)}
          </select>
          <span style={{ fontSize:13 }}>
            <b>{hits}/{rows.length} HIT</b> for this eight-month station view
          </span>
        </div>
        <div style={{ overflowX:'auto', marginTop:12 }}>
          <table style={{ width:'100%', borderCollapse:'collapse', fontSize:13 }}>
            <thead><tr>
              {['Input month','Forecast month','P(bloom)','Model predicts','Observed next month','Maximum Chl-a (µg/L)','Verdict'].map(k =>
                <th key={k} style={{ ...cell, background:'#f4f7f5' }}>{k}</th>)}
            </tr></thead>
            <tbody>{rows.map(r => <tr key={r.target_month + r.station_id}>
              <td style={cell}>{r.input_month}</td>
              <td style={cell}><b>{r.target_month}</b></td>
              <td style={cell}>{pct(r.probability)}</td>
              <td style={cell}>{yName(r.predicted)}</td>
              <td style={cell}>{yName(r.actual)}</td>
              <td style={cell}>{Number(r.actual_next_month_chlorophyll_max_ug_l).toFixed(2)}</td>
              <td style={{...cell, fontWeight:700, color:r.correct ? '#19704b' : '#b42318'}}>
                {r.correct ? 'HIT' : 'MISS'}
              </td>
            </tr>)}</tbody>
          </table>
        </div>
        <p style={{ fontSize:12, color:'#647069', marginBottom:0 }}>
          Preselected chronological test data; no month was selected for whether its prediction was right.
          Source: user-provided 2019–2021 Water Atlas-derived Okeechobee measurements.
          This backtest excludes satellite features because matching historical satellite values were unavailable.
          It is separate from the existing five-input XGBoost fusion demo.
        </p>
      </>}
    </section>
  );
}
