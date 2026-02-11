import React from 'react';

const variants = {
  overdue: 'bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-200',
  due: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-200',
  completed: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-200',
  info: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-200'
};

function StatusBadge({ variant = 'info', children, className = '' }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-semibold ${variants[variant] || variants.info} ${className}`}>
      {children}
    </span>
  );
}

export default React.memo(StatusBadge);
