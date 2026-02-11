import React from 'react';

import { InlineSkeletonText } from '../Skeleton.jsx';

function LoadingState({ label = '' }) {
  return (
    <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
      <InlineSkeletonText />
      {label ? <span>{label}</span> : null}
    </div>
  );
}

export default React.memo(LoadingState);
