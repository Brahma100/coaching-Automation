import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';

function LiveClassPanel({ liveEvent, onStartAttendance, onQuickMessage, onViewBatch }) {
  const shouldReduceMotion = useReducedMotion();
  if (!liveEvent) return null;

  return (
    <motion.div
      className="calendar-live-panel"
      initial={shouldReduceMotion ? false : { y: 20, opacity: 0 }}
      animate={shouldReduceMotion ? undefined : { y: 0, opacity: 1 }}
      transition={{ duration: 0.2 }}
    >
      <div>
        <p className="calendar-live-eyebrow">Live now</p>
        <h3 className="calendar-live-title">{liveEvent.batch_name}</h3>
        <p className="calendar-live-meta">{liveEvent.time_label}</p>
      </div>
      <div className="calendar-live-actions">
        <button type="button" className="calendar-action-btn" onClick={onStartAttendance}>Start Attendance</button>
        <button type="button" className="calendar-action-btn" onClick={onQuickMessage}>Quick Messaging</button>
        <button type="button" className="calendar-action-btn" onClick={onViewBatch}>View Batch</button>
      </div>
    </motion.div>
  );
}

export default LiveClassPanel;
