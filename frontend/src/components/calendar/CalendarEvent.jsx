import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { useDraggable } from '@dnd-kit/core';

import ResizeHandles from './ResizeHandles.jsx';

function CalendarEvent({ event, compact, onClick, onResizeStart }) {
  const shouldReduceMotion = useReducedMotion();
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: event.uid,
    data: { event }
  });

  const style = transform ? {
    transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`
  } : undefined;

  return (
    <motion.button
      ref={setNodeRef}
      type="button"
      onClick={() => onClick(event)}
      className={`calendar-event-card ${event.color_class || ''} ${compact ? 'compact' : ''} ${event.status === 'live' ? 'live' : ''} ${isDragging ? 'dragging' : ''}`}
      style={style}
      whileHover={shouldReduceMotion ? undefined : { scale: 1.01 }}
      transition={{ duration: 0.15 }}
      {...attributes}
      {...listeners}
    >
      <div className="calendar-event-head">
        <p className="calendar-event-title">{event.batch_name}</p>
        {event.status === 'live' ? <span className="calendar-live-pill">LIVE</span> : null}
      </div>
      <p className="calendar-event-time">{event.time_label}</p>
      <p className="calendar-event-meta">{event.student_count} students</p>
      <div className="calendar-event-badges">
        {event.fee_due_count > 0 ? <span className="calendar-badge fee">Fee {event.fee_due_count}</span> : null}
        {event.risk_count > 0 ? <span className="calendar-badge risk">Risk {event.risk_count}</span> : null}
      </div>
      <ResizeHandles onResizeStart={onResizeStart} />
    </motion.button>
  );
}

export default CalendarEvent;
