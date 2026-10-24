import { useEffect, useState } from "react";
import {
  BrowserRouter,
  NavLink,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router";
import "./shared.css";
import "./App.css";
import Dashboard from "./pages/Dashboard";
import SensorData from "./pages/SensorData";
import SatelliteData from "./pages/SatelliteData";
import Forecast from "./pages/Forecast";
import SystemStatus from "./pages/SystemStatus";
import {
  collection,
  limit,
  onSnapshot,
  orderBy,
  query,
} from "firebase/firestore";
import { db } from "./firebase";

const pages = [
  {
    path: "/",
    title: "Dashboard",
    icon: "/icons/dashboard.png",
  },
  {
    path: "/sensor-data",
    title: "Sensor Data",
    icon: "/icons/sensor-data.png",
  },
  {
    path: "/satellite-data",
    title: "Satellite Data",
    icon: "/icons/satellite-data.png",
  },
  {
    path: "/forecast",
    title: "Next-Month Algal Bloom Forecast",
    icon: "/icons/forecast.png",
  },
  {
    path: "/system-status",
    title: "System Status",
    icon: "/icons/system-status.png",
  },
];

function AppLayout() {
  const { pathname } = useLocation();
  const [now, setNow] = useState(() => new Date());
  const [latestMeasurement, setLatestMeasurement] = useState(null);
  const [loadingMeasurement, setLoadingMeasurement] = useState(true);
  const [measurementError, setMeasurementError] = useState(false);

  const currentPage = pages.find((page) => page.path === pathname);

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const latestReadingQuery = query(
      collection(db, "sensor_readings"),
      orderBy("measuredAt", "desc"),
      limit(1)
    );

    return onSnapshot(
      latestReadingQuery,
      (snapshot) => {
        const reading = snapshot.empty
          ? null
          : snapshot.docs[0].data();

        setLatestMeasurement(
          typeof reading?.measuredAt?.toDate === "function"
            ? reading.measuredAt.toDate()
            : null
        );

        setMeasurementError(false);
        setLoadingMeasurement(false);
      },
      (error) => {
        console.error("Header measurement listener:", error);
        setLatestMeasurement(null);
        setMeasurementError(true);
        setLoadingMeasurement(false);
      }
    );
  }, []);

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <nav aria-label="Main navigation">
          {pages.map((page) => (
            <NavLink
              key={page.path}
              to={page.path}
              end={page.path === "/"}
              title={page.title}
              aria-label={page.title}
              className={({ isActive }) =>
                `sidebar-link${isActive ? " active" : ""}`
              }
            >
              <img
                src={page.icon}
                alt=""
                className="sidebar-icon"
              />
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="main-layout">
        <header className="topbar">
          <h1>{currentPage?.title ?? "Dashboard"}</h1>

          <div className="header-details">
            <span className="last-updated" role="status">
              Latest Measurement:{" "}
              {loadingMeasurement
                ? "Loading…"
                : measurementError
                  ? "Unavailable"
                  : latestMeasurement
                    ? `${latestMeasurement.toLocaleString("en-PH", {
                      timeZone: "Asia/Manila",
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })} (PHT)`
                    : "—"}
            </span>

            <span
              className="device-status"
              title="Current device connectivity requires device telemetry."
            >
              <span className="status-dot" aria-hidden="true" />
              Device status unknown
            </span>

            <time
              dateTime={now.toISOString()}
              title="Current Philippine time"
            >
              {now.toLocaleTimeString("en-PH", {
                timeZone: "Asia/Manila",
                hour: "2-digit",
                minute: "2-digit",
                hour12: true,
              })}{" "}
              PHT
            </time>
          </div>
        </header>

        <main className="page-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/sensor-data" element={<SensorData />} />
            <Route path="/satellite-data" element={<SatelliteData />} />
            <Route path="/forecast" element={<Forecast />} />
            <Route path="/system-status" element={<SystemStatus />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppLayout />
    </BrowserRouter>
  );
}