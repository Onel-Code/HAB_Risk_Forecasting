import {
  onSnapshot as liveOnSnapshot,
  getDocs as liveGetDocs,
  Timestamp
} from "firebase/firestore";

const FLAG = "hab_local_sensor_demo";
const STEP = "hab_local_sensor_step";

const enabled = () =>
  import.meta.env.DEV &&
  localStorage.getItem(FLAG) !== "off";

function isSensor(ref) {
  const path = ref?._query?.path ?? ref?._path ?? ref?.path;
  const name = path?.canonicalString?.() ??
    path?.toString?.() ?? String(path ?? "");
  return name.includes("sensor_readings");
}

function makeSnapshot(ref) {
  const step = Number(localStorage.getItem(STEP) || 0);
  const now = Date.now();

  const docs = Array.from({ length: 36 }, (_, index) => {
    const i = index + 1 + step;
    const time = Timestamp.fromDate(
      new Date(now - (35 - index) * 3600000)
    );

    const water = +(29.1 + 1.1 * Math.sin(i / 5)).toFixed(2);
    const ph = +(7.5 + 0.3 * Math.sin(i / 7)).toFixed(2);
    const oxygen = +(6.4 + 0.7 * Math.cos(i / 6)).toFixed(2);
    const air = +(water + 1.4).toFixed(2);
    const humidity = +(73 + 7 * Math.sin(i / 8)).toFixed(2);
    const pressure = +(1011 + 2 * Math.cos(i / 9)).toFixed(2);

    const data = {
      source: "SIMULATED_DEMO",
      demo: true,
      simulated: true,
      deviceId: "DEMO-ESP32",
      stationId: "DEMO-STATION",
      timestamp: time,
      measuredAt: time,
      createdAt: time,
      recordedAt: time,
      date: time.toDate().toISOString(),

      waterTemperature: water,
      waterTemp: water,
      water_temperature: water,
      temperature: water,
      temperatureC: water,
      temperature_c: water,

      ph,
      pH: ph,
      phLevel: ph,

      dissolvedOxygen: oxygen,
      dissolved_oxygen: oxygen,
      do: oxygen,
      DO: oxygen,
      doMgL: oxygen,

      airTemperature: air,
      airTemp: air,
      humidity,
      relativeHumidity: humidity,
      pressure,
      barometricPressure: pressure
    };

    return {
      id: `hab_demo_${index}`,
      exists: () => true,
      data: () => data,
      get: key => data[key]
    };
  }).reverse();

  return {
    query: ref,
    docs,
    size: docs.length,
    empty: false,
    metadata: { fromCache: true, hasPendingWrites: false },
    forEach: fn => docs.forEach(fn),
    docChanges: () => docs.map(doc => ({
      type: "added",
      doc
    }))
  };
}

export function onSnapshot(ref, ...callbacks) {
  if (!enabled() || !isSensor(ref)) {
    return liveOnSnapshot(ref, ...callbacks);
  }

  const observer = callbacks.find(
    x => typeof x === "function" ||
      typeof x?.next === "function"
  );

  const next = typeof observer === "function"
    ? observer
    : observer?.next?.bind(observer);

  let active = true;

  queueMicrotask(() => {
    if (active) next?.(makeSnapshot(ref));
  });

  return () => { active = false; };
}

export function getDocs(ref) {
  if (enabled() && isSensor(ref)) {
    return Promise.resolve(makeSnapshot(ref));
  }
  return liveGetDocs(ref);
}

function mountDemoControls() {
  if (document.getElementById("hab-local-demo")) return;

  const panel = document.createElement("div");
  panel.id = "hab-local-demo";
  panel.style.cssText =
    "position:fixed;right:15px;bottom:15px;z-index:99999;" +
    "background:#142536;color:white;padding:12px;" +
    "border-radius:10px;font:12px Arial;box-shadow:0 4px 20px #0006";

  panel.innerHTML = `
    <b>SIMULATED DATA · LOCAL DEMO</b>
    <p>Not connected to a physical ESP32.</p>
    <button id="hab-next">Next Reading</button>
    <button id="hab-toggle">
      ${enabled() ? "Turn Demo Off" : "Turn Demo On"}
    </button>
  `;

  document.body.appendChild(panel);

  panel.querySelector("#hab-next").onclick = () => {
    localStorage.setItem(
      STEP,
      String(Number(localStorage.getItem(STEP) || 0) + 1)
    );
    location.reload();
  };

  panel.querySelector("#hab-toggle").onclick = () => {
    localStorage.setItem(FLAG, enabled() ? "off" : "on");
    location.reload();
  };
}

if (import.meta.env.DEV) {
  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded", mountDemoControls
    );
  } else {
    mountDemoControls();
  }
}
