import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { FiZap } from 'react-icons/fi';

function CalendarEvent({ event, compact, hideMiddleInfo = false, onClick }) {
  const shouldReduceMotion = useReducedMotion();

  return (
    <motion.button
      type="button"
      onClick={() => onClick(event)}
      className={`calendar-event-card ${event.color_class || ''} ${compact ? 'compact' : ''} ${event.status === 'live' ? 'live' : ''}`}
      whileHover={shouldReduceMotion ? undefined : { scale: 1.01 }}
      transition={{ duration: 0.15 }}
    >
      <div className="calendar-event-head">
        <span className="calendar-event-title-wrap">
          {event.is_current ? <span className="calendar-active-zap" title="Currently running"><FiZap /></span> : null}
          <p className="calendar-event-title">{event.batch_name}</p>
        </span>
        {event.status === 'live' ? <span className="calendar-live-pill">LIVE</span> : null}
      </div>
      <p className="calendar-event-time">{event.time_label}</p>
      {!hideMiddleInfo ? <p className="calendar-event-meta">{event.student_count} students</p> : null}
      <div className="calendar-event-badges">
        {event.fee_due_count > 0 ? <span className="calendar-badge fee">Fee {event.fee_due_count}</span> : null}
        {event.risk_count > 0 ? <span className="calendar-badge risk">Risk {event.risk_count}</span> : null}
      </div>
    </motion.button>
  );
}

export default CalendarEvent;
