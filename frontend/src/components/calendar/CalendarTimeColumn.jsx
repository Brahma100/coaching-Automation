import React from 'react';

function CalendarTimeColumn({ slots }) {
  return (
    <div className="calendar-time-column">
      {slots.map((slot) => (
        <div key={slot} className="calendar-time-slot">{slot}</div>
      ))}
    </div>
  );
}

export default CalendarTimeColumn;
