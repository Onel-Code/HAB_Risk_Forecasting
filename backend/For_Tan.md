# ESP32-to-Cloud Integration

The website reads sensor records from Firebase Cloud Firestore.

## Destination

- **Firebase project ID:** `hab-risk-forecasting`
- **Database:** `(default)`
- **Collection:** `sensor_readings`
- **Document path:** `sensor_readings/{readingId}`
- **Firebase Console:** https://console.firebase.google.com/project/hab-risk-forecasting/firestore

The Console link is for managing the database. It is not the ESP32 upload URL.
**The upload API URL and device authentication have not been configured yet.**

## Variables to Save

Create one document per measurement. Use the exact field names below.

| Variable | Firestore type | Unit / purpose |
| --- | --- | --- |
| `deviceId` | String | Stable device identifier, such as `prototype-01` |
| `source` | String | Use `esp32` for actual device uploads |
| `waterTemperature` | Number or null | Water temperature in °C |
| `ph` | Number or null | pH value |
| `dissolvedOxygen` | Number or null | Dissolved oxygen in mg/L |
| `airTemperature` | Number or null | Air temperature in °C |
| `humidity` | Number or null | Relative humidity in % |
| `pressure` | Number or null | Atmospheric pressure in hPa |
| `latitude` | Number or null | Latitude in decimal degrees |
| `longitude` | Number or null | Longitude in decimal degrees |
| `measuredAt` | Timestamp | Actual date and time the measurement was taken |

Store numbers without unit text. Use null for unavailable measurements or GPS
coordinates; do not substitute sample values. Preserve the original measurement
time when uploading buffered records. The website displays timestamps in
Philippine time.

## Upload Connection

**Planned flow:** ESP32 → authenticated upload API → Firestore → website.

The integration teammate must define:

- The upload API URL.
- The device authentication method.
- The accepted request format and upload response.

If time is sent as a date string in the request, convert it to a **Firestore
Timestamp** before saving `measuredAt`. Give each measurement its own document;
retries should not create duplicate records.

Current Firestore rules allow public reading and deny client writes. Authorized
uploading must be implemented before the ESP32 can send data. Do not enable
public writes or put service-account private keys in the firmware or repository.

## Website Connection

- `frontend/src/firebase.js` selects the Firebase project and exports `db`.
- `collection(db, "sensor_readings")` selects the sensor collection.
- `onSnapshot()` receives saved readings and subsequent updates automatically.

No direct ESP32-to-React connection is required. Once an actual record is saved,
check its values in Dashboard, Sensor Data, and System Status. The current website
assumes one prototype and does not filter readings by `deviceId`. Device online
status requires separate telemetry and is not inferred from saved readings.
