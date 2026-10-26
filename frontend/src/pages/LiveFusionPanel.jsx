import React, { useEffect, useState } from 'react';
import { collection, onSnapshot, query, where } from 'firebase/firestore';
import { db } from '../firebase';

const fields = [
  ['temperatureC','Water temperature','°C'],
  ['pH','pH',''],
  ['dissolvedOxygenMgL','Dissolved oxygen','mg/L'],
];
function previousMonth(month) {
  if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(month)) return '';
  const [y,m] = month.split('-').map(Number);
  return m === 1 ? `${y-1}-12` : `${y}-${String(m-1).padStart(2,'0')}`;
}
function median(xs) {
  const vals = xs.filter(Number.isFinite).sort((a,b)=>a-b);
  if (!vals.length) return null;
  const n=Math.floor(vals.length/2);
  return vals.length%2 ? vals[n] : (vals[n-1]+vals[n])/2;
}
function medians(readings) {
  const fromDevice=readings.filter(r =>
    r.sourceType === 'DEVICE_REPORTED_UNVERIFIED' && r.isSimulated !== true);
  const obj={ count:fromDevice.length };
  for (const [key] of fields) obj[key]=median(fromDevice.map(r=>r[key] == null ? NaN : Number(r[key])));
  return obj;
}
const fmt=v=>Number.isFinite(v)?Number(v).toFixed(2):'Missing';

export default function LiveFusionPanel() {
  const [month,setMonth]=useState('2024-01');
  const [current,setCurrent]=useState([]);
  const [previous,setPrevious]=useState([]);
  const [satellites,setSatellites]=useState([]);
  const [error,setError]=useState('');
  useEffect(()=>{
    setCurrent([]);setPrevious([]);setError('');
    const unsubs=[];
    const watch=(q,setter)=>onSnapshot(q,s=>setter(s.docs.map(d=>d.data())),e=>setError(e.message));
    unsubs.push(watch(query(collection(db,'sensor_readings'),where('month','==',month)),setCurrent));
    unsubs.push(watch(query(collection(db,'sensor_readings'),where('month','==',previousMonth(month))),setPrevious));
    unsubs.push(watch(query(collection(db,'satellite_monthly'),where('month','==',month)),setSatellites));
    return ()=>unsubs.forEach(fn=>fn());
  },[month]);
  const curr=medians(current), prev=medians(previous);
  const satellite=satellites.find(s=>s.satellite_chl_monthly_median!=null &&
    s.validAcquisitions>0);
  const ready=curr.count>0 && prev.count>0 && Boolean(satellite);
  return <section style={{background:'#fff',border:'1px solid #d8e3da',borderRadius:12,
                           padding:20,margin:'14px 0 20px'}}>
    <h2 style={{marginTop:0}}>Live Device + Satellite Fusion Preview</h2>
    <p style={{fontSize:13}}>
      Automatically reads <b>genuine device-reported</b> Firestore observations,
      calculates monthly medians and changes from the previous month,
      and matches <b>the same calendar month</b> with Sentinel-3 data.
      Simulated replay readings are excluded. This prepares model inputs but does not
      claim a validated Laguna forecast.
    </p>
    <label>Observation month{' '}
      <input type="month" value={month} onChange={e=>setMonth(e.target.value)} />
    </label>
    {error && <p style={{color:'#b42318'}}>Firestore read error: {error}</p>}
    <p>Real device readings: <b>{curr.count}</b> this month; <b>{prev.count}</b> previous month.
      {' '}Satellite matching acquisition: <b>{satellite ? 'Present' : 'Missing'}</b></p>
    <div style={{overflowX:'auto'}}><table style={{width:'100%',fontSize:13,borderCollapse:'collapse'}}>
      <thead><tr>{['Input','Current median','Previous median','Change'].map(h=><th key={h}
        style={{padding:10,borderBottom:'1px solid #ddd',textAlign:'left'}}>{h}</th>)}</tr></thead>
      <tbody>{fields.map(([key,label,unit]) => <tr key={key}>
        <td style={{padding:10}}>{label} {unit}</td>
        <td style={{padding:10}}>{fmt(curr[key])}</td>
        <td style={{padding:10}}>{fmt(prev[key])}</td>
        <td style={{padding:10}}>{fmt(Number.isFinite(curr[key]) && Number.isFinite(prev[key])
          ? curr[key]-prev[key]:null)}</td>
      </tr>)}</tbody>
    </table></div>
    <p>Same-month satellite CHL_NN candidate: <b>{satellite
      ? `${fmt(Number(satellite.satellite_chl_monthly_median))} µg/L` : 'No qualifying monthly record'}</b></p>
    <p style={{fontSize:13,color:ready?'#176c49':'#895500'}}>
      <b>{ready ? 'Inputs fused for technical preview.' : 'Waiting for matching device history and/or satellite data.'}</b>
      {' '}No automatic next-month Laguna prediction until a trend+satellite model is trained and validated.
      The existing experimental Lake Okeechobee five-feature model does not consume these trend fields.
    </p>
  </section>;
}
