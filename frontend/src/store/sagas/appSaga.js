import { eventChannel } from 'redux-saga';
import { call, fork, put, take } from 'redux-saga/effects';

import { setGlobalApiErrorNotifier } from '../../services/api';
import { apiErrorToastReceived } from '../slices/appSlice.js';

function createApiErrorChannel() {
  return eventChannel((emit) => {
    setGlobalApiErrorNotifier((payload) => {
      emit(payload || {});
    });
    return () => {
      setGlobalApiErrorNotifier(null);
    };
  });
}

function* watchApiErrorToasts() {
  const channel = yield call(createApiErrorChannel);
  try {
    while (true) {
      const payload = yield take(channel);
      yield put(apiErrorToastReceived(payload));
    }
  } finally {
    channel.close();
  }
}

export default function* appSaga() {
  yield fork(watchApiErrorToasts);
}
