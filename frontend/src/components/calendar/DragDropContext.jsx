import React from 'react';
import { DndContext, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';

function DragDropContext({ children, onDragStart, onDragMove, onDragEnd }) {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));

  return (
    <DndContext
      sensors={sensors}
      onDragStart={onDragStart}
      onDragMove={onDragMove}
      onDragEnd={onDragEnd}
    >
      {children}
    </DndContext>
  );
}

export default DragDropContext;
