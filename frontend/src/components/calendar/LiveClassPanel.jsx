import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';

function LiveClassPanel({ liveEvent, onOpenLiveEvent }) {
  const shouldReduceMotion = useReducedMotion();

  if (!liveEvent) return null;

  return (
    <motion.button
      type="button"
      className="calendar-live-fab"
      onClick={() => onOpenLiveEvent?.(liveEvent)}
      title={`${liveEvent.batch_name} is live`}
      aria-label={`Open live class details for ${liveEvent.batch_name}`}
      initial={shouldReduceMotion ? false : { y: 20, opacity: 0 }}
      animate={shouldReduceMotion ? undefined : { y: 0, opacity: 1 }}
      transition={{ duration: 0.2 }}
    >
      Live
    </motion.button>
  );
}

export default LiveClassPanel;
