import { createSlice } from '@reduxjs/toolkit';

const appSlice = createSlice({
  name: 'app',
  initialState: {
    toastEvent: null,
  },
  reducers: {
    apiErrorToastReceived(state, action) {
      const payload = action.payload || {};
      state.toastEvent = {
        tone: payload.tone || 'error',
        message: payload.message || 'Request failed',
        duration: payload.duration || 5000,
        nonce: Date.now(),
      };
    },
    clearToastEvent(state) {
      state.toastEvent = null;
    },
  },
});

export const { apiErrorToastReceived, clearToastEvent } = appSlice.actions;
export default appSlice.reducer;
