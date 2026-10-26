#!/usr/bin/env bash
set -euo pipefail
cd /workspaces/HAB_Risk_Forecasting
mkdir -p backend frontend/src/pages
cat > backend/satellite_sync.py <<'SATELLITE_PY_EOF'
"""Discover actual Sentinel-3 OLCI scenes, run existing quality screening, and publish truthful results to Firestore.
Use from repo root: python backend/satellite_sync.py
"""
import os
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import boto3
import requests
import firebase_admin
from firebase_admin import credentials, firestore
from botocore.config import Config

sys.path.insert(0, str(Path(__file__).resolve().parent / "models"))
import copernicus_laguna_validation as processor

ROOT = Path(__file__).resolve().parent.parent
LAT, LON = 14.30, 121.25  # TEMPORARY research test point, not an LLDA station
START, END = "2024-01-01T00:00:00.000Z", "2024-02-01T00:00:00.000Z"
MAX_SCENES = 5


def find_scenes():
    point = f"SRID=4326;POINT({LON} {LAT})"
    filter_expr = (
        "Collection/Name eq 'SENTINEL-3' and "
        "contains(Name,'_OL_2_WFR') and "
        f"ContentDate/Start ge {START} and ContentDate/Start lt {END} and "
        f"OData.CSC.Intersects(area=geography'{point}')"
    )
    response = requests.get(
        "https://catalogue.dataspace.copernicus.eu/odata/v1/Products",
        params={"$filter": filter_expr, "$orderby": "ContentDate/Start asc", "$top": 100},
        timeout=75,
    )
    response.raise_for_status()
    products = response.json().get("value", [])
    scenes = [s for s in products if s.get("S3Path") and s.get("Id") and s.get("Name")]
    print(f"Copernicus catalogue: {len(scenes)} accessible OLCI products", flush=True)
    return scenes


def init_db():
    info = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT_JSON"])
    if info.get("type") != "service_account":
        raise RuntimeError("Firebase Codespaces secret is not a service-account JSON")
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(info))
    return firestore.client()


def record_for(scene, result):
    acquired = result.get("acquiredAt") or scene["ContentDate"]["Start"]
    record = {
        "source": "Sentinel-3 OLCI Level-2 Water",
        "sourceProductId": str(scene["Id"]),
        "sourceProductName": scene["Name"],
        "acquiredAt": datetime.fromisoformat(acquired.replace("Z", "+00:00")) if acquired else None,
        "acquiredAtISO": acquired,
        "acquisitionDate": acquired[:10] if acquired else None,
        "processingStatus": result["status"],
        "status": result["status"],
        "observationStatus": "PRELIMINARY_QUALITY_SCREENING_NOT_VALIDATED",
        "locationStatus": "TEMPORARY_TEST_POINT_NOT_LLDA_STATION",
        "monitoringLatitude": LAT, "monitoringLongitude": LON,
        "cloudPercentage": result.get("cloud_pct"),
        "validPixelCount": result.get("valid_pixels", 0),
        "nearbyPixelCount": result.get("nearby_pixels"),
        "qualityEligiblePixelCount": result.get("quality_eligible_pixels"),
        "coverage": result.get("coverage"),
        "chlorophyll": result.get("chlorophyll") if result["status"] == "CANDIDATE" else None,
        "chlorophyllUnits": result.get("chl_units") if result["status"] == "CANDIDATE" else None,
        "qualityFailures": result.get("top_failures", []),
        "processingError": result.get("reason"),
        "processedAt": firestore.SERVER_TIMESTAMP,
        "isQualityCandidate": result["status"] == "CANDIDATE",
    }
    return record


def main():
    required = ["CDSE_S3_ACCESS_KEY", "CDSE_S3_SECRET_KEY", "FIREBASE_SERVICE_ACCOUNT_JSON"]
    missing = [s for s in required if not os.environ.get(s)]
    if missing:
        raise RuntimeError("Missing Codespaces secrets: " + ", ".join(missing))
    db = init_db()
    scenes = find_scenes()
    if not scenes:
        print("No OLCI products in requested area/month. No records written.")
        return
    s3 = boto3.client(
        "s3", endpoint_url="https://eodata.dataspace.copernicus.eu",
        aws_access_key_id=os.environ["CDSE_S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["CDSE_S3_SECRET_KEY"],
        region_name="default",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    results = []
    for i, scene in enumerate(scenes[:MAX_SCENES], 1):
        try:
            result = processor.evaluate_scene(s3, scene, LAT, LON, 1.0, 5.0, 5)
        except Exception as exc:
            result = {"status": "ERROR", "reason": f"{type(exc).__name__}: {str(exc)[:120]}",
                      "acquiredAt": scene.get("ContentDate", {}).get("Start")}
        record = record_for(scene, result)
        db.collection("satellite_observations").document(str(scene["Id"])).set(record)
        results.append(record)
        print(f"{i}/{min(len(scenes), MAX_SCENES)} {record['acquisitionDate']} "
              f"status={result['status']} valid={record['validPixelCount']} "
              f"chlorophyll={record['chlorophyll']}", flush=True)
    print(f"DONE: Published {len(results)} genuine screening records to Firestore.")
    print("Reminder: Invalid scenes have chlorophyll=null, not fabricated numbers.")


if __name__ == "__main__":
    main()

SATELLITE_PY_EOF
cat > frontend/src/pages/SatelliteStatusPanel.jsx <<'SATELLITE_JS_EOF'
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

SATELLITE_JS_EOF
python - <<'INSTALL_PY_EOF'
from pathlib import Path
import shutil
folder=Path('frontend/src/pages')
page=folder/'SatelliteData.jsx'
orig=folder/'SatelliteDataOriginal.jsx'
if not orig.exists():
    shutil.copy2(page, orig)
shutil.copy2(page, folder/'SatelliteData.before_real_sync.bak')
page.write_text("import React from 'react';\nimport Original from './SatelliteDataOriginal.jsx';\nimport SatelliteStatusPanel from './SatelliteStatusPanel.jsx';\nexport default function SatelliteData() {\n  return <><SatelliteStatusPanel/><Original/></>;\n}\n")
print('Installed genuine satellite pipeline + Firestore-connected panel in existing React page.')
INSTALL_PY_EOF
python -m pip install -q requests boto3 netCDF4 numpy firebase-admin
python -m py_compile backend/satellite_sync.py
printf '\nSATELLITE INSTALL COMPLETE. Run: python backend/satellite_sync.py\n'
