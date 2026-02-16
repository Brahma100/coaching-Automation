import { createSlice } from '@reduxjs/toolkit';

function toTodayInput() {
  return new Date().toISOString().slice(0, 10);
}

const initialState = {
  activeTab: 'availability',
  dateValue: toTodayInput(),
  debouncedDate: toTodayInput(),
  availability: { busy_slots: [], free_slots: [] },
  capacityRows: [],
  weeklyLoad: { daily_hours: [] },
  batchList: [],
  rescheduleBatchId: '',
  rescheduleRows: [],
  rescheduleWeeksVisible: 1,
  availabilityLoading: false,
  capacityLoading: false,
  rescheduleLoading: false,
  weeklyLoading: false,
  syncTick: 0,
};

const timeCapacitySlice = createSlice({
  name: 'timeCapacity',
  initialState,
  reducers: {
    setActiveTab(state, action) {
      state.activeTab = String(action.payload || 'availability');
    },
    setDateValue(state, action) {
      state.dateValue = String(action.payload || toTodayInput());
    },
    setDebouncedDate(state, action) {
      state.debouncedDate = String(action.payload || toTodayInput());
    },
    setRescheduleBatchId(state, action) {
      state.rescheduleBatchId = String(action.payload || '');
    },
    setRescheduleWeeksVisible(state, action) {
      const value = Number(action.payload || 1);
      state.rescheduleWeeksVisible = Math.max(1, value);
    },
    incrementSyncTick(state) {
      state.syncTick += 1;
    },

    loadBatchesRequested() {},
    loadBatchesSucceeded(state, action) {
      state.batchList = Array.isArray(action.payload) ? action.payload : [];
    },
    loadBatchesFailed(state) {
      state.batchList = [];
    },

    loadAvailabilityRequested(state) {
      state.availabilityLoading = true;
    },
    loadAvailabilitySucceeded(state, action) {
      state.availabilityLoading = false;
      state.availability = action.payload || { busy_slots: [], free_slots: [] };
    },
    loadAvailabilityFailed(state) {
      state.availabilityLoading = false;
      state.availability = { busy_slots: [], free_slots: [] };
    },

    loadCapacityRequested(state) {
      state.capacityLoading = true;
    },
    loadCapacitySucceeded(state, action) {
      state.capacityLoading = false;
      state.capacityRows = Array.isArray(action.payload) ? action.payload : [];
    },
    loadCapacityFailed(state) {
      state.capacityLoading = false;
      state.capacityRows = [];
    },

    loadRescheduleRequested(state) {
      state.rescheduleLoading = true;
    },
    loadRescheduleSucceeded(state, action) {
      state.rescheduleLoading = false;
      state.rescheduleRows = Array.isArray(action.payload) ? action.payload : [];
    },
    loadRescheduleFailed(state) {
      state.rescheduleLoading = false;
      state.rescheduleRows = [];
    },

    loadWeeklyRequested(state) {
      state.weeklyLoading = true;
    },
    loadWeeklySucceeded(state, action) {
      state.weeklyLoading = false;
      state.weeklyLoad = action.payload || { daily_hours: [] };
    },
    loadWeeklyFailed(state) {
      state.weeklyLoading = false;
      state.weeklyLoad = { daily_hours: [] };
    },

    addBusySlot(state, action) {
      const slot = action.payload;
      if (!slot) return;
      state.availability = {
        ...(state.availability || {}),
        busy_slots: [...(state.availability?.busy_slots || []), slot],
      };
    },
    removeBusySlotById(state, action) {
      const targetId = action.payload;
      state.availability = {
        ...(state.availability || {}),
        busy_slots: (state.availability?.busy_slots || []).filter((row) => row.id !== targetId),
      };
    },
    replaceBusySlot(state, action) {
      const payload = action.payload || {};
      const tempId = payload.tempId;
      const nextSlot = payload.nextSlot;
      if (!tempId || !nextSlot) return;
      state.availability = {
        ...(state.availability || {}),
        busy_slots: (state.availability?.busy_slots || []).map((row) => (
          row.id === tempId ? { ...row, ...nextSlot } : row
        )),
      };
    },
    convertFreeToBusy(state, action) {
      const payload = action.payload || {};
      const freeStart = payload.freeStart;
      const freeEnd = payload.freeEnd;
      const busySlot = payload.busySlot;
      if (!busySlot) return;
      const freeSlots = (state.availability?.free_slots || []).filter((row) => !(
        row.start_time === freeStart && row.end_time === freeEnd
      ));
      state.availability = {
        ...(state.availability || {}),
        free_slots: freeSlots,
        busy_slots: [...(state.availability?.busy_slots || []), busySlot],
      };
    },
    removeRescheduleRowsByStart(state, action) {
      const start = String(action.payload || '');
      state.rescheduleRows = (state.rescheduleRows || []).filter((item) => String(item.start || '') !== start);
    },
    createTimeBlockRequested() {},
    deleteTimeBlockRequested() {},
    createOverrideRequested() {},
  },
});

export const {
  setActiveTab,
  setDateValue,
  setDebouncedDate,
  setRescheduleBatchId,
  setRescheduleWeeksVisible,
  incrementSyncTick,
  loadBatchesRequested,
  loadBatchesSucceeded,
  loadBatchesFailed,
  loadAvailabilityRequested,
  loadAvailabilitySucceeded,
  loadAvailabilityFailed,
  loadCapacityRequested,
  loadCapacitySucceeded,
  loadCapacityFailed,
  loadRescheduleRequested,
  loadRescheduleSucceeded,
  loadRescheduleFailed,
  loadWeeklyRequested,
  loadWeeklySucceeded,
  loadWeeklyFailed,
  addBusySlot,
  removeBusySlotById,
  replaceBusySlot,
  convertFreeToBusy,
  removeRescheduleRowsByStart,
  createTimeBlockRequested,
  deleteTimeBlockRequested,
  createOverrideRequested,
} = timeCapacitySlice.actions;

export default timeCapacitySlice.reducer;
