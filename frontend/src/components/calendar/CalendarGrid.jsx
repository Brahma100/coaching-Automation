import React from 'react';
import CalendarTimeColumn from './CalendarTimeColumn.jsx';
import CalendarDayColumn from './CalendarDayColumn.jsx';
import CalendarEvent from './CalendarEvent.jsx';

function formatDateLocal(dt) {
  const year = dt.getFullYear();
  const month = String(dt.getMonth() + 1).padStart(2, '0');
  const day = String(dt.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

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
  heatmapByDay,
  heatmapEnabled,
  holidaysByDate,
  showHolidays,
  scrollContainerRef,
}) {
  const isSingleDay = days.length === 1;
  const todayKey = formatDateLocal(new Date());

  return (
    <div ref={scrollContainerRef} className={`calendar-grid-wrap ${isSingleDay ? 'single-day' : ''}`}>
      <div className="calendar-grid-head" style={{ gridTemplateColumns: `${timeColWidth}px repeat(${days.length}, ${dayWidth}px)` }}>
        <div className="calendar-grid-spacer" />
        {days.map((dt) => {
          const dayKey = formatDateLocal(dt);
          const isToday = dayKey === todayKey;
          return (
          <div key={dayKey} className={`calendar-grid-day-title ${isToday ? 'today' : ''}`}>
            {dt.toLocaleDateString([], { weekday: 'short', day: 'numeric' })}
          </div>
          );
        })}
      </div>
      <div className="calendar-grid-body" style={{ gridTemplateColumns: `${timeColWidth}px repeat(${days.length}, ${dayWidth}px)` }}>
        <CalendarTimeColumn slots={slots} />
        {days.map((dt) => {
          const dayKey = formatDateLocal(dt);
          const dayEvents = (eventsByDay[dayKey] || []).map((event) => {
            const top = (event.start_minutes / 30) * slotHeight;
            const height = Math.max(slotHeight, (event.duration_minutes / 30) * slotHeight);
            const compact = isNarrow || height < slotHeight * 2.3;
            const hideMiddleInfo = height < slotHeight * 3.2;
            return (
              <div
                key={event.uid}
                className="calendar-event-positioner"
                style={{ top: `${top}px`, height: `${height}px` }}
              >
                <CalendarEvent
                  event={event}
                  compact={compact}
                  hideMiddleInfo={hideMiddleInfo}
                  onClick={onEventClick}
                />
              </div>
            );
          });

          const isToday = dayKey === todayKey;
          const heatmapClass = heatmapByDay?.[dayKey] || '';
          const holidayLabel = showHolidays ? (holidaysByDate?.[dayKey] || [])[0] : '';
          return (
            <CalendarDayColumn
              key={dayKey}
              dayKey={dayKey}
              slots={slots}
              isToday={isToday}
              currentTimeLine={currentTimeLine}
              heatmapClass={heatmapClass}
              heatmapEnabled={heatmapEnabled}
              holidayLabel={holidayLabel}
            >
              {dayEvents}
            </CalendarDayColumn>
          );
        })}
      </div>
    </div>
  );
}

export default CalendarGrid;
