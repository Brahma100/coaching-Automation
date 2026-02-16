import React from 'react';
import { AnimatePresence, motion } from 'framer-motion';

function SlotDrawer({
  open,
  onClose,
  selectedSlot,
  selectedDate,
  actionType,
  onActionTypeChange,
  batchList,
  scheduleBatchId,
  onScheduleBatchChange,
  blockForm,
  onBlockFormChange,
  onConfirmSchedule,
  onGoReschedule,
  onConfirmBlock,
  saving
}) {
  return (
    <AnimatePresence>
      {open ? (
        <>
          <motion.button
            type="button"
            aria-label="Close action drawer"
            className="time-capacity-drawer-backdrop"
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />
          <motion.aside
            className="time-capacity-drawer"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
          >
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">Selected Slot</h3>
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg border border-slate-300 px-2 py-1 text-xs font-semibold text-slate-700 dark:border-slate-600 dark:text-slate-200"
              >
                Close
              </button>
            </div>

            <dl className="mt-3 grid grid-cols-2 gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200">
              <div>
                <dt className="text-slate-500 dark:text-slate-400">Date</dt>
                <dd className="font-semibold">{selectedDate}</dd>
              </div>
              <div>
                <dt className="text-slate-500 dark:text-slate-400">Duration</dt>
                <dd className="font-semibold">{selectedSlot?.minutes || 0} mins</dd>
              </div>
              <div>
                <dt className="text-slate-500 dark:text-slate-400">Start Time</dt>
                <dd className="font-semibold">{selectedSlot?.start_time || '--:--'}</dd>
              </div>
              <div>
                <dt className="text-slate-500 dark:text-slate-400">End Time</dt>
                <dd className="font-semibold">{selectedSlot?.end_time || '--:--'}</dd>
              </div>
            </dl>

            <p className="mt-4 text-sm font-bold text-slate-800 dark:text-slate-100">Available Actions</p>
            <div className="mt-2 grid gap-2">
              <button
                type="button"
                onClick={() => onActionTypeChange('schedule')}
                className={`rounded-lg border px-3 py-2 text-left text-sm font-semibold transition ${
                  actionType === 'schedule' ? 'border-[#2f7bf6] bg-blue-50 text-[#1f5fc7] dark:bg-blue-950/40 dark:text-blue-300' : 'border-slate-300 text-slate-700 dark:border-slate-600 dark:text-slate-200'
                }`}
              >
                Schedule New Class
              </button>
              <button
                type="button"
                onClick={() => onActionTypeChange('reschedule')}
                className={`rounded-lg border px-3 py-2 text-left text-sm font-semibold transition ${
                  actionType === 'reschedule' ? 'border-[#2f7bf6] bg-blue-50 text-[#1f5fc7] dark:bg-blue-950/40 dark:text-blue-300' : 'border-slate-300 text-slate-700 dark:border-slate-600 dark:text-slate-200'
                }`}
              >
                Reschedule Existing Batch
              </button>
              <button
                type="button"
                onClick={() => onActionTypeChange('block')}
                className={`rounded-lg border px-3 py-2 text-left text-sm font-semibold transition ${
                  actionType === 'block' ? 'border-[#2f7bf6] bg-blue-50 text-[#1f5fc7] dark:bg-blue-950/40 dark:text-blue-300' : 'border-slate-300 text-slate-700 dark:border-slate-600 dark:text-slate-200'
                }`}
              >
                Block Personal Time
              </button>
            </div>

            {actionType === 'schedule' ? (
              <div className="mt-4 rounded-xl border border-slate-200 p-3 dark:border-slate-700">
                <label className="text-xs font-semibold text-slate-600 dark:text-slate-300">Select Batch</label>
                <select
                  value={scheduleBatchId}
                  onChange={(event) => onScheduleBatchChange(event.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                >
                  <option value="">Select batch</option>
                  {batchList.map((batch) => (
                    <option key={batch.id} value={batch.id}>
                      {batch.name}
                    </option>
                  ))}
                </select>
                {batchList.length === 0 ? <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">Create a batch to start scheduling.</p> : null}
                <button
                  type="button"
                  onClick={onConfirmSchedule}
                  disabled={!scheduleBatchId || saving}
                  className="mt-3 w-full rounded-lg bg-[#2f7bf6] px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
                >
                  Confirm Schedule
                </button>
              </div>
            ) : null}

            {actionType === 'reschedule' ? (
              <div className="mt-4 rounded-xl border border-slate-200 p-3 dark:border-slate-700">
                <p className="text-sm text-slate-700 dark:text-slate-200">Open assistant to pick a target batch and suggested slot.</p>
                <button
                  type="button"
                  onClick={onGoReschedule}
                  className="mt-3 w-full rounded-lg bg-amber-500 px-3 py-2 text-sm font-semibold text-white"
                >
                  Open Reschedule Assistant
                </button>
              </div>
            ) : null}

            {actionType === 'block' ? (
              <div className="mt-4 rounded-xl border border-slate-200 p-3 dark:border-slate-700">
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="time"
                    value={blockForm.start}
                    onChange={(event) => onBlockFormChange({ ...blockForm, start: event.target.value })}
                    className="rounded-lg border border-slate-300 px-2 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                  />
                  <input
                    type="time"
                    value={blockForm.end}
                    onChange={(event) => onBlockFormChange({ ...blockForm, end: event.target.value })}
                    className="rounded-lg border border-slate-300 px-2 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                  />
                </div>
                <input
                  type="text"
                  value={blockForm.reason}
                  onChange={(event) => onBlockFormChange({ ...blockForm, reason: event.target.value })}
                  placeholder="Reason"
                  className="mt-2 w-full rounded-lg border border-slate-300 px-2 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                />
                <button
                  type="button"
                  onClick={onConfirmBlock}
                  disabled={saving}
                  className="mt-3 w-full rounded-lg bg-slate-800 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
                >
                  Confirm Block
                </button>
              </div>
            ) : null}
          </motion.aside>
        </>
      ) : null}
    </AnimatePresence>
  );
}

export default React.memo(SlotDrawer);
