import { useEffect, useState } from "react";
import { collection, limit, orderBy, query, Timestamp, where } from "firebase/firestore";
import { onSnapshot } from "../demoSnapshot.js";
import { db } from "../firebase";
import "./SensorData.css";

const PAGE_SIZE = 100;

const columns = [
    { key: "date", label: "Date" },
    { key: "time", label: "Time (PHT)" },
    { key: "waterTemperature", label: "Water Temperature (°C)" },
    { key: "ph", label: "pH" },
    { key: "dissolvedOxygen", label: "Dissolved Oxygen (mg/L)" },
    { key: "airTemperature", label: "Air Temperature (°C)" },
    { key: "humidity", label: "Humidity (%)" },
    { key: "pressure", label: "Pressure (hPa)" },
];

const dateFormatter = new Intl.DateTimeFormat("en-PH", {
    timeZone: "Asia/Manila",
    year: "numeric",
    month: "short",
    day: "numeric",
});

const timeFormatter = new Intl.DateTimeFormat("en-PH", {
    timeZone: "Asia/Manila",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
});

function getDayStart(dateString) {
    return new Date(`${dateString}T00:00:00+08:00`);
}

function formatValue(reading, key) {
    if (key === "date" || key === "time") {
        return reading[key];
    }

    return Number.isFinite(reading[key]) ? reading[key] : "—";
}

export default function SensorData() {
    const [startDate, setStartDate] = useState("");
    const [endDate, setEndDate] = useState("");
    const [recordLimit, setRecordLimit] = useState(PAGE_SIZE);

    const [result, setResult] = useState({
        key: "",
        readings: [],
        canLoadMore: false,
        error: "",
    });

    const invalidRange = Boolean(
        startDate && endDate && startDate > endDate
    );

    const requestKey = `${startDate}|${endDate}|${recordLimit}`;

    const loading = !invalidRange && result.key !== requestKey;
    const error = !loading && !invalidRange ? result.error : "";
    const readings =
        !loading && !invalidRange && !error ? result.readings : [];

    useEffect(() => {
        if (invalidRange) {
            return;
        }

        const constraints = [];

        if (startDate) {
            constraints.push(
                where(
                    "measuredAt",
                    ">=",
                    Timestamp.fromDate(getDayStart(startDate))
                )
            );
        }

        if (endDate) {
            // Include the entire selected end date in Philippine time.
            const nextDay = new Date(
                getDayStart(endDate).getTime() + 24 * 60 * 60 * 1000
            );

            constraints.push(
                where("measuredAt", "<", Timestamp.fromDate(nextDay))
            );
        }

        constraints.push(
            orderBy("measuredAt", "desc"),
            limit(recordLimit)
        );

        const readingsQuery = query(
            collection(db, "sensor_readings"),
            ...constraints
        );

        const unsubscribe = onSnapshot(
            readingsQuery,
            (snapshot) => {
                const records = snapshot.docs.flatMap((document) => {
                    const data = document.data();

                    if (typeof data.measuredAt?.toDate !== "function") {
                        return [];
                    }

                    const measuredAt = data.measuredAt.toDate();

                    return [
                        {
                            ...data,
                            id: document.id,
                            date: dateFormatter.format(measuredAt),
                            time: timeFormatter.format(measuredAt),
                        },
                    ];
                });

                setResult({
                    key: requestKey,
                    readings: records,
                    canLoadMore: snapshot.size === recordLimit,
                    error: "",
                });
            },
            (snapshotError) => {
                console.error("Historical readings listener:", snapshotError);

                setResult({
                    key: requestKey,
                    readings: [],
                    canLoadMore: false,
                    error: "Unable to load sensor readings. Please try again later.",
                });
            }
        );

        return unsubscribe;
    }, [
        startDate,
        endDate,
        recordLimit,
        invalidRange,
        requestKey,
    ]);

    function changeStartDate(value) {
        setStartDate(value);
        setRecordLimit(PAGE_SIZE);
    }

    function changeEndDate(value) {
        setEndDate(value);
        setRecordLimit(PAGE_SIZE);
    }

    function clearFilters() {
        setStartDate("");
        setEndDate("");
        setRecordLimit(PAGE_SIZE);
    }

    const emptyMessage = invalidRange
        ? "Correct the date range to view records."
        : loading
            ? "Loading sensor readings…"
            : error
                ? "Sensor readings are unavailable."
                : startDate || endDate
                    ? "No readings available for the selected dates."
                    : "No sensor readings available. Waiting for device uploads.";

    return (
        <section className="sensor-data-card">
            <h2>Historical Sensor Readings</h2>

            <p className="sensor-description">
                Stored sensor measurements, displayed newest first.
                All dates and times represent Philippine time.
            </p>

            <div className="sensor-filters">
                <label>
                    From
                    <input
                        type="date"
                        value={startDate}
                        onChange={(event) => changeStartDate(event.target.value)}
                    />
                </label>

                <label>
                    To
                    <input
                        type="date"
                        value={endDate}
                        onChange={(event) => changeEndDate(event.target.value)}
                    />
                </label>

                <button type="button" onClick={clearFilters}>
                    Clear Filters
                </button>
            </div>

            {invalidRange && (
                <p className="filter-error" role="alert">
                    The start date must be on or before the end date.
                </p>
            )}

            {error && (
                <p className="filter-error" role="alert">
                    {error}
                </p>
            )}

            <p className="record-count" role="status">
                {invalidRange
                    ? "Select a valid date range."
                    : loading
                        ? "Loading records…"
                        : error
                            ? "Records could not be loaded."
                            : `${readings.length} record(s) shown`}
            </p>

            <div
                className="sensor-table-wrapper"
                role="region"
                aria-label="Historical sensor readings"
                aria-busy={loading}
                tabIndex={0}
            >
                <table className="sensor-table">
                    <thead>
                        <tr>
                            {columns.map((column) => (
                                <th key={column.key} scope="col">
                                    {column.label}
                                </th>
                            ))}
                        </tr>
                    </thead>

                    <tbody>
                        {readings.map((reading) => (
                            <tr key={reading.id}>
                                {columns.map((column) => (
                                    <td key={column.key}>
                                        {formatValue(reading, column.key)}
                                    </td>
                                ))}
                            </tr>
                        ))}

                        {readings.length === 0 && (
                            <tr>
                                <td colSpan={columns.length}>
                                    {emptyMessage}
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            {!loading && !error && !invalidRange && result.canLoadMore && (
                <div className="sensor-filters">
                    <button
                        type="button"
                        onClick={() =>
                            setRecordLimit((current) => current + PAGE_SIZE)
                        }
                    >
                        Load more
                    </button>
                </div>
            )}
        </section>
    );
}