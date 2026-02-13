import React from 'react';
import { AnimatePresence, motion } from 'framer-motion';

function ConfirmModal({
  open,
  title = 'Confirm',
  message = 'Are you sure?',
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  loading = false,
  onConfirm,
  onClose,
}) {
  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-900/40 p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 10 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl"
          >
            <h3 className="text-lg font-bold text-slate-900">{title}</h3>
            <p className="mt-2 text-sm text-slate-600">{message}</p>

            <div className="mt-5 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={onClose}
                disabled={loading}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-60"
              >
                {cancelText}
              </button>
              <motion.button
                type="button"
                onClick={onConfirm}
                disabled={loading}
                animate={loading ? { boxShadow: ['0 0 0 0 rgba(239,68,68,0.0)', '0 0 0 3px rgba(239,68,68,0.25)', '0 0 0 0 rgba(239,68,68,0.0)'] } : { boxShadow: '0 0 0 0 rgba(239,68,68,0.0)' }}
                transition={loading ? { repeat: Infinity, duration: 1.05, ease: 'linear' } : { duration: 0.15 }}
                className="inline-flex items-center rounded-lg border border-rose-600 bg-rose-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-70"
              >
                {loading ? <span className="mr-2 inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" /> : null}
                {loading ? 'Deleting...' : confirmText}
              </motion.button>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

export default ConfirmModal;
