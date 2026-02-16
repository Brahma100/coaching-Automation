
import React from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import { FiHelpCircle, FiInfo, FiCalendar, FiClock, FiZap, FiArrowRight, FiChevronDown, FiPlusCircle } from 'react-icons/fi';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';

import { apiErrorToastReceived } from '../store/slices/appSlice.js';
import {
  addBusySlot,
  createOverrideRequested,
  createTimeBlockRequested,
  convertFreeToBusy,
  deleteTimeBlockRequested,
  loadAvailabilityRequested,
  loadBatchesRequested,
  loadCapacityRequested,
  loadRescheduleRequested,
  loadWeeklyRequested,
  removeBusySlotById,
  removeRescheduleRowsByStart,
  replaceBusySlot,
  setActiveTab,
  setDateValue,
  setDebouncedDate,
  setRescheduleBatchId,
  setRescheduleWeeksVisible,
} from '../store/slices/timeCapacitySlice.js';
import Legend from '../components/time-capacity/Legend';
import SlotDrawer from '../components/time-capacity/SlotDrawer';
import ConfirmationModal from '../components/time-capacity/ConfirmationModal';
import '../styles/time-capacity.css';

const TABS = [
  { key: 'availability', label: 'Availability' },
  { key: 'capacity', label: 'Batch Capacity' },
  { key: 'reschedule', label: 'Reschedule Assistant' },
  { key: 'weekly', label: 'Weekly Load' }
];

const SLOT_LEGEND = [
  { key: 'free', label: 'Green = Available slot', dotClass: 'bg-emerald-500' },
  { key: 'busy', label: 'Red = Scheduled class', dotClass: 'bg-rose-500' },
  { key: 'blocked', label: 'Grey = Personal blocked time', dotClass: 'bg-slate-500' },
  { key: 'suggested', label: 'Yellow = Suggested reschedule option', dotClass: 'bg-amber-500' }
];

const CAPACITY_LEGEND = [
  { key: 'healthy', label: 'Green = Healthy capacity', dotClass: 'bg-emerald-500' },
  { key: 'near', label: 'Yellow = Near full', dotClass: 'bg-amber-500' },
  { key: 'full', label: 'Red = Full', dotClass: 'bg-rose-500' }
];

const cardMotion = {
  initial: { opacity: 0, scale: 0.99 },
  animate: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 0.99 }
};

function EmptyStateNotice({ message, onManageBatches }) {
  return (
    <div className="time-capacity-empty rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600 dark:border-slate-600 dark:bg-slate-800/70 dark:text-slate-200">
      <p className="font-medium">{message}</p>
      <button
        type="button"
        onClick={onManageBatches}
        className="mt-3 rounded-lg bg-[#2f7bf6] px-3 py-2 text-xs font-semibold text-white"
      >
        Configure Batch Schedule
      </button>
    </div>
  );
}

function dateToInput(value) {
  return value.toISOString().slice(0, 10);
}

function mondayForDate(inputDate) {
  const base = new Date(`${inputDate}T00:00:00`);
  const day = base.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  base.setDate(base.getDate() + diff);
  return dateToInput(base);
}

function weekdayFromInputDate(inputDate) {
  const day = new Date(`${inputDate}T00:00:00`).getDay();
  return day === 0 ? 6 : day - 1;
}

function shortWeekdayLabelFromInputDate(inputDate) {
  const dt = new Date(`${inputDate}T00:00:00`);
  if (Number.isNaN(dt.getTime())) return '';
  return dt.toLocaleDateString(undefined, { weekday: 'short' });
}

function resolveOverrideDurationMinutes({ selectedFree, selectedBatch, inputDate }) {
  const slotMinutesRaw = Number(selectedFree?.minutes || 0);
  const slotMinutes = Number.isFinite(slotMinutesRaw) ? Math.max(1, slotMinutesRaw) : 60;
  const weekday = weekdayFromInputDate(inputDate);
  const schedules = Array.isArray(selectedBatch?.schedules) ? selectedBatch.schedules : [];
  const weekdaySchedule = schedules.find((row) => Number(row?.weekday) === weekday);
  const preferredRaw = Number(
    weekdaySchedule?.duration_minutes
      ?? selectedBatch?.default_duration_minutes
      ?? 60
  );
  const preferred = Number.isFinite(preferredRaw) ? preferredRaw : 60;
  return Math.max(1, Math.min(300, preferred, slotMinutes));
}

function utilizationTone(value) {
  if (value >= 100) return 'bg-rose-500';
  if (value > 90) return 'bg-rose-500';
  if (value >= 70) return 'bg-amber-500';
  return 'bg-emerald-500';
}

function minutesToHoursLabel(totalMinutes) {
  const safe = Math.max(0, Number(totalMinutes || 0));
  const hrs = Math.floor(safe / 60);
  const mins = safe % 60;
  if (mins === 0) return `${hrs}h`;
  return `${hrs}h ${mins}m`;
}

function prettyDate(value) {
  if (!value) return '--';
  const dt = new Date(`${value}T00:00:00`);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
}

function longDate(value) {
  if (!value) return '--';
  const dt = new Date(`${value}T00:00:00`);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
}

