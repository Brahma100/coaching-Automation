import React from 'react';

function ActionCard({ className = '', children }) {
  return (
    <div className={`rounded-xl border border-slate-200 px-4 py-3 text-sm dark:border-slate-800 ${className}`}>
      {children}
    </div>
  );
}

export default React.memo(ActionCard);
