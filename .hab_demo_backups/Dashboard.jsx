import { useEffect, useState } from "react";
import {
    collection,
    limit,
    onSnapshot,
    orderBy,
    query,
} from "firebase/firestore";
import { db } from "../firebase";
import "./Dashboard.css";
import DeviceMap from "../components/DeviceMap";
import SensorTrend from "../components/SensorTrend";
import ForecastChart from "../components/ForecastChart";

function formatMeasurement(value, unit = "") {
    return Number.isFinite(value)
        ? `${value}${unit ? ` ${unit}` : ""}`
        : "—";
}

const dateFormatter = new Intl.DateTimeFormat("en-PH", {
    timeZone: "Asia/Manila",
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
});

export default function Dashboard() {
    const [readings, setReadings] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [forecastState, setForecastState] = useState({
        data: null,
        loading: true,
        error: "",
    });

    const [satelliteState, setSatelliteState] = useState({
        data: null,
        loading: true,
        error: "",
    });

    useEffect(() => {
        const readingsQuery = query(
            collection(db, "sensor_readings"),
            orderBy("measuredAt", "desc"),
            limit(48)
        );

        const unsubscribe = onSnapshot(
            readingsQuery,
            (snapshot) => {
                const records = snapshot.docs
                    .map((document) => ({
                        ...document.data(),
                        id: document.id,
                    }))
                    .filter(
                        (record) =>
                            typeof record.measuredAt?.toDate === "function"
                    );

                setReadings(records);
                setError("");
                setLoading(false);
            },
            (snapshotError) => {
                console.error("Sensor readings listener:", snapshotError);
                setReadings([]);
                setError("Unable to load sensor readings. Please try again later.");
                setLoading(false);
            }
        );

        return unsubscribe;
    }, []);

    useEffect(() => {
        function listenToLatest(collectionName, timestampField, setState) {
            const latestQuery = query(
                collection(db, collectionName),
                orderBy(timestampField, "desc"),
                limit(1)
            );

            return onSnapshot(
                latestQuery,
                (snapshot) => {
                    setState({
                        data: snapshot.empty ? null : snapshot.docs[0].data(),
                        loading: false,
                        error: "",
                    });
                },
                (snapshotError) => {
                    console.error(`${collectionName} listener:`, snapshotError);

                    setState({
                        data: null,
                        loading: false,
                        error: "Unable to load data. Please try again later.",
                    });
                }
            );
        }

        const unsubscribeForecast = listenToLatest(
            "forecasts",
            "generatedAt",
            setForecastState
        );

        const unsubscribeSatellite = listenToLatest(
            "satellite_observations",
            "acquiredAt",
            setSatelliteState
        );

        return () => {
            unsubscribeForecast();
            unsubscribeSatellite();
        };
    }, []);

    const latest = readings[0];

    // Reverse the newest-first query results for chronological chart display.
    const history = [...readings].reverse();

    const labels = history.map((reading) =>
        dateFormatter.format(reading.measuredAt.toDate())
    );

    const trendMessage = loading
        ? "Loading sensor readings…"
        : error
            ? "Sensor readings are unavailable."
            : "No data available.";

    const forecast = forecastState.data;
    const satellite = satelliteState.data;

    const validProbability =
        Number.isFinite(forecast?.probability) &&
        forecast.probability >= 0 &&
        forecast.probability <= 100;

    return (
        <>
            <p className="demo-notice" role="status">
                {loading
                    ? "Loading sensor readings…"
                    : error
                        ? "Sensor data could not be loaded."
                        : latest
                            ? `Latest measurement: ${dateFormatter.format(
                                latest.measuredAt.toDate()
                            )} (PHT)`
                            : "No sensor data available. Waiting for device uploads."}
            </p>

            {error && <p role="alert">{error}</p>}

            <div className="dashboard-grid">
                <section className="dashboard-card location-card">
                    <h2>Device Location</h2>

                    <DeviceMap
                        latitude={latest?.latitude}
                        longitude={latest?.longitude}
                        emptyMessage={
                            loading
                                ? "Loading device location…"
                                : error
                                    ? "Device location is unavailable."
                                    : "No GPS coordinates available."
                        }
                    />
                </section>

                <section className="dashboard-card forecast-card">
                    <h2>Next-Month Algal Bloom Forecast</h2>

                    {forecastState.loading ? (
                        <p role="status">Loading forecast…</p>
                    ) : forecastState.error ? (
                        <p role="alert">{forecastState.error}</p>
                    ) : !forecast ? (
                        <p>No forecast available.</p>
                    ) : !validProbability ? (
                        <p>The saved forecast has no valid probability.</p>
                    ) : (
                        <>
                            <ForecastChart probability={forecast.probability} />

                            <p>
                                {typeof forecast.targetMonth === "string" &&
                                    forecast.targetMonth.trim()
                                    ? forecast.targetMonth
                                    : "Target month unavailable"}
                            </p>

                            <small>Estimated probability of bloom occurrence</small>
                        </>
                    )}
                </section>

                <div className="measurement-stack">
                    <section className="dashboard-card measurement-card">
                        <h2>Water Temperature</h2>
                        <p>{formatMeasurement(latest?.waterTemperature, "°C")}</p>
                    </section>

                    <section className="dashboard-card measurement-card">
                        <h2>pH Level</h2>
                        <p>{formatMeasurement(latest?.ph)}</p>
                    </section>

                    <section className="dashboard-card measurement-card">
                        <h2>Dissolved Oxygen</h2>
                        <p>{formatMeasurement(latest?.dissolvedOxygen, "mg/L")}</p>
                    </section>
                </div>

                <section className="dashboard-card atmosphere-card observation-panel">
                    <img
                        src="/icons/weather.png"
                        alt=""
                        className="observation-illustration"
                    />

                    <div className="observation-content">
                        <h2>Local Atmospheric Conditions</h2>

                        <dl className="observation-list">
                            <div>
                                <dt>Air Temperature:</dt>
                                <dd>
                                    {formatMeasurement(latest?.airTemperature, "°C")}
                                </dd>
                            </div>

                            <div>
                                <dt>Humidity:</dt>
                                <dd>{formatMeasurement(latest?.humidity, "%")}</dd>
                            </div>

                            <div>
                                <dt>Pressure:</dt>
                                <dd>{formatMeasurement(latest?.pressure, "hPa")}</dd>
                            </div>
                        </dl>
                    </div>
                </section>

                <section className="dashboard-card satellite-card observation-panel">
                    <img
                        src="/icons/satellite-observation.png"
                        alt=""
                        className="observation-illustration"
                    />

                    <div className="observation-content">
                        <h2>Latest Satellite Observation</h2>

                        {satelliteState.loading ? (
                            <p role="status">Loading satellite observation…</p>
                        ) : satelliteState.error ? (
                            <p role="alert">{satelliteState.error}</p>
                        ) : !satellite ? (
                            <p>No satellite observation available.</p>
                        ) : (
                            <dl className="observation-list">
                                <div>
                                    <dt>Acquisition:</dt>
                                    <dd>
                                        {typeof satellite.acquiredAt?.toDate === "function"
                                            ? satellite.acquiredAt.toDate().toLocaleDateString(
                                                "en-PH",
                                                {
                                                    timeZone: "Asia/Manila",
                                                    year: "numeric",
                                                    month: "short",
                                                    day: "numeric",
                                                }
                                            )
                                            : "—"}
                                    </dd>
                                </div>

                                <div>
                                    <dt>Estimated Chlorophyll-a:</dt>
                                    <dd>
                                        {formatMeasurement(satellite.chlorophyll, "µg/L")}
                                    </dd>
                                </div>

                                <div>
                                    <dt>Valid Coverage After Cloud Masking:</dt>
                                    <dd>{formatMeasurement(satellite.coverage, "%")}</dd>
                                </div>
                            </dl>
                        )}
                    </div>
                </section>

                <div className="trend-grid">
                    <SensorTrend
                        title="Water Temperature Trend"
                        labels={labels}
                        values={history.map((reading) => reading.waterTemperature)}
                        color="#ff765e"
                        fillColor="rgba(255, 118, 94, 0.15)"
                        unit="°C"
                        emptyMessage={trendMessage}
                    />

                    <SensorTrend
                        title="pH Level Trend"
                        labels={labels}
                        values={history.map((reading) => reading.ph)}
                        color="#39b8ed"
                        fillColor="rgba(57, 184, 237, 0.15)"
                        emptyMessage={trendMessage}
                    />

                    <SensorTrend
                        title="Dissolved Oxygen Trend"
                        labels={labels}
                        values={history.map((reading) => reading.dissolvedOxygen)}
                        color="#dc65e8"
                        fillColor="rgba(220, 101, 232, 0.15)"
                        unit="mg/L"
                        emptyMessage={trendMessage}
                    />
                </div>
            </div>
        </>
    );
}