function timeToMinutes(timeText) {
  const parts = String(timeText || '').split(':');
  const hh = Number(parts[0] || 0);
  const mm = Number(parts[1] || 0);
  return hh * 60 + mm;
}

function addMinutesToTime(timeText, minutesToAdd) {
  const total = timeToMinutes(timeText) + Number(minutesToAdd || 0);
  const normalized = ((total % (24 * 60)) + (24 * 60)) % (24 * 60);
  const hh = String(Math.floor(normalized / 60)).padStart(2, '0');
  const mm = String(normalized % 60).padStart(2, '0');
  return `${hh}:${mm}`;
}

function slotStatusLabel(slot) {
  if (slot.type === 'free') return 'Free';
  if (slot.source === 'teacher_block') return 'Blocked personal time';
  return 'Scheduled class';
}

function slotBatchName(slot) {
  return slot.batch_name || slot.batch || slot.subject || 'N/A';
}

function defaultActionTypeForSlot(slot) {
  return slot?.type === 'free' ? 'schedule' : 'block';
}

const SlotItem = React.memo(function SlotItem({ slot, reducedMotion, onSelectSlot, onInspectSlot, onDeleteBlocked }) {
  const tone =
    slot.type === 'free'
      ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
      : slot.source === 'teacher_block'
        ? 'border-slate-300 bg-slate-100 text-slate-700'
        : 'border-rose-200 bg-rose-50 text-rose-900';
  return (
    <motion.div
      layout
      initial={reducedMotion ? false : { opacity: 0, y: 8 }}
      animate={reducedMotion ? undefined : { opacity: 1, y: 0 }}
      transition={{ duration: 0.18 }}
      className={`time-slot-item group relative rounded-xl border p-3 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${tone}`}
      onClick={() => onSelectSlot(slot)}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onSelectSlot(slot);
        }
      }}
    >
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold">
          {slot.start_time} - {slot.end_time}
        </p>
        <p className="text-xs font-medium">{slot.minutes}m</p>
      </div>
      <p className="mt-1 text-xs font-semibold">{slotStatusLabel(slot)}</p>
      {slot.reason ? <p className="mt-1 text-xs">{slot.reason}</p> : null}
      {slot.type !== 'free' ? <p className="mt-1 text-xs">Batch: {slotBatchName(slot)}</p> : null}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onInspectSlot(slot);
          }}
          className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700"
        >
          <FiInfo className="h-3 w-3" /> Details
        </button>
        {slot.type === 'free' ? (
          <span className="rounded-md bg-emerald-600 px-2 py-1 text-[11px] font-semibold text-white">Choose slot</span>
        ) : null}
        {slot.source === 'teacher_block' && slot.id ? (
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onDeleteBlocked(slot);
            }}
            className="rounded-lg bg-slate-700 px-2.5 py-1 text-xs font-semibold text-white"
          >
            Remove block
          </button>
        ) : null}
      </div>
      <div className="time-slot-tooltip pointer-events-none absolute left-3 top-[calc(100%+6px)] z-10 hidden w-64 rounded-lg border border-slate-200 bg-white p-2 text-xs text-slate-700 shadow-lg group-hover:block">
        <p><span className="font-semibold">Time:</span> {slot.start_time} - {slot.end_time}</p>
        <p><span className="font-semibold">Status:</span> {slotStatusLabel(slot)}</p>
        <p><span className="font-semibold">Batch:</span> {slot.type === 'free' ? 'N/A' : slotBatchName(slot)}</p>
        <p><span className="font-semibold">Duration:</span> {slot.minutes} mins</p>
      </div>
    </motion.div>
  );
});

