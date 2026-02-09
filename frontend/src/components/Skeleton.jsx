import React from 'react';

function SkeletonBlock({ className = '' }) {
  return <div className={`animate-pulse rounded-lg bg-slate-200/80 dark:bg-slate-700/70 ${className}`} />;
}

export function PageSkeleton() {
  return (
    <section className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <div className="mb-4 flex items-center justify-between gap-3">
          <SkeletonBlock className="h-8 w-48" />
          <SkeletonBlock className="h-9 w-32" />
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          <SkeletonBlock className="h-24 w-full" />
          <SkeletonBlock className="h-24 w-full" />
          <SkeletonBlock className="h-24 w-full" />
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <div className="mb-4 grid gap-3 md:grid-cols-3">
          <SkeletonBlock className="h-10 w-full" />
          <SkeletonBlock className="h-10 w-full" />
          <SkeletonBlock className="h-10 w-full" />
        </div>
        <div className="space-y-2">
          <SkeletonBlock className="h-10 w-full" />
          <SkeletonBlock className="h-10 w-full" />
          <SkeletonBlock className="h-10 w-full" />
          <SkeletonBlock className="h-10 w-full" />
        </div>
      </div>
    </section>
  );
}

export function InlineSkeletonText() {
  return <SkeletonBlock className="h-4 w-40" />;
}

export default SkeletonBlock;
