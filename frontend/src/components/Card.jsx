import React from 'react';

function Card({ title, value, subtitle, tone = 'default', onClick }) {
  const tones = {
    default: 'border-slate-200 dark:border-slate-800',
    success: 'border-emerald-200 dark:border-emerald-900',
    warning: 'border-amber-200 dark:border-amber-900',
    danger: 'border-rose-200 dark:border-rose-900'
  };

  return (
    <button
      type="button"
      onClick={onClick}
      className={`card-panel w-full text-left ${tones[tone] || tones.default} ${onClick ? 'hover:scale-[1.01]' : ''}`}
    >
      <p className="text-sm text-slate-500 dark:text-slate-400">{title}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-900 dark:text-slate-50">{value}</p>
      {subtitle ? <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">{subtitle}</p> : null}
    </button>
  );
}

export default Card;
