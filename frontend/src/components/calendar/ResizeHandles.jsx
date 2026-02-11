import React from 'react';

function ResizeHandles({ onResizeStart }) {
  return (
    <div
      className="calendar-resize-handle"
      onPointerDown={onResizeStart}
      role="presentation"
    />
  );
}

export default ResizeHandles;
