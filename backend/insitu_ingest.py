"""Protected endpoint for genuine ESP32/IoT device readings.

To use, configure HAB_DEVICE_INGEST_TOKEN as a server-side Codespaces secret.
This doesn't make a private Codespaces port internet-accessible to an ESP32;
actual field deployment needs a reachable, secured HTTPS service.
"""
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Header, HTTPException
from pydantic import BaseModel, Field
from backend.auto_forecast import get_database

class DeviceReading(BaseModel):
    device_id: str = Field(min_length=2, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')
    observed_at: datetime
    temperature_c: float = Field(ge=0, le=60)
    ph: float = Field(ge=0, le=14)
    dissolved_oxygen_mg_l: float = Field(ge=0, le=30)


def ingest_device_reading(reading: DeviceReading, x_device_token: Optional[str] = Header(default=None)):
    expected = os.getenv('HAB_DEVICE_INGEST_TOKEN', '')
    if not expected:
        raise HTTPException(503, 'Device ingestion disabled; configure HAB_DEVICE_INGEST_TOKEN')
    if not x_device_token or not hmac.compare_digest(expected, x_device_token):
        raise HTTPException(401, 'Invalid device credentials')
    if reading.observed_at.tzinfo is None:
        raise HTTPException(422, 'observed_at must include time-zone offset')
    dt=reading.observed_at.astimezone(timezone.utc)
    if dt > datetime.now(timezone.utc) + timedelta(minutes=10):
        raise HTTPException(422, 'Future observation timestamp')
    month=dt.strftime('%Y-%m')
    safe_id=hashlib.sha256(f'{reading.device_id}:{dt.isoformat()}'.encode('utf-8')).hexdigest()
    db=get_database()
    db.collection('sensor_readings').document(safe_id).set({
        'month':month,
        'deviceId':reading.device_id,
        'timestamp':dt,
        'temperatureC':reading.temperature_c,
        'pH':reading.ph,
        'dissolvedOxygenMgL':reading.dissolved_oxygen_mg_l,
        'sourceType':'DEVICE_REPORTED_UNVERIFIED',
        'isSimulated':False,
        'ingestedAt':datetime.now(timezone.utc),
    })
    return {'accepted':True,'month':month,'reading_id':safe_id,
            'note':'Stored as device-reported, not independently calibrated or verified'}
