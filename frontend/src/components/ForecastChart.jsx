import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
} from "chart.js";
import { Doughnut } from "react-chartjs-2";

ChartJS.register(ArcElement, Tooltip);

export default function ForecastChart({ probability }) {
  const valid =
    typeof probability === "number" &&
    Number.isFinite(probability) &&
    probability >= 0 &&
    probability <= 100;

  if (!valid) {
    return <p>No forecast available.</p>;
  }

  const data = {
    labels: ["Bloom occurrence", "No bloom occurrence"],
    datasets: [
      {
        data: [probability, 100 - probability],
        backgroundColor: ["#24b2a5", "#eeeeee"],
        borderWidth: 0,
        hoverOffset: 3,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: "76%",
    plugins: {
      tooltip: {
        callbacks: {
          label: (context) =>
            `${context.label}: ${Number(context.raw).toFixed(1)}%`,
        },
      },
    },
  };

  return (
    <div className="forecast-visual">
      <Doughnut
        data={data}
        options={options}
        role="img"
        aria-label={`Estimated probability of next-month algal bloom occurrence: ${probability}%`}
      />

      <span className="forecast-value" aria-hidden="true">
        {probability}%
      </span>
    </div>
  );
}