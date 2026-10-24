import { useEffect, useState } from "react";
import {
    collection,
    limit,
    onSnapshot,
    orderBy,
    query,
} from "firebase/firestore";
import { db } from "../firebase";
import ForecastChart from "../components/ForecastChart";
import "./Forecast.css";

function formatText(value) {
    return typeof value === "string" && value.trim()
        ? value
        : "—";
}

function formatGenerationDate(timestamp) {
    if (typeof timestamp?.toDate !== "function") {
        return "—";
    }

    return `${timestamp.toDate().toLocaleString("en-PH", {
        timeZone: "Asia/Manila",
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    })} (PHT)`;
}

function formatCoordinates(latitude, longitude) {
    const valid =
        Number.isFinite(latitude) &&
        Number.isFinite(longitude) &&
        latitude >= -90 &&
        latitude <= 90 &&
        longitude >= -180 &&
        longitude <= 180;

    return valid
        ? `${latitude.toFixed(6)}, ${longitude.toFixed(6)}`
        : "—";
}

export default function Forecast() {
    const [forecast, setForecast] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        const forecastQuery = query(
            collection(db, "forecasts"),
            orderBy("generatedAt", "desc"),
            limit(1)
        );

        const unsubscribe = onSnapshot(
            forecastQuery,
            (snapshot) => {
                setForecast(
                    snapshot.empty ? null : snapshot.docs[0].data()
                );
                setError("");
                setLoading(false);
            },
            (snapshotError) => {
                console.error("Forecast listener:", snapshotError);

                setForecast(null);
                setError("Unable to load the forecast. Please try again later.");
                setLoading(false);
            }
        );

        return unsubscribe;
    }, []);

    const validProbability =
        Number.isFinite(forecast?.probability) &&
        forecast.probability >= 0 &&
        forecast.probability <= 100;

    return (
        <div className="forecast-page">
            <p className="forecast-preview-note" role="status">
                {loading
                    ? "Loading forecast results…"
                    : error
                        ? "Forecast results could not be loaded."
                        : forecast
                            ? "Showing the most recently generated forecast."
                            : "No forecast available. Waiting for a saved model result."}
            </p>

            {error && <p role="alert">{error}</p>}

            <div className="forecast-page-grid">
                <section className="forecast-panel forecast-result">
                    <h2>Next-Month Algal Bloom Forecast</h2>

                    {loading ? (
                        <p>Loading forecast…</p>
                    ) : error ? (
                        <p>Forecast unavailable.</p>
                    ) : validProbability ? (
                        <ForecastChart probability={forecast.probability} />
                    ) : (
                        <p>
                            {forecast
                                ? "The saved forecast has no valid probability."
                                : "No forecast available."}
                        </p>
                    )}

                    <p className="forecast-target">
                        {formatText(forecast?.targetMonth)}
                    </p>

                    <p className="forecast-explanation">
                        Estimated probability of algal bloom occurrence at the
                        selected monitoring location during the target month.
                    </p>
                </section>

                <section className="forecast-panel">
                    <h2>Forecast Details</h2>

                    <dl className="forecast-details">
                        <div>
                            <dt>Target Month</dt>
                            <dd>{formatText(forecast?.targetMonth)}</dd>
                        </div>

                        <div>
                            <dt>Input Observation Period</dt>
                            <dd>{formatText(forecast?.inputPeriod)}</dd>
                        </div>

                        <div>
                            <dt>Monitoring Location</dt>
                            <dd>{formatText(forecast?.location)}</dd>
                        </div>

                        <div>
                            <dt>GPS Coordinates</dt>
                            <dd>
                                {formatCoordinates(
                                    forecast?.latitude,
                                    forecast?.longitude
                                )}
                            </dd>
                        </div>

                        <div>
                            <dt>Generation Date</dt>
                            <dd>
                                {formatGenerationDate(forecast?.generatedAt)}
                            </dd>
                        </div>
                    </dl>
                </section>
            </div>

            <section className="forecast-panel">
                <h2>Forecast Inputs</h2>

                <p className="forecast-explanation">
                    The planned forecasting workflow combines water temperature,
                    pH, and dissolved oxygen measurements with corresponding
                    satellite-derived indicators for the monitoring area.
                </p>

                <p className="forecast-explanation">
                    Air temperature, humidity, and pressure are displayed as
                    local atmospheric conditions and are excluded from the
                    forecasting inputs.
                </p>
            </section>
        </div>
    );
}