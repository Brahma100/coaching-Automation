import React from 'react';
import { FiPlus, FiRefreshCw } from 'react-icons/fi';

import Modal from '../components/Modal.jsx';
import CalendarHeader from '../components/calendar/CalendarHeader.jsx';
import CalendarGrid from '../components/calendar/CalendarGrid.jsx';
import LiveClassPanel from '../components/calendar/LiveClassPanel.jsx';
import ErrorState from '../components/ui/ErrorState.jsx';
import LoadingState from '../components/ui/LoadingState.jsx';
import useRole from '../hooks/useRole';
import {
  createCalendarOverride,
  deleteCalendarOverride,
  fetchCalendarSession,
  fetchTeacherCalendar,
  fetchCalendarAnalytics,
  updateCalendarOverride,
  validateCalendarConflicts
} from '../services/api';
import '../styles/teacher-calendar.css';

const HALF_HOUR_SLOTS = Array.from({ length: 48 }, (_, idx) => {
  const minutes = idx * 30;
  const hour = String(Math.floor(minutes / 60)).padStart(2, '0');
  const minute = String(minutes % 60).padStart(2, '0');
  return `${hour}:${minute}`;
});

const DEFAULT_PREFS = {
  snap_interval: 30,
  work_day_start: '07:00',
  work_day_end: '20:00',
  default_view: 'week'
};

function startOfWeek(sourceDate) {
  const dt = new Date(sourceDate);
  const day = dt.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  dt.setDate(dt.getDate() + diff);
  dt.setHours(0, 0, 0, 0);
  return dt;
}

