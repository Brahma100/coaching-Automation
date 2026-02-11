import React from 'react';

function SectionHeader({ title, subtitle, action, className = '', titleClassName = '', subtitleClassName = '' }) {
  return (
    <div className={`flex flex-wrap items-center justify-between gap-3 ${className}`}>
      <div>
        <h3 className={`text-lg font-semibold text-slate-900 dark:text-slate-100 ${titleClassName}`}>{title}</h3>
        {subtitle ? (
          <p className={`text-sm text-slate-500 dark:text-slate-400 ${subtitleClassName}`}>{subtitle}</p>
        ) : null}
      </div>
      {action ? <div>{action}</div> : null}
    </div>
  );
}

export default React.memo(SectionHeader);
