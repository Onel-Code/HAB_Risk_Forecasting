import { useEffect, useState } from "react";
import { collection, limit, orderBy, query } from "firebase/firestore";
import { onSnapshot } from "../demoSnapshot.js";
import { db } from "../firebase";
import "./SatelliteData.css";

const PAGE_SIZE = 100;

const dateFormatter = new Intl.DateTimeFormat("en-PH", {
    timeZone: "Asia/Manila",
    year: "numeric",
    month: "short",
    day: "numeric",
});

function formatDate(timestamp) {
    return typeof timestamp?.toDate === "function"
        ? dateFormatter.format(timestamp.toDate())
        : "—";
}

function formatMeasurement(value, unit = "") {
    return Number.isFinite(value) ? `${value}${unit}` : "—";
}

export default function SatelliteData() {
    const [recordLimit, setRecordLimit] = useState(PAGE_SIZE);

    const [result, setResult] = useState({
        limit: 0,
        observations: [],
        canLoadMore: false,
        error: "",
    });

    const loading = result.limit !== recordLimit;
    const error = loading ? "" : result.error;
    const observations = error ? [] : result.observations;
    const latest = observations[0];

    useEffect(() => {
        const observationsQuery = query(
            collection(db, "satellite_observations"),
            orderBy("acquiredAt", "desc"),
            limit(recordLimit)
        );

        const unsubscribe = onSnapshot(
            observationsQuery,
            (snapshot) => {
                const records = snapshot.docs
                    .map((document) => ({
                        ...document.data(),
                        id: document.id,
                    }))
                    .filter(
                        (observation) =>
                            typeof observation.acquiredAt?.toDate === "function"
                    );

                setResult({
                    limit: recordLimit,
                    observations: records,
                    canLoadMore: snapshot.size === recordLimit,
                    error: "",
                });
            },
            (snapshotError) => {
                console.error("Satellite observations listener:", snapshotError);

                setResult({
                    limit: recordLimit,
                    observations: [],
                    canLoadMore: false,
                    error: "Unable to load satellite observations. Please try again later.",
                });
            }
        );

        return unsubscribe;
    }, [recordLimit]);

    return (
        <div className="satellite-page">
            <p className="satellite-note" role="status">
                {loading
                    ? "Loading satellite observations…"
                    : error
                        ? "Satellite observations could not be loaded."
                        : latest
                            ? "Processed satellite observations for the defined monitoring area."
                            : "No satellite observations available. Waiting for processed data."}
            </p>

            {error && <p role="alert">{error}</p>}

            <div className="satellite-summary">
                <section className="satellite-panel">
                    <h2>Latest Acquisition Date</h2>
                    <p className="satellite-value">
                        {formatDate(latest?.acquiredAt)}
                    </p>
                </section>

                <section className="satellite-panel">
                    <h2>Estimated Chlorophyll-a</h2>
                    <p className="satellite-value">
                        {formatMeasurement(latest?.chlorophyll, " µg/L")}
                    </p>
                </section>

                <section className="satellite-panel">
                    <h2>Valid Coverage After Cloud Masking</h2>
                    <p className="satellite-value">
                        {formatMeasurement(latest?.coverage, "%")}
                    </p>
                </section>
            </div>

            <section className="satellite-panel">
                <h2>Satellite Observation History</h2>

                <p className="satellite-note">
                    Numerical observations, displayed newest first.
                    Acquisition dates are shown in Philippine time.
                </p>

                <p className="satellite-note" role="status">
                    {loading
                        ? "Loading records…"
                        : error
                            ? "Records could not be loaded."
                            : `${observations.length} observation(s) shown`}
                </p>

                <div
                    className="satellite-table-wrapper"
                    role="region"
                    aria-label="Satellite observation history"
                    aria-busy={loading}
                    tabIndex={0}
                >
                    <table className="satellite-table">
                        <thead>
                            <tr>
                                <th scope="col">Acquisition Date</th>
                                <th scope="col">Estimated Chlorophyll-a (µg/L)</th>
                                <th scope="col">
                                    Valid Coverage After Cloud Masking (%)
                                </th>
                            </tr>
                        </thead>

                        <tbody>
                            {observations.map((observation) => (
                                <tr key={observation.id}>
                                    <td>{formatDate(observation.acquiredAt)}</td>
                                    <td>
                                        {formatMeasurement(observation.chlorophyll)}
                                    </td>
                                    <td>
                                        {formatMeasurement(observation.coverage)}
                                    </td>
                                </tr>
                            ))}

                            {observations.length === 0 && (
                                <tr>
                                    <td colSpan={3}>
                                        {loading
                                            ? "Loading satellite observations…"
                                            : error
                                                ? "Satellite observations are unavailable."
                                                : "No satellite observations available."}
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>

                {!loading && !error && result.canLoadMore && (
                    <button
                        type="button"
                        onClick={() =>
                            setRecordLimit((current) => current + PAGE_SIZE)
                        }
                    >
                        Load more
                    </button>
                )}
            </section>
        </div>
    );
}