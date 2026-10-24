import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Filler,
} from "chart.js";
import { Line } from "react-chartjs-2";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Filler
);

export default function SensorTrend({
  title,
  labels = [],
  values = [],
  color,
  fillColor,
  unit = "",
  emptyMessage = "No data available.",
}) {
  const chartValues = labels.map((_, index) =>
    Number.isFinite(values[index]) ? values[index] : null
  );

  const hasData = chartValues.some((value) => value !== null);

  const data = {
    labels,
    datasets: [
      {
        label: title,
        data: chartValues,
        borderColor: color,
        backgroundColor: fillColor,
        borderWidth: 2,
        pointRadius: 3,
        pointHoverRadius: 5,
        tension: 0.2,
        fill: true,
        spanGaps: false,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: "index",
      intersect: false,
    },
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        callbacks: {
          label: (context) =>
            `${context.dataset.label}: ${context.parsed.y}${
              unit ? ` ${unit}` : ""
            }`,
        },
      },
    },
    scales: {
      x: {
        grid: {
          display: false,
        },
        ticks: {
          maxTicksLimit: 4,
        },
        title: {
          display: true,
          text: "Measurement date and time (PHT)",
        },
      },
      y: {
        grid: {
          color: "rgba(0, 0, 0, 0.06)",
        },
        ticks: {
          maxTicksLimit: 5,
        },
        title: {
          display: Boolean(unit),
          text: unit,
        },
      },
    },
  };

  return (
    <section className="dashboard-card trend-card">
      <div className="trend-heading">
        <h2>{title}</h2>
        <span>Latest stored observations</span>
      </div>

      <div className="sensor-chart">
        {hasData ? (
          <Line
            data={data}
            options={options}
            role="img"
            aria-label={title}
          />
        ) : (
          <p role="status">{emptyMessage}</p>
        )}
      </div>
    </section>
  );
}