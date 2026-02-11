import React from 'react';

function HeatmapOverlay({ className }) {
  if (!className) return <div className="calendar-heatmap-overlay" />;
  return <div className={`calendar-heatmap-overlay ${className}`} />;
}

export default React.memo(HeatmapOverlay);
