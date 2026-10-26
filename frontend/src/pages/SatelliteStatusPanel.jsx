import { useEffect, useState } from 'react';
import { collection, onSnapshot } from 'firebase/firestore';
import { db } from '../firebase';

const fmt = (v) => v === null || v === undefined ? '—' : String(v);

export default function SatelliteStatusPanel() {
  const [rows, setRows] = useState([]);
  const [error, setError] = useState('');
  useEffect(() => onSnapshot(collection(db, 'satellite_observations'), snap => {
    const docs = snap.docs.map(d => ({ id: d.id, ...d.data() }));
    docs.sort((a,b) => (b.acquisitionDate ?? '').localeCompare(a.acquisitionDate ?? ''));
    setRows(docs);
    setError('');
  }, e => setError(e.message)), []);
  return <section style={{background:'#fff',padding:20,margin:16,borderRadius:12,border:'1px solid #dae3dc'}}>
    <h3>Sentinel-3 OLCI Processing Records</h3>
    <p style={{fontSize:13,color:'#905500'}}>Real Copernicus scenes · Preliminary quality screening · Temporary test point (14.30°N, 121.25°E) · Not validated HAB warnings</p>
    {error ? <p style={{color:'#b42318'}}>Firestore read error: {error}</p> :
      rows.length === 0 ? <p>No processed satellite records in Firestore yet. Run <code>python backend/satellite_sync.py</code>.</p> :
      <div style={{overflowX:'auto'}}><table style={{width:'100%',borderCollapse:'collapse',fontSize:13}}>
        <thead><tr>{['Date','Product','Screening','Cloud %','Valid pixels','Chlorophyll candidate (µg/L)'].map(t => <th key={t} style={{textAlign:'left',padding:10,borderBottom:'1px solid #ddd'}}>{t}</th>)}</tr></thead>
        <tbody>{rows.map(r=><tr key={r.id}>
          {[r.acquisitionDate, r.sourceProductName, r.processingStatus, r.cloudPercentage, r.validPixelCount, r.isQualityCandidate ? r.chlorophyll : null].map((v,i)=><td key={i} style={{padding:10,borderBottom:'1px solid #eee',overflowWrap:'anywhere'}}>{fmt(v)}</td>)}
        </tr>)}</tbody>
      </table></div>}
    <p style={{fontSize:12}}>Rejected scenes have no numerical chlorophyll measurement. Passing quality checks is not the same as scientifically validating chlorophyll or predicting harmfulness.</p>
  </section>;
}

