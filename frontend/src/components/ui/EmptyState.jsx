import React from 'react';

function EmptyState({ title, description, action, className = '' }) {
  return (
    <div className={className}>
      <p className="text-sm text-slate-500 dark:text-slate-400">{title}</p>
      {description ? <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{description}</p> : null}
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  );
}

export default React.memo(EmptyState);
