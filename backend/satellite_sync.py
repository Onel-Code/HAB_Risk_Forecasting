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
MAX_SCENES = 29
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
        params={"$filter": filter_expr, "$orderby": "ContentDate/Start desc", "$top": 100},
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
        "cloudMarginPercentage": result.get("cloud_margin_pct"),
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
            result = processor.evaluate_scene(s3, scene, LAT, LON, 5.0, 5.0, 5)
        except Exception as exc:
            result = {"status": "ERROR", "reason": f"{type(exc).__name__}: {str(exc)[:120]}",
                      "acquiredAt": scene.get("ContentDate", {}).get("Start")}

        print("PIXEL DIAGNOSTICS:", {
            "date": result.get("acquiredAt"),
            "status": result.get("status"),
            "nearby": result.get("nearby_pixels"),
            "water": result.get("water_pixels"),
            "cloud_pct": result.get("cloud_pct"),
            "cloud_flags": result.get("cloud_flag_counts"),
            "invalid": result.get("invalid_flag_pixels"),
            "raw_numeric": result.get("raw_chl_numeric_pixels"),
            "raw_water_numeric": result.get("raw_water_numeric_pixels"),
            "quality_passed_numeric": result.get(
                "quality_passed_numeric_pixels"
            ),
            "diagnostic_error": result.get("chl_diagnostic_error"),
        }, flush=True)
        record = record_for(scene, result)
        db.collection("satellite_observations").document(str(scene["Id"])).set(record)
        results.append(record)
        print(f"{i}/{min(len(scenes), MAX_SCENES)} {record['acquisitionDate']} "
              f"status={result['status']} valid={record['validPixelCount']} "
              f"chlorophyll={record['chlorophyll']}", flush=True)

    from statistics import median

    accepted = [
        r for r in results
        if r.get("isQualityCandidate")
        and r.get("chlorophyll") is not None
    ]

    if accepted:
        monthly_chl = round(
            median(float(r["chlorophyll"]) for r in accepted),
            4
        )

        db.collection("satellite_monthly").document(
            "2024-01_laguna_test_point"
        ).set({
            "month": "2024-01",
            "satellite_chl_monthly_median": monthly_chl,
            "units": "ug/L",
            "validAcquisitions": len(accepted),
            "source": "Sentinel-3 OLCI CHL_NN",
            "monitoringLatitude": LAT,
            "monitoringLongitude": LON,
            "radiusKm": 5.0,
            "cloudLimitPercent": 5.0,
            "status": "PRELIMINARY_NOT_LLDA_VALIDATED",
            "sourceProductIds": [
                r["sourceProductId"] for r in accepted
            ]
        })

        print(
            "MONTHLY SATELLITE FEATURE:",
            monthly_chl, "ug/L",
            "| Valid scenes:", len(accepted)
        )
    else:
        print(
            "No scenes passed the 5% cloud requirement.",
            "No monthly chlorophyll value created."
        )

    print(f"DONE: Published {len(results)} genuine screening records to Firestore.")
    print("Reminder: Invalid scenes have chlorophyll=null, not fabricated numbers.")


if __name__ == "__main__":
    main()

