import React from 'react';

function ErrorState({ message, variant = 'boxed', className = '' }) {
  if (!message) return null;

  let displayMessage = message;
  if (typeof displayMessage !== 'string') {
    if (displayMessage instanceof Error && typeof displayMessage.message === 'string') {
      displayMessage = displayMessage.message;
    } else {
      try {
        displayMessage = JSON.stringify(displayMessage);
      } catch {
        displayMessage = String(displayMessage);
      }
    }
  }
  if (variant === 'inline') {
    return <p className={`text-rose-600 ${className}`}>{displayMessage}</p>;
  }
  return (
    <div className={`rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-200 ${className}`}>
      {displayMessage}
    </div>
  );
}

export default React.memo(ErrorState);