function formatDateLocal(dt) {
  const year = dt.getFullYear();
  const month = String(dt.getMonth() + 1).padStart(2, '0');
  const day = String(dt.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function rangeForView(anchorDate, view) {
  const base = new Date(anchorDate);
  base.setHours(0, 0, 0, 0);

  if (view === 'day') {
    return { start: base, end: base };
  }
  if (view === 'week') {
    const start = startOfWeek(base);
    const end = new Date(start);
    end.setDate(start.getDate() + 6);
    return { start, end };
  }
  if (view === 'month') {
    const start = new Date(base.getFullYear(), base.getMonth(), 1);
    const end = new Date(base.getFullYear(), base.getMonth() + 1, 0);
    return { start, end };
  }

  const start = new Date(base);
  const end = new Date(base);
  end.setDate(start.getDate() + 13);
  return { start, end };
}

function nextAnchor(anchorDate, view, direction) {
  const dt = new Date(anchorDate);
  if (view === 'day') dt.setDate(dt.getDate() + direction);
  else if (view === 'week') dt.setDate(dt.getDate() + direction * 7);
  else if (view === 'month') dt.setMonth(dt.getMonth() + direction);
  else dt.setDate(dt.getDate() + direction * 14);
  return dt;
}

function minutesSinceMidnight(isoString) {
  const dt = new Date(isoString);
  return dt.getHours() * 60 + dt.getMinutes();
}

function formatTimeRange(startIso, endIso) {
  const start = new Date(startIso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const end = new Date(endIso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  return `${start} - ${end}`;
}

function parsePreferences(raw) {
  if (!raw) return DEFAULT_PREFS;
  try {
    if (typeof raw === 'string') return { ...DEFAULT_PREFS, ...JSON.parse(raw) };
    return { ...DEFAULT_PREFS, ...raw };
  } catch {
    return DEFAULT_PREFS;
  }
}

function buildEvents(items) {
  return items.map((item) => {
    const uid = item.session_id ? `session-${item.session_id}` : `batch-${item.batch_id}-${item.start_datetime}`;
    const startMinutes = minutesSinceMidnight(item.start_datetime);
    return {
      ...item,
      uid,
      start_minutes: startMinutes,
      time_label: formatTimeRange(item.start_datetime, item.end_datetime),
      color_class: 'calendar-tone-default'
    };
  });
}

function groupEventsByDate(events) {
  return events.reduce((acc, item) => {
    const day = item.start_datetime.slice(0, 10);
    if (!acc[day]) acc[day] = [];
    acc[day].push(item);
    return acc;
  }, {});
}

function buildMonthMatrix(anchorDate) {
  const first = new Date(anchorDate.getFullYear(), anchorDate.getMonth(), 1);
  const last = new Date(anchorDate.getFullYear(), anchorDate.getMonth() + 1, 0);
  const start = startOfWeek(first);
  const end = new Date(last);
  const lastWeekday = end.getDay();
  if (lastWeekday !== 0) {
    end.setDate(end.getDate() + (7 - lastWeekday));
  }

  const days = [];
  const cursor = new Date(start);
  while (cursor <= end) {
    days.push(new Date(cursor));
    cursor.setDate(cursor.getDate() + 1);
  }
  return days;
}

function snapMinutes(value, interval) {
  return Math.round(value / interval) * interval;
}

function TeacherCalendar() {
  const { isAdmin, loading: roleLoading } = useRole();
  const [view, setView] = React.useState('week');
  const [anchorDate, setAnchorDate] = React.useState(() => new Date());
  const [teacherId, setTeacherId] = React.useState('');
  const [filters, setFilters] = React.useState({ search: '', subject: '', academicLevel: '', room: '', hideInactive: false });
  const [items, setItems] = React.useState([]);
  const [preferences, setPreferences] = React.useState(DEFAULT_PREFS);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState('');
  const [viewportWidth, setViewportWidth] = React.useState(() => window.innerWidth);
  const initialViewApplied = React.useRef(false);
  const [heatmapEnabled, setHeatmapEnabled] = React.useState(false);
  const [analyticsByDay, setAnalyticsByDay] = React.useState({});

  const [selectedEvent, setSelectedEvent] = React.useState(null);
  const [selectedSession, setSelectedSession] = React.useState(null);

  const [editorOpen, setEditorOpen] = React.useState(false);
  const [editorMode, setEditorMode] = React.useState('create');
  const [overrideId, setOverrideId] = React.useState(null);
  const [editorForm, setEditorForm] = React.useState({
    batch_id: '',
    override_date: formatDateLocal(new Date()),
    new_start_time: '08:00',
    new_duration_minutes: 60,
    cancelled: false,
    reason: ''
  });
  const [conflictState, setConflictState] = React.useState({ checking: false, message: '', conflicts: [] });

  const slotHeight = 24;
  const dragSnapshot = React.useRef(null);
  const conflictTimer = React.useRef(null);

  React.useEffect(() => {
    const onResize = () => setViewportWidth(window.innerWidth);
    window.addEventListener('resize', onResize);
    window.addEventListener('orientationchange', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
      window.removeEventListener('orientationchange', onResize);
    };
  }, []);

  const isNarrow = viewportWidth <= 720;
  const timeColWidth = isNarrow ? 56 : 80;
  const sidebarWidth = viewportWidth >= 1024 ? 280 : 0;
  const availableWidth = Math.max(320, viewportWidth - sidebarWidth - 64);
  const dayCount = view === 'day' ? 1 : 7;
  const minDayWidth = isNarrow ? 130 : 170;
  const computedDayWidth = Math.floor((availableWidth - timeColWidth) / dayCount);
  const dayWidth = view === 'day'
    ? Math.max(minDayWidth, availableWidth - timeColWidth)
    : Math.max(minDayWidth, computedDayWidth);

  const dateRange = React.useMemo(() => rangeForView(anchorDate, view), [anchorDate, view]);
  const headerDateLabel = React.useMemo(() => {
    const options = { month: 'long', day: 'numeric', year: 'numeric' };
    if (view === 'day') return dateRange.start.toLocaleDateString([], options);
    return `${dateRange.start.toLocaleDateString([], options)} - ${dateRange.end.toLocaleDateString([], options)}`;
  }, [dateRange, view]);

  const loadCalendar = React.useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchTeacherCalendar({
        start: formatDateLocal(dateRange.start),
        end: formatDateLocal(dateRange.end),
        view,
        teacherId: isAdmin ? teacherId : undefined
      });
      setPreferences(parsePreferences(data.preferences));
      setItems(buildEvents(data.items || []));
    } catch (err) {
      const message = err?.response?.data?.detail || err?.message || 'Failed to load calendar.';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [dateRange.start, dateRange.end, isAdmin, teacherId, view]);

  React.useEffect(() => {
    if (roleLoading) return;
    loadCalendar().catch(() => null);
  }, [loadCalendar, roleLoading]);

  React.useEffect(() => {
    if (initialViewApplied.current) return;
    if (preferences?.default_view && view === 'week') {
      setView(preferences.default_view);
      initialViewApplied.current = true;
    }
  }, [preferences, view]);

  React.useEffect(() => {
    const shouldFetch = heatmapEnabled || view === 'month';
    if (!shouldFetch) return;
    let isActive = true;
    const loadAnalytics = async () => {
      try {
        const data = await fetchCalendarAnalytics({
          start: formatDateLocal(dateRange.start),
          end: formatDateLocal(dateRange.end),
          teacherId: isAdmin ? teacherId : undefined
        });
        if (!isActive) return;
        const map = {};
        (data.days || []).forEach((row) => {
          map[row.date] = row;
        });
        setAnalyticsByDay(map);
      } catch {
        if (isActive) setAnalyticsByDay({});
      }
    };
    loadAnalytics();
    return () => {
      isActive = false;
    };
  }, [dateRange.start, dateRange.end, heatmapEnabled, isAdmin, teacherId, view]);

  const filteredEvents = React.useMemo(() => {
    return items.filter((item) => {
      if (filters.search && !item.batch_name.toLowerCase().includes(filters.search.toLowerCase())) return false;
      if (filters.subject && !item.subject.toLowerCase().includes(filters.subject.toLowerCase())) return false;
      if (filters.academicLevel && !(item.academic_level || '').toLowerCase().includes(filters.academicLevel.toLowerCase())) return false;
      if (filters.room && !(item.room || '').toLowerCase().includes(filters.room.toLowerCase())) return false;
      if (filters.hideInactive && item.status === 'completed') return false;
      return true;
    });
  }, [items, filters]);

  const eventsByDate = React.useMemo(() => groupEventsByDate(filteredEvents), [filteredEvents]);
  const heatmapByDay = React.useMemo(() => {
    const map = {};
    Object.keys(analyticsByDay || {}).forEach((day) => {
      const row = analyticsByDay[day];
      if (!row || row.attendance_rate == null) {
        map[day] = '';
        return;
      }
      let className = 'heatmap-mid';
      if (row.attendance_rate >= 0.9) className = 'heatmap-high';
      else if (row.attendance_rate < 0.7) className = 'heatmap-low';

      const hasFeeDue = (eventsByDate[day] || []).some((event) => event.fee_due_count > 0);
      if (hasFeeDue) className = `${className} heatmap-fee`;
      map[day] = className;
    });
    return map;
  }, [analyticsByDay, eventsByDate]);

  const weekdays = React.useMemo(() => {
    const start = startOfWeek(anchorDate);
    return Array.from({ length: 7 }, (_, idx) => {
      const dt = new Date(start);
      dt.setDate(start.getDate() + idx);
      return dt;
    });
  }, [anchorDate]);

  const currentTimeLine = React.useMemo(() => {
    const now = new Date();
    return (now.getHours() * 60 + now.getMinutes()) / 30 * slotHeight;
  }, [loading]);

  const openEvent = React.useCallback(async (event) => {
    setSelectedEvent(event);
    setSelectedSession(null);
    if (!event.session_id) return;
    try {
      const details = await fetchCalendarSession(event.session_id);
      setSelectedSession(details);
    } catch {
      setSelectedSession(null);
    }
  }, []);

  const closeEventModal = React.useCallback(() => {
    setSelectedEvent(null);
    setSelectedSession(null);
  }, []);

  const startAddClass = React.useCallback(() => {
    setEditorMode('create');
    setOverrideId(null);
    setEditorForm((prev) => ({
      ...prev,
      override_date: formatDateLocal(dateRange.start)
    }));
    setConflictState({ checking: false, message: '', conflicts: [] });
    setEditorOpen(true);
  }, [dateRange.start]);

  const startEditFromSelection = React.useCallback(() => {
    if (!selectedEvent) return;
    const startDt = new Date(selectedEvent.start_datetime);
    setEditorMode('update');
    setOverrideId(selectedEvent.override_id || null);
    setEditorForm({
      batch_id: selectedEvent.batch_id,
      override_date: selectedEvent.start_datetime.slice(0, 10),
      new_start_time: `${String(startDt.getHours()).padStart(2, '0')}:${String(startDt.getMinutes()).padStart(2, '0')}`,
      new_duration_minutes: selectedEvent.duration_minutes,
      cancelled: false,
      reason: 'Rescheduled from calendar'
    });
    setConflictState({ checking: false, message: '', conflicts: [] });
    setEditorOpen(true);
  }, [selectedEvent]);

  const runConflictCheck = React.useCallback(async ({ teacherValue, dateValue, startTime, duration, roomId }) => {
    setConflictState({ checking: true, message: '', conflicts: [] });
    try {
      const result = await validateCalendarConflicts({
        teacher_id: teacherValue,
        date: dateValue,
        start_time: startTime,
        duration_minutes: duration,
        room_id: roomId || null
      });
      if (result.ok) {
        setConflictState({ checking: false, message: '', conflicts: [] });
        return { ok: true, conflicts: [] };
      }
      const message = result.detail || 'Conflict detected';
      setConflictState({ checking: false, message, conflicts: result.conflicts || [] });
      return { ok: false, conflicts: result.conflicts || [], message };
    } catch (err) {
      const message = err?.response?.data?.detail || 'Conflict validation failed';
      setConflictState({ checking: false, message, conflicts: [] });
      return { ok: false, conflicts: [], message };
    }
  }, []);

  const validateConflict = React.useCallback(async ({ teacherValue, dateValue, startTime, duration, roomId }) => {
    if (conflictTimer.current) {
      clearTimeout(conflictTimer.current);
    }
    conflictTimer.current = setTimeout(async () => {
      await runConflictCheck({ teacherValue, dateValue, startTime, duration, roomId });
    }, 240);
  }, [runConflictCheck]);

  const applyOptimisticUpdate = React.useCallback((eventId, updates) => {
    setItems((prev) => prev.map((item) => (item.uid === eventId ? { ...item, ...updates } : item)));
  }, []);

  const handleEventDrop = React.useCallback(async (dragEvent) => {
    const activeEvent = dragEvent.active?.data?.current?.event;
    const overId = dragEvent.over?.id;
    if (!activeEvent || !overId) return;

    const deltaMinutesRaw = (dragEvent.delta?.y || 0) / slotHeight * 30;
    const snappedDelta = snapMinutes(deltaMinutesRaw, preferences.snap_interval || 30);

    const baseStart = new Date(activeEvent.start_datetime);
    const targetDate = new Date(overId);
    targetDate.setHours(baseStart.getHours(), baseStart.getMinutes(), 0, 0);
    const newStart = new Date(targetDate.getTime() + snappedDelta * 60000);
    const newEnd = new Date(newStart.getTime() + activeEvent.duration_minutes * 60000);

    const teacherValue = isAdmin ? Number(teacherId || 0) : Number(activeEvent.teacher_id || 0);
    const conflictCheck = await runConflictCheck({
      teacherValue,
      dateValue: formatDateLocal(newStart),
      startTime: newStart.toTimeString().slice(0, 5),
      duration: activeEvent.duration_minutes,
      roomId: activeEvent.room_id
    });

    if (!conflictCheck.ok) {
      return;
    }

    dragSnapshot.current = { uid: activeEvent.uid, start_datetime: activeEvent.start_datetime, end_datetime: activeEvent.end_datetime };

    applyOptimisticUpdate(activeEvent.uid, {
      start_datetime: newStart.toISOString(),
      end_datetime: newEnd.toISOString(),
      start_minutes: minutesSinceMidnight(newStart.toISOString()),
      time_label: formatTimeRange(newStart.toISOString(), newEnd.toISOString())
    });

    try {
      await createCalendarOverride({
        batch_id: activeEvent.batch_id,
        override_date: formatDateLocal(newStart),
        new_start_time: newStart.toTimeString().slice(0, 5),
        new_duration_minutes: activeEvent.duration_minutes,
        reason: 'Rescheduled via drag'
      });
    } catch (err) {
      if (dragSnapshot.current) {
        applyOptimisticUpdate(activeEvent.uid, dragSnapshot.current);
      }
      setError(err?.response?.data?.detail || 'Failed to save reschedule');
    }
  }, [applyOptimisticUpdate, isAdmin, preferences.snap_interval, runConflictCheck, slotHeight, teacherId]);

  const handleDragPreview = React.useCallback((dragEvent) => {
    const activeEvent = dragEvent.active?.data?.current?.event;
    const overId = dragEvent.over?.id;
    if (!activeEvent || !overId) return;

    const deltaMinutesRaw = (dragEvent.delta?.y || 0) / slotHeight * 30;
    const snappedDelta = snapMinutes(deltaMinutesRaw, preferences.snap_interval || 30);
    const baseStart = new Date(activeEvent.start_datetime);
    const targetDate = new Date(overId);
    targetDate.setHours(baseStart.getHours(), baseStart.getMinutes(), 0, 0);
    const previewStart = new Date(targetDate.getTime() + snappedDelta * 60000);

    const teacherValue = isAdmin ? Number(teacherId || 0) : Number(activeEvent.teacher_id || 0);
    validateConflict({
      teacherValue,
      dateValue: formatDateLocal(previewStart),
      startTime: previewStart.toTimeString().slice(0, 5),
      duration: activeEvent.duration_minutes,
      roomId: activeEvent.room_id
    });
  }, [isAdmin, preferences.snap_interval, slotHeight, teacherId, validateConflict]);

  const handleResizeStart = React.useCallback((pointerEvent, event) => {
    pointerEvent.stopPropagation();
    const startY = pointerEvent.clientY;
    const originalDuration = event.duration_minutes;

    const onMove = async (moveEvent) => {
      const delta = moveEvent.clientY - startY;
      const deltaMinutesRaw = delta / slotHeight * 30;
      const newDuration = Math.max(30, snapMinutes(originalDuration + deltaMinutesRaw, preferences.snap_interval || 30));
      applyOptimisticUpdate(event.uid, {
        duration_minutes: newDuration,
        end_datetime: new Date(new Date(event.start_datetime).getTime() + newDuration * 60000).toISOString(),
        time_label: formatTimeRange(event.start_datetime, new Date(new Date(event.start_datetime).getTime() + newDuration * 60000).toISOString())
      });

      const teacherValue = isAdmin ? Number(teacherId || 0) : Number(event.teacher_id || 0);
      validateConflict({
        teacherValue,
        dateValue: event.start_datetime.slice(0, 10),
        startTime: event.start_datetime.slice(11, 16),
        duration: newDuration,
        roomId: event.room_id
      });
    };

    const onUp = async () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      const teacherValue = isAdmin ? Number(teacherId || 0) : Number(event.teacher_id || 0);
      const finalCheck = await runConflictCheck({
        teacherValue,
        dateValue: event.start_datetime.slice(0, 10),
        startTime: event.start_datetime.slice(11, 16),
        duration: event.duration_minutes,
        roomId: event.room_id
      });
      if (!finalCheck.ok) {
        applyOptimisticUpdate(event.uid, { duration_minutes: originalDuration });
        return;
      }
      try {
        await createCalendarOverride({
          batch_id: event.batch_id,
          override_date: event.start_datetime.slice(0, 10),
          new_start_time: event.start_datetime.slice(11, 16),
          new_duration_minutes: event.duration_minutes,
          reason: 'Resized via drag'
        });
      } catch (err) {
        applyOptimisticUpdate(event.uid, { duration_minutes: originalDuration });
        setError(err?.response?.data?.detail || 'Failed to save resize');
      }
    };

    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  }, [applyOptimisticUpdate, isAdmin, preferences.snap_interval, runConflictCheck, slotHeight, teacherId, validateConflict]);

  const saveOverride = React.useCallback(async () => {
    const formPayload = {
      batch_id: Number(editorForm.batch_id),
      override_date: editorForm.override_date,
      new_start_time: editorForm.new_start_time || null,
      new_duration_minutes: Number(editorForm.new_duration_minutes) || null,
      cancelled: Boolean(editorForm.cancelled),
      reason: editorForm.reason || ''
    };
    try {
      if (editorMode === 'update' && overrideId) {
        await updateCalendarOverride(overrideId, formPayload);
      } else {
        await createCalendarOverride(formPayload);
      }
      setEditorOpen(false);
      await loadCalendar();
    } catch (err) {
      setConflictState((prev) => ({
        ...prev,
        message: err?.response?.data?.detail || 'Failed to save override.'
      }));
    }
  }, [editorForm, editorMode, loadCalendar, overrideId]);

  const removeOverride = React.useCallback(async () => {
    if (!overrideId) return;
    try {
      await deleteCalendarOverride(overrideId);
      setEditorOpen(false);
      await loadCalendar();
    } catch (err) {
      setConflictState((prev) => ({ ...prev, message: err?.response?.data?.detail || 'Failed to delete override.' }));
    }
  }, [loadCalendar, overrideId]);

  const liveEvent = preferences?.enable_live_mode_auto_open === false
    ? null
    : items.find((item) => item.status === 'live');

  const monthDays = React.useMemo(() => buildMonthMatrix(anchorDate), [anchorDate]);
  const monthEventsByDate = React.useMemo(() => groupEventsByDate(filteredEvents), [filteredEvents]);
  const agendaByDate = React.useMemo(() => {
    const grouped = groupEventsByDate(filteredEvents);
    return Object.keys(grouped)
      .sort()
      .map((day) => ({ day, events: grouped[day].sort((a, b) => a.start_datetime.localeCompare(b.start_datetime)) }));
  }, [filteredEvents]);

  const mainContent = () => {
    if (loading || roleLoading) return <LoadingState label="Loading teacher calendar..." />;
    if (view === 'agenda') {
      if (!agendaByDate.length) return <div className="calendar-agenda-list" />;
      return (
        <div className="calendar-agenda-list">
          {agendaByDate.map(({ day, events }) => (
            <div key={day} className="calendar-agenda-day">
              <h3>{new Date(day).toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' })}</h3>
              <div className="calendar-agenda-items">
                {events.map((event) => (
                  <button
                    key={event.uid}
                    type="button"
                    className={`calendar-event-card ${event.color_class || ''}`}
                    onClick={() => openEvent(event)}
                  >
                    <div className="calendar-event-head">
                      <p className="calendar-event-title">{event.batch_name}</p>
                      {event.status === 'live' ? <span className="calendar-live-pill">LIVE</span> : null}
                    </div>
                    <p className="calendar-event-time">{event.time_label}</p>
                    <p className="calendar-event-meta">{event.student_count} students</p>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      );
    }
    if (view === 'month') {
      return (
        <div className="calendar-month-grid">
          {monthDays.map((day) => {
            const dayKey = formatDateLocal(day);
            const isOutside = day.getMonth() !== anchorDate.getMonth();
            const dayEvents = monthEventsByDate[dayKey] || [];
            const visibleEvents = dayEvents.slice(0, 3);
            const moreCount = Math.max(0, dayEvents.length - visibleEvents.length);
            return (
              <div key={dayKey} className={`calendar-month-cell ${isOutside ? 'outside' : ''}`}>
                <div className="calendar-month-date">{day.getDate()}</div>
                <div className="calendar-month-items">
                  {visibleEvents.map((event) => (
                    <button
                      key={event.uid}
                      type="button"
                      className={`calendar-event-card ${event.color_class || ''} compact`}
                      onClick={() => openEvent(event)}
                    >
                      <div className="calendar-event-head">
                        <p className="calendar-event-title">{event.batch_name}</p>
                        {event.status === 'live' ? <span className="calendar-live-pill">LIVE</span> : null}
                      </div>
                      <p className="calendar-event-time">{event.time_label}</p>
                    </button>
                  ))}
                  {moreCount > 0 ? <div className="calendar-month-more">+{moreCount} more</div> : null}
                </div>
              </div>
            );
          })}
        </div>
      );
    }
    return (
      <CalendarGrid
        days={view === 'day' ? [anchorDate] : weekdays}
        eventsByDay={eventsByDate}
        slots={HALF_HOUR_SLOTS}
        slotHeight={slotHeight}
        timeColWidth={timeColWidth}
        dayWidth={dayWidth}
        isNarrow={isNarrow}
        currentTimeLine={currentTimeLine}
        onEventClick={openEvent}
        onEventDrop={handleEventDrop}
        onDragPreview={handleDragPreview}
        onResizeStart={handleResizeStart}
      />
    );
  };

  return (
    <section className="teacher-calendar-page">
      <CalendarHeader
        currentDate={headerDateLabel}
        view={view}
        onViewChange={setView}
        onPrev={() => setAnchorDate((prev) => nextAnchor(prev, view, -1))}
        onNext={() => setAnchorDate((prev) => nextAnchor(prev, view, 1))}
        onToday={() => setAnchorDate(new Date())}
        filters={filters}
        onFiltersChange={setFilters}
        isAdmin={isAdmin}
        teacherId={teacherId}
        onTeacherIdChange={setTeacherId}
      />

      <ErrorState message={error} />

      <div className="calendar-content-shell">
        <button type="button" className="calendar-refresh-btn" onClick={() => loadCalendar().catch(() => null)}>
          <FiRefreshCw /> Refresh
        </button>
        {mainContent()}
      </div>

      <button type="button" className="calendar-fab" onClick={startAddClass}>
        <FiPlus /> Add Class
      </button>

      <LiveClassPanel
        liveEvent={liveEvent}
        onStartAttendance={() => null}
        onQuickMessage={() => null}
        onViewBatch={() => null}
      />

      <Modal
        open={Boolean(selectedEvent)}
        title={selectedEvent ? `${selectedEvent.batch_name} • ${selectedEvent.subject}` : 'Class'}
        onClose={closeEventModal}
      >
        {selectedEvent ? (
          <div className="calendar-modal-body">
            <p><strong>Time:</strong> {new Date(selectedEvent.start_datetime).toLocaleString()} - {new Date(selectedEvent.end_datetime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</p>
            <p><strong>Status:</strong> {selectedEvent.status}</p>
            <p><strong>Students:</strong> {selectedEvent.student_count} | <strong>Fees:</strong> {selectedEvent.fee_due_count} | <strong>Risk:</strong> {selectedEvent.risk_count}</p>
            {selectedSession?.topic_planned ? <p><strong>Plan:</strong> {selectedSession.topic_planned}</p> : null}
            <div className="calendar-modal-actions">
              <button type="button" className="calendar-action-btn">Open Attendance</button>
              <button type="button" className="calendar-action-btn">View Batch</button>
              <button type="button" className="calendar-action-btn" onClick={startEditFromSelection}>Edit Schedule</button>
              <button type="button" className="calendar-action-btn danger">Cancel Class</button>
              <button type="button" className="calendar-action-btn">Send Reminder</button>
            </div>
          </div>
        ) : null}
      </Modal>

      <Modal
        open={editorOpen}
        title={editorMode === 'update' ? 'Edit Schedule Override' : 'Add Class / Override'}
        onClose={() => setEditorOpen(false)}
        footer={(
          <div className="calendar-editor-footer">
            {editorMode === 'update' && overrideId ? (
              <button type="button" className="calendar-action-btn danger" onClick={removeOverride}>Delete Override</button>
            ) : null}
            <button type="button" className="calendar-action-btn" onClick={saveOverride}>Save</button>
          </div>
        )}
      >
        <div className="calendar-editor-grid">
          <label>
            Batch ID
            <input value={editorForm.batch_id} onChange={(event) => setEditorForm((prev) => ({ ...prev, batch_id: event.target.value }))} />
          </label>
          <label>
            Date
            <input type="date" value={editorForm.override_date} onChange={(event) => setEditorForm((prev) => ({ ...prev, override_date: event.target.value }))} />
          </label>
          <label>
            Start time
            <input type="time" value={editorForm.new_start_time} onChange={(event) => setEditorForm((prev) => ({ ...prev, new_start_time: event.target.value }))} />
          </label>
          <label>
            Duration (minutes)
            <input
              type="number"
              min={30}
              max={300}
              value={editorForm.new_duration_minutes}
              onChange={(event) => setEditorForm((prev) => ({ ...prev, new_duration_minutes: Number(event.target.value) }))}
            />
          </label>
          <label>
            Reason
            <input value={editorForm.reason} onChange={(event) => setEditorForm((prev) => ({ ...prev, reason: event.target.value }))} />
          </label>
        </div>
        {conflictState.checking ? <p className="calendar-conflict-info">Validating overlap...</p> : null}
        {conflictState.message ? <p className="calendar-conflict-error">{conflictState.message}</p> : null}
      </Modal>
    </section>
  );
}

export default TeacherCalendar;