function TimeCapacity() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const reducedMotion = useReducedMotion();
  const {
    activeTab,
    dateValue,
    debouncedDate,
    availability,
    capacityRows,
    weeklyLoad,
    batchList,
    rescheduleBatchId,
    rescheduleRows,
    rescheduleWeeksVisible,
    availabilityLoading,
    capacityLoading,
    rescheduleLoading,
    weeklyLoading,
    syncTick,
  } = useSelector((state) => state.timeCapacity || {});
  const [openRescheduleDate, setOpenRescheduleDate] = React.useState('');
  const [selectedSlot, setSelectedSlot] = React.useState(null);
  const [scheduleBatchId, setScheduleBatchId] = React.useState('');
  const [blockForm, setBlockForm] = React.useState({ start: '13:00', end: '14:00', reason: '' });
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [drawerAction, setDrawerAction] = React.useState('schedule');
  const [inspectSlot, setInspectSlot] = React.useState(null);
  const [helpOpen, setHelpOpen] = React.useState(false);
  const [pendingConfirm, setPendingConfirm] = React.useState(null);
  const [rescheduleConfirm, setRescheduleConfirm] = React.useState(null);
  const [saving, setSaving] = React.useState(false);

  React.useEffect(() => {
    const handle = window.setTimeout(() => dispatch(setDebouncedDate(dateValue)), 260);
    return () => window.clearTimeout(handle);
  }, [dateValue, dispatch]);

  React.useEffect(() => {
    dispatch(loadBatchesRequested({ forDate: debouncedDate }));
  }, [debouncedDate, dispatch, syncTick]);

  React.useEffect(() => {
    if (activeTab !== 'availability') return;
    dispatch(loadAvailabilityRequested({ date: debouncedDate }));
  }, [activeTab, debouncedDate, dispatch, syncTick]);

  React.useEffect(() => {
    if (activeTab !== 'capacity') return;
    dispatch(loadCapacityRequested());
  }, [activeTab, dispatch, syncTick]);

  React.useEffect(() => {
    dispatch(setRescheduleWeeksVisible(1));
  }, [debouncedDate, dispatch, rescheduleBatchId]);

  React.useEffect(() => {
    if (activeTab !== 'reschedule' || !rescheduleBatchId) {
      dispatch(loadRescheduleRequested({ batchId: '', date: debouncedDate, weeksVisible: 1 }));
      return;
    }
    dispatch(loadRescheduleRequested({
      batchId: rescheduleBatchId,
      date: debouncedDate,
      weeksVisible: rescheduleWeeksVisible,
    }));
  }, [activeTab, debouncedDate, dispatch, rescheduleBatchId, rescheduleWeeksVisible, syncTick]);

  React.useEffect(() => {
    if (activeTab !== 'weekly') return;
    dispatch(loadWeeklyRequested({ weekStart: mondayForDate(debouncedDate) }));
  }, [activeTab, debouncedDate, dispatch, syncTick]);

  const mergedSlots = React.useMemo(() => {
    const busy = Array.isArray(availability?.busy_slots) ? availability.busy_slots : [];
    const free = Array.isArray(availability?.free_slots) ? availability.free_slots : [];
    return [...busy, ...free].sort((a, b) => String(a.start_time || '').localeCompare(String(b.start_time || '')));
  }, [availability]);

  const groupedSuggestions = React.useMemo(() => {
    return rescheduleRows.reduce((acc, row) => {
      const key = row.date || '';
      if (!acc[key]) acc[key] = [];
      acc[key].push(row);
      return acc;
    }, {});
  }, [rescheduleRows]);

  React.useEffect(() => {
    const keys = Object.keys(groupedSuggestions);
    if (!keys.length) {
      if (openRescheduleDate) setOpenRescheduleDate('');
      return;
    }
    if (openRescheduleDate && !groupedSuggestions[openRescheduleDate]) {
      setOpenRescheduleDate('');
    }
  }, [groupedSuggestions, openRescheduleDate]);

  const batchById = React.useMemo(() => {
    const map = new Map();
    batchList.forEach((batch) => map.set(String(batch.id), batch));
    return map;
  }, [batchList]);

  const selectedRescheduleBatch = batchById.get(String(rescheduleBatchId));
  const selectedWeekday = React.useMemo(() => weekdayFromInputDate(debouncedDate), [debouncedDate]);
  const selectedDayLabel = React.useMemo(() => shortWeekdayLabelFromInputDate(debouncedDate), [debouncedDate]);
  const availableBatchesForDay = React.useMemo(() => {
    return batchList.filter((batch) => {
      const effective = batch?.effective_schedule_for_date;
      if (effective) {
        return Boolean(effective.start_time) && !Boolean(effective.cancelled);
      }
      const schedules = Array.isArray(batch?.schedules) ? batch.schedules : [];
      if (!schedules.length) return false;
      return schedules.some((row) => Number(row?.weekday) === selectedWeekday);
    });
  }, [batchList, selectedWeekday]);
  const availableBatchIdsForDay = React.useMemo(() => {
    return new Set(availableBatchesForDay.map((row) => Number(row.id)));
  }, [availableBatchesForDay]);
  const displayBatchesForSelection = React.useMemo(() => {
    return availableBatchesForDay.length > 0 ? availableBatchesForDay : batchList;
  }, [availableBatchesForDay, batchList]);
  const displayBatchIdsForSelection = React.useMemo(() => {
    return new Set(displayBatchesForSelection.map((row) => Number(row.id)));
  }, [displayBatchesForSelection]);
  const capacityRowsForDay = React.useMemo(() => {
    return capacityRows.filter((row) => availableBatchIdsForDay.has(Number(row.batch_id)));
  }, [capacityRows, availableBatchIdsForDay]);
  const displayCapacityRows = React.useMemo(() => {
    return capacityRowsForDay.length > 0 ? capacityRowsForDay : capacityRows;
  }, [capacityRowsForDay, capacityRows]);
  const selectedDayLong = React.useMemo(() => longDate(debouncedDate), [debouncedDate]);

  React.useEffect(() => {
    if (!rescheduleBatchId) return;
    if (!displayBatchIdsForSelection.has(Number(rescheduleBatchId))) {
      dispatch(setRescheduleBatchId(''));
      dispatch(loadRescheduleRequested({ batchId: '', date: debouncedDate, weeksVisible: 1 }));
    }
  }, [debouncedDate, dispatch, displayBatchIdsForSelection, rescheduleBatchId]);
  const currentBatchSchedule = React.useMemo(() => {
    const effective = selectedRescheduleBatch?.effective_schedule_for_date;
    if (effective) {
      if (effective.start_time) {
        return `${selectedDayLabel || 'Selected day'} ${effective.start_time}${effective.source === 'override' ? ' (override)' : ''}`;
      }
      if (effective.cancelled) return 'Cancelled for selected day (override)';
    }
    const rows = Array.isArray(selectedRescheduleBatch?.schedules) ? selectedRescheduleBatch.schedules : [];
    if (!rows.length) return 'Not available';
    const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    const matched = rows.find((row) => Number(row.weekday) === selectedWeekday);
    if (matched) {
      return `${selectedDayLabel || dayNames[selectedWeekday] || 'Day'} ${matched.start_time || '--:--'}`;
    }
    return `No regular class on ${selectedDayLabel || dayNames[selectedWeekday] || 'selected day'}`;
  }, [selectedRescheduleBatch, selectedWeekday, selectedDayLabel]);

  const patchAvailabilityAfterSchedule = React.useCallback((slot, batch) => {
    if (!slot) return;
    const duration = resolveOverrideDurationMinutes({
      selectedFree: slot,
      selectedBatch: batch,
      inputDate: debouncedDate
    });
    const endTime = addMinutesToTime(slot.start_time, duration);
    dispatch(convertFreeToBusy({
      freeStart: slot.start_time,
      freeEnd: slot.end_time,
      busySlot: {
        start_time: slot.start_time,
        end_time: endTime,
        minutes: duration,
        reason: `Scheduled: ${batch?.name || 'Batch'}`,
        type: 'busy',
        source: 'calendar_override',
        batch_name: batch?.name || '',
      },
    }));
  }, [debouncedDate, dispatch]);

  const onSelectSlot = React.useCallback((slot) => {
    setSelectedSlot(slot);
    setDrawerAction(defaultActionTypeForSlot(slot));
    setBlockForm((prev) => ({
      ...prev,
      start: slot?.start_time || prev.start,
      end: slot?.end_time || prev.end
    }));
    setDrawerOpen(true);
  }, []);

  const onCreateBlock = React.useCallback(async () => {
    if (!blockForm.start || !blockForm.end) return;
    const tempId = `tmp-${Date.now()}`;
    const optimistic = {
      id: tempId,
      start: `${debouncedDate}T${blockForm.start}:00`,
      end: `${debouncedDate}T${blockForm.end}:00`,
      start_time: blockForm.start,
      end_time: blockForm.end,
      minutes: Math.max(0, timeToMinutes(blockForm.end) - timeToMinutes(blockForm.start)),
      type: 'blocked',
      source: 'teacher_block',
      reason: blockForm.reason || ''
    };
    dispatch(addBusySlot(optimistic));
    setSaving(true);
    dispatch(createTimeBlockRequested({
      body: {
        date: debouncedDate,
        start_time: blockForm.start,
        end_time: blockForm.end,
        reason: blockForm.reason,
      },
      onSuccess: (row) => {
        dispatch(replaceBusySlot({
          tempId,
          nextSlot: { id: row?.id, minutes: row?.minutes || optimistic.minutes },
        }));
        dispatch(apiErrorToastReceived({ tone: 'success', message: 'Personal time blocked.' }));
        setDrawerOpen(false);
        setSaving(false);
      },
      onError: () => {
        dispatch(removeBusySlotById(tempId));
        setSaving(false);
      },
    }));
  }, [blockForm.end, blockForm.reason, blockForm.start, debouncedDate, dispatch]);

  const onDeleteBlocked = React.useCallback(async (slot) => {
    if (!slot?.id || String(slot.id).startsWith('tmp-')) return;
    const snapshot = slot;
    dispatch(removeBusySlotById(slot.id));
    dispatch(deleteTimeBlockRequested({
      blockId: slot.id,
      onSuccess: () => {
        dispatch(apiErrorToastReceived({ tone: 'success', message: 'Personal block removed.' }));
      },
      onError: () => {
        dispatch(addBusySlot(snapshot));
      },
    }));
  }, [dispatch]);

  const onScheduleFromFreeSlot = React.useCallback(async () => {
    if (!selectedSlot || !scheduleBatchId) return;
    const selectedBatch = batchById.get(String(scheduleBatchId));
    const overrideDurationMinutes = resolveOverrideDurationMinutes({
      selectedFree: selectedSlot,
      selectedBatch,
      inputDate: debouncedDate
    });
    setSaving(true);
    dispatch(createOverrideRequested({
      body: {
        batch_id: Number(scheduleBatchId),
        override_date: debouncedDate,
        new_start_time: selectedSlot.start_time,
        new_duration_minutes: overrideDurationMinutes,
        cancelled: false,
        reason: 'Scheduled from Time & Capacity free slot',
      },
      onSuccess: () => {
        patchAvailabilityAfterSchedule(selectedSlot, selectedBatch);
        dispatch(apiErrorToastReceived({ tone: 'success', message: 'Schedule updated.' }));
        setSelectedSlot(null);
        setScheduleBatchId('');
        setDrawerOpen(false);
        setSaving(false);
      },
      onError: () => {
        setSaving(false);
      },
    }));
  }, [batchById, debouncedDate, patchAvailabilityAfterSchedule, scheduleBatchId, selectedSlot]);

  const onOpenRescheduleFromDrawer = React.useCallback(() => {
    if (scheduleBatchId) dispatch(setRescheduleBatchId(scheduleBatchId));
    dispatch(setActiveTab('reschedule'));
    setDrawerOpen(false);
    dispatch(apiErrorToastReceived({ tone: 'info', message: 'Select batch and confirm a suggested slot.' }));
  }, [dispatch, scheduleBatchId]);

  const onManageBatches = React.useCallback(() => {
    navigate('/batches');
  }, [navigate]);

  const weeklyTotalHours = minutesToHoursLabel(weeklyLoad.total_weekly_minutes || 0);

  return (
    <section className="space-y-5">
      <div className="time-capacity-hero rounded-2xl border border-slate-200 p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold text-slate-900">Time & Capacity</h2>
            <p className="text-sm text-slate-600">Availability, seat utilization, smart reschedule options, and weekly workload.</p>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="date"
              value={dateValue}
              onChange={(event) => dispatch(setDateValue(event.target.value))}
              className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
            />
            <button
              type="button"
              onClick={() => setHelpOpen(true)}
              className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-slate-300 bg-white text-slate-700 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
              aria-label="Time and capacity guide"
              title="Help"
            >
              <FiHelpCircle className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      <div className="time-capacity-tabbar flex flex-wrap gap-2">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => dispatch(setActiveTab(tab.key))}
            className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
              activeTab === tab.key ? 'bg-[#2f7bf6] text-white' : 'bg-white text-slate-600 hover:bg-slate-100'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {activeTab === 'availability' ? (
          <motion.div key="availability" {...cardMotion} transition={{ duration: reducedMotion ? 0 : 0.2 }} className="space-y-4">
            <Legend items={SLOT_LEGEND} stickyMobile />
            <div className="grid gap-4 lg:grid-cols-[2fr,1fr]">
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="text-sm font-bold text-slate-800">Daily Slots</h3>
                  {availabilityLoading ? <p className="text-xs text-slate-500">Loading...</p> : null}
                </div>
                <div className="time-capacity-grid max-h-[460px] space-y-2 overflow-auto pr-1">
                  {mergedSlots.map((slot, index) => (
                    <SlotItem
                      key={`${slot.start_time || slot.start}-${slot.end_time || slot.end}-${index}`}
                      slot={slot}
                      reducedMotion={Boolean(reducedMotion)}
                      onSelectSlot={onSelectSlot}
                      onInspectSlot={setInspectSlot}
                      onDeleteBlocked={onDeleteBlocked}
                    />
                  ))}
                  {!availabilityLoading && mergedSlots.length === 0 ? (
                    <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">
                      All slots are busy. Adjust working hours or remove blocks.
                    </div>
                  ) : null}
                </div>
              </div>
              <div className="space-y-4">
                <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                  <h3 className="text-sm font-bold text-slate-800">Summary</h3>
                  <p className="mt-2 text-xs text-slate-600">Busy: {availability?.total_busy_minutes || 0} min</p>
                  <p className="text-xs text-slate-600">Free: {availability?.total_free_minutes || 0} min</p>
                  <p className="mt-2 text-xs text-slate-500">Click a slot to open the action drawer and confirm the action.</p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                  <h3 className="text-sm font-bold text-slate-800">Quick Block</h3>
                  <p className="mt-1 text-xs text-slate-500">Use slot drawer for guided flow. Quick block is optional.</p>
                  <div className="mt-2 grid grid-cols-2 gap-2">
                    <input
                      type="time"
                      value={blockForm.start}
                      onChange={(event) => setBlockForm((prev) => ({ ...prev, start: event.target.value }))}
                      className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                    />
                    <input
                      type="time"
                      value={blockForm.end}
                      onChange={(event) => setBlockForm((prev) => ({ ...prev, end: event.target.value }))}
                      className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                    />
                  </div>
                  <input
                    type="text"
                    value={blockForm.reason}
                    onChange={(event) => setBlockForm((prev) => ({ ...prev, reason: event.target.value }))}
                    placeholder="Reason"
                    className="mt-2 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                  />
                  <button
                    type="button"
                    disabled={saving}
                    onClick={() => setPendingConfirm({ type: 'block' })}
                    className="mt-2 w-full rounded-lg bg-slate-800 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
                  >
                    Confirm block
                  </button>
                </div>
              </div>
            </div>
          </motion.div>
        ) : null}

        {activeTab === 'capacity' ? (
          <motion.div key="capacity" {...cardMotion} transition={{ duration: reducedMotion ? 0 : 0.2 }} className="space-y-4">
            <Legend items={CAPACITY_LEGEND} />
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {displayCapacityRows.map((row) => {
                const batch = batchById.get(String(row.batch_id));
                const scheduleRows = Array.isArray(batch?.schedules) ? batch.schedules : [];
                const effective = batch?.effective_schedule_for_date;
                const scheduleLabel = effective && effective.start_time
                  ? `${selectedDayLabel} ${effective.start_time}${effective.source === 'override' ? ' (override)' : ''}`
                  : scheduleRows.length
                    ? scheduleRows
                        .slice(0, 2)
                        .map((s) => `${['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][Number(s.weekday) || 0]} ${s.start_time || '--:--'}`)
                        .join(' | ')
                    : 'Not available';
                return (
                  <motion.div
                    key={row.batch_id}
                    initial={reducedMotion ? false : { opacity: 0, y: 10 }}
                    animate={reducedMotion ? undefined : { opacity: 1, y: 0 }}
                    className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
                  >
                    <p className="text-base font-bold text-slate-800">{row.name}</p>
                    <p className="mt-1 text-xs text-slate-500">Subject: {batch?.subject || row.subject || 'General'}</p>
                    <p className="mt-1 text-xs text-slate-500">Current Schedule: {scheduleLabel}</p>
                    <p className="mt-2 text-sm text-slate-600">Max Students: {row.max_students ?? 'Unlimited'}</p>
                    <p className="text-sm text-slate-600">Enrolled: {row.enrolled_students}</p>
                    <p className="text-sm text-slate-600" title="Seats left = max_students - enrolled_students">
                      Seats Left: {row.available_seats ?? 'Unlimited'}
                    </p>
                    <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                      <motion.div
                        initial={false}
                        animate={{ width: `${Math.max(0, Math.min(100, row.utilization_percentage || 0))}%` }}
                        transition={{ duration: reducedMotion ? 0 : 0.3, ease: 'easeOut' }}
                        className={`h-full ${utilizationTone(row.utilization_percentage || 0)}`}
                      />
                    </div>
                    <p className="mt-2 text-xs font-semibold text-slate-600">{row.utilization_percentage || 0}% utilization</p>
                  </motion.div>
                );
              })}
              {!capacityLoading && capacityRowsForDay.length === 0 && capacityRows.length > 0 ? (
                <div className="md:col-span-2 xl:col-span-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-800">
                  No batch has a schedule on {selectedDayLong}. Showing all active batches.
                </div>
              ) : null}
              {!capacityLoading && displayCapacityRows.length === 0 ? (
                <EmptyStateNotice
                  message="No active batch data available for Batch Capacity."
                  onManageBatches={onManageBatches}
                />
              ) : null}
            </div>
          </motion.div>
        ) : null}

        {activeTab === 'reschedule' ? (
          <motion.div key="reschedule" {...cardMotion} transition={{ duration: reducedMotion ? 0 : 0.2 }} className="space-y-3 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-700 dark:bg-slate-900">
            <div className="flex flex-wrap items-center gap-2">
              <select
                value={rescheduleBatchId}
                onChange={(event) => dispatch(setRescheduleBatchId(event.target.value))}
                className="w-full max-w-sm rounded-xl border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
              >
                <option value="">Select batch</option>
                {displayBatchesForSelection.map((batch) => (
                  <option key={batch.id} value={batch.id}>
                    {batch.name}
                  </option>
                ))}
              </select>
              {rescheduleBatchId ? (
                <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                  {rescheduleRows.length} options
                </span>
              ) : null}
              {rescheduleLoading ? <span className="text-xs text-slate-500 dark:text-slate-400">Loading suggestions...</span> : null}
            </div>

            {!rescheduleLoading && availableBatchesForDay.length === 0 ? (
              <EmptyStateNotice
                message={`No Batch Available on this Day ${selectedDayLong}. Showing all active batches for reschedule suggestions.`}
                onManageBatches={onManageBatches}
              />
            ) : null}

            {selectedRescheduleBatch ? (
              <div className="rounded-xl border border-amber-200 bg-amber-50/90 p-3 dark:border-amber-700 dark:bg-amber-900/20">
                <div className="mb-2 flex items-center gap-2">
                  <FiZap className="h-4 w-4 text-amber-700 dark:text-amber-300" />
                  <p className="text-sm font-bold text-amber-900 dark:text-amber-200">Rescheduling Batch</p>
                </div>
                <div className="grid gap-2 sm:grid-cols-3">
                  <div className="rounded-lg bg-white/70 px-2 py-1.5 text-xs dark:bg-slate-900/40">
                    <p className="text-[10px] uppercase tracking-wide text-amber-700/80 dark:text-amber-300/90">Name</p>
                    <p className="font-semibold text-amber-900 dark:text-amber-100">{selectedRescheduleBatch.name}</p>
                  </div>
                  <div className="rounded-lg bg-white/70 px-2 py-1.5 text-xs dark:bg-slate-900/40">
                    <p className="text-[10px] uppercase tracking-wide text-amber-700/80 dark:text-amber-300/90">Current Time</p>
                    <p className="font-semibold text-amber-900 dark:text-amber-100">{currentBatchSchedule}</p>
                  </div>
                  <div className="rounded-lg bg-white/70 px-2 py-1.5 text-xs dark:bg-slate-900/40">
                    <p className="text-[10px] uppercase tracking-wide text-amber-700/80 dark:text-amber-300/90">Duration</p>
                    <p className="font-semibold text-amber-900 dark:text-amber-100">{selectedRescheduleBatch.default_duration_minutes || 60} mins</p>
                  </div>
                </div>
              </div>
            ) : null}

            {!rescheduleBatchId ? (
              <p className="text-sm text-slate-500 dark:text-slate-400">Select a batch to view smart suggestions.</p>
            ) : null}

            {rescheduleBatchId && Object.keys(groupedSuggestions).length === 0 ? (
              <p className="text-sm text-slate-500 dark:text-slate-400">No suggested slots for this range.</p>
            ) : null}

            {rescheduleBatchId ? (
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">
                  Showing {rescheduleWeeksVisible} week{rescheduleWeeksVisible > 1 ? 's' : ''} of suggestions
                </p>
                <button
                  type="button"
                  onClick={() => dispatch(setRescheduleWeeksVisible(rescheduleWeeksVisible + 1))}
                  disabled={rescheduleLoading}
                  className="inline-flex items-center gap-1.5 rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:-translate-y-0.5 hover:shadow disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                >
                  <FiPlusCircle className="h-3.5 w-3.5" />
                  {rescheduleLoading ? 'Loading...' : 'Load Next 7 Days'}
                </button>
              </div>
            ) : null}

            <div className="space-y-2">
              {Object.entries(groupedSuggestions).map(([groupDate, rows]) => (
                <div key={groupDate} className="rounded-xl border border-slate-200 bg-slate-50 p-2.5 dark:border-slate-700 dark:bg-slate-800/70">
                  <button
                    type="button"
                    onClick={() =>
                      setOpenRescheduleDate((prev) => (prev === groupDate ? '' : groupDate))
                    }
                    className="flex w-full items-center justify-between rounded-lg px-1 py-1 text-left"
                  >
                    <span className="inline-flex items-center gap-1.5 text-sm font-bold text-slate-700 dark:text-slate-100">
                      <FiCalendar className="h-3.5 w-3.5" />
                      {prettyDate(groupDate)}
                    </span>
                    <span className="inline-flex items-center gap-2">
                      <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-semibold text-slate-500 dark:bg-slate-900 dark:text-slate-300">
                        {rows.length} slots
                      </span>
                      <FiChevronDown
                        className={`h-4 w-4 text-slate-500 transition-transform ${
                          openRescheduleDate === groupDate ? 'rotate-180' : ''
                        }`}
                      />
                    </span>
                  </button>
                  {openRescheduleDate === groupDate ? (
                    <div className="mt-2 space-y-1.5">
                      {rows.map((row, index) => {
                        const isBest = row.is_best_earliest || row.is_best_low_load;
                        return (
                          <button
                            key={`${row.start || row.start_time}-${index}`}
                            type="button"
                            onClick={() => setRescheduleConfirm(row)}
                            className={`time-capacity-reschedule-option flex w-full items-center justify-between rounded-lg border px-2.5 py-2 text-left transition hover:-translate-y-0.5 ${
                              isBest
                                ? 'border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-600 dark:bg-amber-900/25 dark:text-amber-200'
                                : 'border-slate-300 bg-white text-slate-700 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100'
                            }`}
                          >
                            <span className="min-w-0">
                              <span className="inline-flex items-center gap-1.5 text-sm font-semibold">
                                <FiClock className="h-3.5 w-3.5" />
                                {row.start_time} - {row.end_time}
                                {isBest ? <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-700 dark:bg-amber-700/30 dark:text-amber-200">Best</span> : null}
                              </span>
                              <span className="mt-0.5 block text-[11px] font-medium text-slate-500 dark:text-slate-400">No conflict + low daily load</span>
                            </span>
                            <FiArrowRight className="h-4 w-4 shrink-0 opacity-70" />
                          </button>
                        );
                      })}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          </motion.div>
        ) : null}

        {activeTab === 'weekly' ? (
          <motion.div key="weekly" {...cardMotion} transition={{ duration: reducedMotion ? 0 : 0.2 }} className="space-y-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-sm text-slate-600">
              Weekly Load shows total teaching hours per day.
              {weeklyLoading ? ' Loading...' : ''}
            </p>
            <div className="grid gap-2 sm:grid-cols-3">
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs text-slate-500">Total Hours</p>
                <p className="text-xl font-bold text-slate-800">{weeklyTotalHours}</p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs text-slate-500">Utilization</p>
                <p className="text-xl font-bold text-slate-800">{weeklyLoad.utilization_percentage || 0}%</p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs text-slate-500">Free Utilization</p>
                <p className="text-xl font-bold text-slate-800">{weeklyLoad.free_utilization_percentage || 0}%</p>
              </div>
            </div>
            <div className="time-capacity-bars">
              {(weeklyLoad.daily_hours || []).map((row) => {
                const base = Number(weeklyLoad.work_minutes_per_day || 600);
                const percent = Math.max(0, Math.min(100, ((row.total_minutes || 0) / (base || 1)) * 100));
                const label = `${new Date(`${row.date}T00:00:00`).toLocaleDateString(undefined, { weekday: 'long' })}: ${minutesToHoursLabel(row.total_minutes || 0)} scheduled`;
                return (
                  <div key={row.date} className="time-capacity-bar-row" title={label}>
                    <span className="time-capacity-label">{row.date.slice(5)}</span>
                    <div className="time-capacity-track">
                      <motion.div
                        className="time-capacity-fill"
                        initial={false}
                        animate={{ width: `${percent}%` }}
                        transition={{ duration: reducedMotion ? 0 : 0.3 }}
                      />
                    </div>
                    <span className="time-capacity-value">{minutesToHoursLabel(row.total_minutes || 0)}</span>
                  </div>
                );
              })}
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <SlotDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        selectedSlot={selectedSlot}
        selectedDate={debouncedDate}
        actionType={drawerAction}
        onActionTypeChange={setDrawerAction}
        batchList={batchList}
        scheduleBatchId={scheduleBatchId}
        onScheduleBatchChange={setScheduleBatchId}
        blockForm={blockForm}
        onBlockFormChange={setBlockForm}
        onConfirmSchedule={() => setPendingConfirm({ type: 'schedule' })}
        onGoReschedule={onOpenRescheduleFromDrawer}
        onConfirmBlock={() => setPendingConfirm({ type: 'block' })}
        saving={saving}
      />

      <ConfirmationModal
        open={Boolean(inspectSlot)}
        title="Slot Details"
        description={inspectSlot ? `Time: ${inspectSlot.start_time} - ${inspectSlot.end_time}\nStatus: ${slotStatusLabel(inspectSlot)}\nBatch: ${inspectSlot.type === 'free' ? 'N/A' : slotBatchName(inspectSlot)}\nDuration: ${inspectSlot.minutes} mins` : ''}
        confirmLabel="Close"
        onConfirm={() => setInspectSlot(null)}
        onCancel={() => setInspectSlot(null)}
        hideCancel
      />

      <ConfirmationModal
        open={helpOpen}
        title="Time & Capacity Guide"
        description={'Availability shows free, busy, and blocked time for your selected day. Reschedule Assistant suggests conflict-free options grouped by date. Batch Capacity shows seats used and remaining seats based on enrolled students.'}
        confirmLabel="Got it"
        onConfirm={() => setHelpOpen(false)}
        onCancel={() => setHelpOpen(false)}
        hideCancel
      />

      <ConfirmationModal
        open={pendingConfirm?.type === 'schedule'}
        title="Confirm Schedule"
        description={
          selectedSlot && scheduleBatchId
            ? `Schedule ${batchById.get(String(scheduleBatchId))?.name || 'selected batch'} on ${prettyDate(debouncedDate)} at ${selectedSlot.start_time}?`
            : 'Select a batch and slot before confirming.'
        }
        confirmLabel="Schedule"
        onConfirm={async () => {
          setPendingConfirm(null);
          await onScheduleFromFreeSlot();
        }}
        onCancel={() => setPendingConfirm(null)}
        busy={saving}
      />

      <ConfirmationModal
        open={pendingConfirm?.type === 'block'}
        title="Confirm Personal Block"
        description={`Block personal time on ${prettyDate(debouncedDate)} from ${blockForm.start} to ${blockForm.end}?`}
        confirmLabel="Block Time"
        onConfirm={async () => {
          setPendingConfirm(null);
          await onCreateBlock();
        }}
        onCancel={() => setPendingConfirm(null)}
        busy={saving}
      />

      <ConfirmationModal
        open={Boolean(rescheduleConfirm)}
        title="Confirm Reschedule"
        description={
          rescheduleConfirm
            ? `Move ${selectedRescheduleBatch?.name || 'batch'} from ${currentBatchSchedule} to ${prettyDate(rescheduleConfirm.date)} ${rescheduleConfirm.start_time}?`
            : ''
        }
        confirmLabel="Move Batch"
        onConfirm={async () => {
          if (!rescheduleConfirm || !rescheduleBatchId) return;
          const row = rescheduleConfirm;
          setSaving(true);
          const safeDuration = Math.max(1, Math.min(300, Number(row.duration_minutes || 60)));
          dispatch(createOverrideRequested({
            body: {
              batch_id: Number(rescheduleBatchId),
              override_date: row.date,
              new_start_time: row.start_time,
              new_duration_minutes: safeDuration,
              reason: 'Rescheduled via assistant',
              cancelled: false,
            },
            onSuccess: () => {
              dispatch(removeRescheduleRowsByStart(row.start));
              dispatch(apiErrorToastReceived({ tone: 'success', message: 'Batch successfully moved.' }));
              if (row.date === debouncedDate) {
                dispatch(convertFreeToBusy({
                  freeStart: row.start_time,
                  freeEnd: row.end_time,
                  busySlot: {
                    start_time: row.start_time,
                    end_time: row.end_time,
                    minutes: row.duration_minutes || 60,
                    type: 'busy',
                    source: 'calendar_override',
                    batch_name: selectedRescheduleBatch?.name || '',
                  },
                }));
              }
              setSaving(false);
              setRescheduleConfirm(null);
            },
            onError: () => {
              setSaving(false);
              setRescheduleConfirm(null);
            },
          }));
        }}
        onCancel={() => setRescheduleConfirm(null)}
        busy={saving}
      />
    </section>
  );
}

export default TimeCapacity;
