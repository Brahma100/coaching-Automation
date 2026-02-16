import { createSlice } from '@reduxjs/toolkit';

const brainSlice = createSlice({
  name: 'brain',
  initialState: {
    loading: false,
    error: '',
    data: null,
    lastLoadedAt: '',
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
      state.lastLoadedAt = new Date().toISOString();
    },
    loadFailed(state, action) {
      state.loading = false;
      state.error = String(action.payload || 'Failed to load operational brain');
    },
  },
});

export const {
  loadRequested,
  loadSucceeded,
  loadFailed,
} = brainSlice.actions;

export default brainSlice.reducer;
