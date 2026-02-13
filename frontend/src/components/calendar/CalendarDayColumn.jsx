import React from 'react';

import HeatmapOverlay from './HeatmapOverlay.jsx';

function CalendarDayColumn({ dayKey, slots, children, isToday, currentTimeLine, heatmapClass, heatmapEnabled, holidayLabel }) {
  return (
    <div className={`calendar-day-column ${isToday ? 'today' : ''}`}>
      {heatmapEnabled ? <HeatmapOverlay className={heatmapClass} /> : null}
      {holidayLabel ? <div className="calendar-day-holiday" title={holidayLabel}>{holidayLabel}</div> : null}
      {slots.map((slot) => (
        <div key={`${dayKey}-${slot}`} className="calendar-cell" />
      ))}
      {isToday ? <div className="calendar-now-line" style={{ top: `${currentTimeLine}px` }} /> : null}
      {children}
    </div>
  );
}

export default CalendarDayColumn;
