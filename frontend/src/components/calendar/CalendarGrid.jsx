import React from 'react';
import DragDropContext from './DragDropContext.jsx';
import CalendarTimeColumn from './CalendarTimeColumn.jsx';
import CalendarDayColumn from './CalendarDayColumn.jsx';
import CalendarEvent from './CalendarEvent.jsx';

function CalendarGrid({
  days,
  eventsByDay,
  slots,
  slotHeight,
  timeColWidth,
  dayWidth,
  isNarrow,
  currentTimeLine,
  onEventClick,
  onEventDrop,
  onDragPreview,
  onResizeStart,
  heatmapByDay,
  heatmapEnabled,
}) {
  const onDragStart = React.useCallback((event) => {
    if (!event?.active?.data?.current?.event) return;
  }, []);

  const onDragMove = React.useCallback((event) => {
    if (!event?.active?.data?.current?.event) return;
    if (onDragPreview) {
      onDragPreview(event);
    }
  }, [onDragPreview]);

  const onDragEnd = React.useCallback((event) => {
    if (!event?.active?.data?.current?.event) return;
    if (onEventDrop) {
      onEventDrop(event);
    }
  }, [onEventDrop]);

  return (
    <DragDropContext onDragStart={onDragStart} onDragMove={onDragMove} onDragEnd={onDragEnd}>
      <div className="calendar-grid-wrap">
        <div className="calendar-grid-head" style={{ gridTemplateColumns: `${timeColWidth}px repeat(${days.length}, ${dayWidth}px)` }}>
          <div className="calendar-grid-spacer" />
          {days.map((dt) => (
            <div key={dt.toISOString()} className="calendar-grid-day-title">
              {dt.toLocaleDateString([], { weekday: 'short', day: 'numeric' })}
            </div>
          ))}
        </div>
        <div className="calendar-grid-body" style={{ gridTemplateColumns: `${timeColWidth}px repeat(${days.length}, ${dayWidth}px)` }}>
          <CalendarTimeColumn slots={slots} />
          {days.map((dt) => {
            const dayKey = dt.toISOString().slice(0, 10);
            const dayEvents = (eventsByDay[dayKey] || []).map((event) => {
              const top = (event.start_minutes / 30) * slotHeight;
              const height = Math.max(slotHeight, (event.duration_minutes / 30) * slotHeight);
              const compact = isNarrow || height < slotHeight * 2.3;
              return (
                <div
                  key={event.uid}
                  className="calendar-event-positioner"
                  style={{ top: `${top}px`, height: `${height}px` }}
                >
                  <CalendarEvent
                    event={event}
                    compact={compact}
                    onClick={onEventClick}
                    onResizeStart={(pointerEvent) => onResizeStart(pointerEvent, event)}
                  />
                </div>
              );
            });

            const isToday = dt.toISOString().slice(0, 10) === new Date().toISOString().slice(0, 10);
            const heatmapClass = heatmapByDay?.[dayKey] || '';
            return (
              <CalendarDayColumn
                key={dayKey}
                dayKey={dayKey}
                slots={slots}
                isToday={isToday}
                currentTimeLine={currentTimeLine}
                heatmapClass={heatmapClass}
                heatmapEnabled={heatmapEnabled}
              >
                {dayEvents}
              </CalendarDayColumn>
            );
          })}
        </div>
      </div>
    </DragDropContext>
  );
}

export default CalendarGrid;
