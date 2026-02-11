import React from 'react';
import { useDroppable } from '@dnd-kit/core';

import HeatmapOverlay from './HeatmapOverlay.jsx';

function CalendarDayColumn({ dayKey, slots, children, isToday, currentTimeLine, heatmapClass, heatmapEnabled }) {
  const { setNodeRef, isOver } = useDroppable({ id: dayKey });

  return (
    <div ref={setNodeRef} className={`calendar-day-column ${isOver ? 'drag-over' : ''}`}>
      {heatmapEnabled ? <HeatmapOverlay className={heatmapClass} /> : null}
      {slots.map((slot) => (
        <div key={`${dayKey}-${slot}`} className="calendar-cell" />
      ))}
      {isToday ? <div className="calendar-now-line" style={{ top: `${currentTimeLine}px` }} /> : null}
      {children}
    </div>
  );
}

export default CalendarDayColumn;
