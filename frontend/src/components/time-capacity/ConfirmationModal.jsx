import React from 'react';
import { AnimatePresence, motion } from 'framer-motion';

function ConfirmationModal({
  open,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  onConfirm,
  onCancel,
  busy = false,
  hideCancel = false
}) {
  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="time-capacity-modal-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.div
            className="time-capacity-modal"
            initial={{ opacity: 0, scale: 0.98, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.98, y: 8 }}
            transition={{ duration: 0.18 }}
          >
            <h4 className="text-base font-bold text-slate-900 dark:text-slate-100">{title}</h4>
            {description ? <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{description}</p> : null}
            <div className="mt-4 flex justify-end gap-2">
              {!hideCancel ? (
                <button
                  type="button"
                  onClick={onCancel}
                  className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-semibold text-slate-700 dark:border-slate-600 dark:text-slate-200"
                  disabled={busy}
                >
                  {cancelLabel}
                </button>
              ) : null}
              <button
                type="button"
                onClick={onConfirm}
                disabled={busy}
                className="rounded-lg bg-[#2f7bf6] px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-60"
              >
                {busy ? 'Saving...' : confirmLabel}
              </button>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

export default React.memo(ConfirmationModal);
