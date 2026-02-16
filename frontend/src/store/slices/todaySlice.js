import { createSlice } from '@reduxjs/toolkit';

const todaySlice = createSlice({
  name: 'today',
  initialState: {
    loading: false,
    error: '',
    data: null,
    teacherFilter: '',
    resolvingActionId: null,
  },
  reducers: {
    loadRequested(state) {
      state.loading = true;
      state.error = '';
    },
    loadSucceeded(state, action) {
      state.loading = false;
      state.error = '';
      state.data = action.payload || null;
    },
    loadFailed(state, action) {
      state.loading = false;
      state.error = String(action.payload || "Failed to load today's actions.");
    },
    setTeacherFilter(state, action) {
      state.teacherFilter = String(action.payload || '');
    },
    resolveActionRequested(state, action) {
      state.resolvingActionId = Number(action.payload?.actionId || 0) || null;
      state.error = '';
    },
    resolveActionSucceeded(state, action) {
      state.resolvingActionId = null;
      state.error = '';
      const resolvedId = Number(action.payload?.actionId || 0) || null;
      const incomingData = action.payload && Object.prototype.hasOwnProperty.call(action.payload, 'data')
        ? action.payload.data
        : (action.payload || null);
      state.data = incomingData || state.data || null;

      if (!resolvedId || !state.data) {
        return;
      }

      const overdueActions = Array.isArray(state.data.overdue_actions) ? state.data.overdue_actions : [];
      const dueTodayActions = Array.isArray(state.data.due_today_actions) ? state.data.due_today_actions : [];
      const completedToday = Array.isArray(state.data.completed_today) ? state.data.completed_today : [];

      const resolvedFromOverdue = overdueActions.find((row) => Number(row?.id) === resolvedId);
      const resolvedFromDue = dueTodayActions.find((row) => Number(row?.id) === resolvedId);
      const resolvedAction = resolvedFromOverdue || resolvedFromDue;

      state.data.overdue_actions = overdueActions.filter((row) => Number(row?.id) !== resolvedId);
      state.data.due_today_actions = dueTodayActions.filter((row) => Number(row?.id) !== resolvedId);

      const alreadyInCompleted = completedToday.some((row) => Number(row?.id) === resolvedId);
      if (!alreadyInCompleted && resolvedAction) {
        state.data.completed_today = [
          {
            ...resolvedAction,
            resolution_note: resolvedAction.resolution_note || 'Resolved from Today View',
          },
          ...completedToday,
        ];
      }
    },
    resolveActionFailed(state, action) {
      state.resolvingActionId = null;
      state.error = String(action.payload || 'Failed to resolve action.');
    },
  },
});

export const {
  loadRequested,
  loadSucceeded,
  loadFailed,
  setTeacherFilter,
  resolveActionRequested,
  resolveActionSucceeded,
  resolveActionFailed,
} = todaySlice.actions;

export default todaySlice.reducer;
