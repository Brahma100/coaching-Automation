import React from 'react';

import Toast from './Toast.jsx';

function GlobalToastHost({ event, onDone }) {
  return (
    <Toast
      open={Boolean(event)}
      tone={event?.tone || 'error'}
      message={event?.message || ''}
      duration={event?.duration || 5000}
      onClose={onDone}
    />
  );
}

export default GlobalToastHost;
