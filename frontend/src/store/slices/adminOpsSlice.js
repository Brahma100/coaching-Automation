import { createSlice } from '@reduxjs/toolkit';

const initialCollapsed = {
  alerts: false,
  teachers: false,
  batches: false,
  risk: false,
  automation: false,
};

const adminOpsSlice = createSlice({
  name: 'adminOps',
  initialState: {
    loading: true,
    error: '',
    errorStatus: null,
    data: null,
    updatedAt: null,
    collapsed: initialCollapsed,
  },
  reducers: {
    loadRequested(state) {
      state.loading = true;
      state.error = '';
      state.errorStatus = null;
    },
    loadSucceeded(state, action) {
      const payload = action.payload || {};
      state.loading = false;
      state.error = '';
      state.errorStatus = null;
      state.data = payload.data || null;
      state.updatedAt = payload.updatedAt || null;
    },
    loadFailed(state, action) {
      const payload = action.payload || {};
      state.loading = false;
      state.error = String(payload.message || 'Could not load operations dashboard');
      state.errorStatus = Number(payload.status) || null;
    },
    toggleSection(state, action) {
      const key = String(action.payload || '');
      if (!Object.prototype.hasOwnProperty.call(state.collapsed, key)) return;
      state.collapsed[key] = !state.collapsed[key];
    },
  },
});

export const {
  loadRequested,
  loadSucceeded,
  loadFailed,
  toggleSection,
} = adminOpsSlice.actions;

export default adminOpsSlice.reducer;
