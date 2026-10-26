import { useEffect, useState } from "react";
import { collection, limit, orderBy, query } from "firebase/firestore";
import { onSnapshot } from "../demoSnapshot.js";
import { db } from "../firebase";
import "./SystemStatus.css";

const sensors = [
    {
        name: "Water Temperature",
        module: "DS18B20",
        fields: ["waterTemperature"],
    },
    {
        name: "pH",
        module: "DFRobot pH Sensor",
        fields: ["ph"],
    },
    {
        name: "Dissolved Oxygen",
        module: "DFRobot DO Sensor",
        fields: ["dissolvedOxygen"],
    },
    {
        name: "Air Temperature, Humidity, and Pressure",
        module: "BME280",
        fields: ["airTemperature", "humidity", "pressure"],
    },
];

function formatTimestamp(timestamp) {
    if (typeof timestamp?.toDate !== "function") {
        return null;
    }

    return timestamp.toDate().toLocaleString("en-PH", {
        timeZone: "Asia/Manila",
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
    });
}

function getAvailability(reading, fields) {
    if (!reading) {
        return "No data received";
    }

    const availableCount = fields.filter((field) =>
        Number.isFinite(reading[field])
    ).length;

    if (availableCount === fields.length) {
        return "Available";
    }

    return availableCount > 0 ? "Partially available" : "Unavailable";
}

export default function SystemStatus() {
    const [latest, setLatest] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        const latestReadingQuery = query(
            collection(db, "sensor_readings"),
            orderBy("measuredAt", "desc"),
            limit(1)
        );

        const unsubscribe = onSnapshot(
            latestReadingQuery,
            (snapshot) => {
                setLatest(
                    snapshot.empty ? null : snapshot.docs[0].data()
                );
                setError("");
                setLoading(false);
            },
            (snapshotError) => {
                console.error("System status listener:", snapshotError);
                setLatest(null);
                setError("Unable to load system status. Please try again later.");
                setLoading(false);
            }
        );

        return unsubscribe;
    }, []);

    const measuredAt = formatTimestamp(latest?.measuredAt);

    const hasCoordinates =
        Number.isFinite(latest?.latitude) &&
        Number.isFinite(latest?.longitude) &&
        latest.latitude >= -90 &&
        latest.latitude <= 90 &&
        latest.longitude >= -180 &&
        latest.longitude <= 180;

    const unavailableText = loading
        ? "Loading…"
        : error
            ? "Unavailable"
            : "No data received";

    return (
        <div className="system-status-page">
            <p className="system-status-note" role="status">
                {loading
                    ? "Loading system information…"
                    : error
                        ? "System information could not be loaded."
                        : latest
                            ? "Information below reflects the latest stored measurement."
                            : "No sensor data available. Waiting for device uploads."}
            </p>

            {error && <p role="alert">{error}</p>}

            <div className="system-status-grid">
                <section className="system-status-panel">
                    <h2>Device Connection</h2>

                    <p className="system-status-value">
                        {latest ? "Unknown" : unavailableText}
                    </p>

                    <p className="system-status-note">
                        {latest
                            ? "Stored readings are available. Current device connectivity requires device telemetry."
                            : "Waiting for device transmission information."}
                    </p>
                </section>

                <section className="system-status-panel">
                    <h2>Latest Measurement</h2>

                    <p className="system-status-value">
                        {measuredAt ? `${measuredAt} (PHT)` : "—"}
                    </p>

                    <p className="system-status-note">
                        Time the measurement was taken, as recorded in measuredAt.
                    </p>
                </section>

                <section className="system-status-panel">
                    <h2>GPS Data Availability</h2>

                    <p className="system-status-value">
                        {loading
                            ? "Loading…"
                            : hasCoordinates
                                ? "Coordinates available"
                                : "Unavailable"}
                    </p>

                    <p className="system-status-note">
                        {hasCoordinates
                            ? `Latitude: ${latest.latitude.toFixed(6)}, Longitude: ${latest.longitude.toFixed(6)}`
                            : "No valid coordinates available in the latest measurement."}
                    </p>
                </section>
            </div>

            <section className="system-status-panel">
                <h2>Sensor Data Availability</h2>

                <p className="system-status-note">
                    Availability refers to numeric values in the latest stored
                    measurement. It does not confirm sensor health.
                </p>

                <div
                    className="system-status-table-wrapper"
                    role="region"
                    aria-label="Sensor data availability"
                    tabIndex={0}
                >
                    <table className="system-status-table">
                        <thead>
                            <tr>
                                <th scope="col">Measurement</th>
                                <th scope="col">Sensor</th>
                                <th scope="col">Data Availability</th>
                            </tr>
                        </thead>

                        <tbody>
                            {sensors.map((sensor) => (
                                <tr key={sensor.name}>
                                    <td>{sensor.name}</td>
                                    <td>{sensor.module}</td>
                                    <td>
                                        {loading
                                            ? "Loading…"
                                            : error
                                                ? "Unavailable"
                                                : getAvailability(latest, sensor.fields)}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </section>
        </div>
    );
}