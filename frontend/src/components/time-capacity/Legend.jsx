import React from 'react';

function Legend({ items = [], className = '', stickyMobile = false }) {
  return (
    <div
      className={`time-capacity-legend rounded-xl border border-slate-200 bg-white/95 p-3 dark:border-slate-700 dark:bg-slate-900/95 ${
        stickyMobile ? 'time-capacity-legend-sticky' : ''
      } ${className}`}
    >
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-300">Legend</p>
      <div className="flex flex-wrap gap-3">
        {items.map((item) => (
          <div key={item.key} className="flex items-center gap-2">
            <span className={`h-2.5 w-2.5 rounded-full ${item.dotClass}`} />
            <span className="text-xs font-medium text-slate-700 dark:text-slate-200">{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default React.memo(Legend);
