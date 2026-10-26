import React from 'react';
import Original from './ForecastOriginal.jsx';
import ForecastExperimentPanel from './ForecastExperimentPanel.jsx';
import AutoForecastPanel from './AutoForecastPanel.jsx';
import DemoPipelinePanel from './DemoPipelinePanel.jsx';
export default function Forecast() {
  return <><AutoForecastPanel />
    <DemoPipelinePanel />
    <details style={{marginBottom:20}}><summary>Manual experimental test</summary>
      <ForecastExperimentPanel />
    </details>
    <Original />
  </>;
}
