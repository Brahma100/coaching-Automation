import React from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { FiAlertTriangle, FiCheckCircle, FiInfo } from 'react-icons/fi';

const TONE_MAP = {
  success: {
    icon: FiCheckCircle,
    shell: 'border-emerald-200 bg-emerald-50 text-emerald-800',
    iconColor: 'text-emerald-600',
  },
  error: {
    icon: FiAlertTriangle,
    shell: 'border-rose-200 bg-rose-50 text-rose-800',
    iconColor: 'text-rose-600',
  },
  info: {
    icon: FiInfo,
    shell: 'border-sky-200 bg-sky-50 text-sky-800',
    iconColor: 'text-sky-600',
  },
};

function Toast({ open, message, tone = 'success', duration = 5000, onClose }) {
  React.useEffect(() => {
    if (!open) return undefined;
    const timer = window.setTimeout(() => onClose?.(), duration);
    return () => window.clearTimeout(timer);
  }, [open, duration, onClose]);

  const ui = TONE_MAP[tone] || TONE_MAP.info;
  const Icon = ui.icon;

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          initial={{ opacity: 0, x: 80, y: -16 }}
          animate={{ opacity: 1, x: 0, y: 0 }}
          exit={{ opacity: 0, x: 80, y: -16 }}
          transition={{ duration: 0.24, ease: 'easeOut' }}
          className="fixed right-4 top-4 z-[80]"
        >
          <div className={`flex min-w-[260px] items-start gap-2 rounded-xl border px-3 py-2 shadow-lg ${ui.shell}`}>
            <Icon className={`mt-0.5 ${ui.iconColor}`} />
            <p className="text-sm font-semibold">{message}</p>
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

export default Toast;
