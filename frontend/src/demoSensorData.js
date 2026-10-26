import { db } from './firebase';
import { doc, Timestamp, writeBatch } from 'firebase/firestore';

const count = 36;
const id = i => `hab_demo_reading_${String(i).padStart(3, '0')}`;
const round = n => Number(n.toFixed(2));

async function updateDemo(remove, status, buttons) {
  buttons.forEach(b => b.disabled = true);
  status.textContent = remove ? 'Removing demo readings…' : 'Saving demo readings…';

  try {
    const batch = writeBatch(db);

    for (let i = 1; i <= count; i++) {
      const ref = doc(db, 'sensor_readings', id(i));

      if (remove) {
        batch.delete(ref);
        continue;
      }

      const date = new Date(Date.now() - (count - i) * 3600000);
      const timestamp = Timestamp.fromDate(date);
      const water = round(29.1 + 1.1 * Math.sin(i / 5));
      const ph = round(7.5 + 0.3 * Math.sin(i / 7));
      const oxygen = round(6.4 + 0.7 * Math.cos(i / 6));
      const air = round(water + 1.4);
      const humidity = round(73 + 7 * Math.sin(i / 8));
      const pressure = round(1011 + 2 * Math.cos(i / 9));

      batch.set(ref, {
        demo: true,
        isDemo: true,
        simulated: true,
        source: 'SIMULATED_DEMO',
        deviceId: 'DEMO-ESP32',
        stationId: 'DEMO-STATION',

        timestamp,
        createdAt: timestamp,
        measuredAt: timestamp,
        recordedAt: timestamp,
        date: date.toISOString(),

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
      });
    }

    await batch.commit();
    status.textContent = remove
      ? 'Demo readings removed.'
      : '36 demo readings saved. Check Dashboard and Sensor Data.';

  } catch (err) {
    status.textContent = `Firebase error: ${err.code || err.message}`;
    console.error(err);
  } finally {
    buttons.forEach(b => b.disabled = false);
  }
}

function mount() {
  if (document.getElementById('hab-demo-tools')) return;

  const el = document.createElement('aside');
  el.id = 'hab-demo-tools';
  el.style.cssText =
    'position:fixed;right:16px;bottom:16px;z-index:99999;' +
    'max-width:290px;padding:14px;border-radius:12px;' +
    'background:#16202d;color:white;font:13px Arial;' +
    'box-shadow:0 4px 25px #0008';

  el.innerHTML = `
    <b>DEMO MODE · SIMULATED DATA</b>
    <p>Existing HAB Risk Forecasting web app</p>
    <button id="demo-load">Load Demo Data</button>
    <button id="demo-remove">Remove Demo</button>
    <p id="demo-status">No physical sensor connected.</p>
  `;

  document.body.appendChild(el);

  const status = el.querySelector('#demo-status');
  const buttons = [
    el.querySelector('#demo-load'),
    el.querySelector('#demo-remove')
  ];

  buttons[0].onclick = () => updateDemo(false, status, buttons);
  buttons[1].onclick = () => updateDemo(true, status, buttons);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', mount);
} else {
  mount();
}
