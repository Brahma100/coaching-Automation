import React from 'react';
import { FiAlertTriangle, FiBell, FiCalendar, FiClock, FiPlus, FiRefreshCw, FiUsers, FiZap } from 'react-icons/fi';
import { FaIndianRupeeSign } from 'react-icons/fa6';
import { useNavigate } from 'react-router-dom';

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
  fetchBatches,
  fetchCalendarSession,
  fetchTeacherCalendar,
  fetchCalendarAnalytics,
  openAttendanceSession,
  syncCalendarHolidays,
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

function fullYear(dt) {
  return String(dt.getFullYear());
}

function shortMonth(dt) {
  return dt.toLocaleDateString([], { month: 'short' });
}

function compactDateRangeLabel(start, end, view) {
  if (view === 'day') {
    return `${shortMonth(start)} ${start.getDate()}, ${fullYear(start)}`;
  }

  const sameYear = start.getFullYear() === end.getFullYear();
  const sameMonth = sameYear && start.getMonth() === end.getMonth();

  if (sameMonth) {
    return `${shortMonth(start)} ${start.getDate()}-${end.getDate()}, ${fullYear(start)}`;
  }

  if (sameYear) {
    return `${shortMonth(start)}/${shortMonth(end)} ${fullYear(start)}`;
  }

  return `${shortMonth(start)} ${start.getDate()}, ${fullYear(start)} - ${shortMonth(end)} ${end.getDate()}, ${fullYear(end)}`;
}

function toToday() {
  return formatDateLocal(new Date());
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

function getWeekOfMonth(sourceDate) {
  const dt = new Date(sourceDate);
  const firstOfMonth = new Date(dt.getFullYear(), dt.getMonth(), 1);
  const firstWeekday = (firstOfMonth.getDay() + 6) % 7;
  return Math.floor((dt.getDate() + firstWeekday - 1) / 7) + 1;
}

function nextAnchor(anchorDate, view, direction) {
  const dt = new Date(anchorDate);
  if (view === 'day') dt.setDate(dt.getDate() + direction);
  else if (view === 'week') dt.setDate(dt.getDate() + direction * 7);
  else if (view === 'month') dt.setMonth(dt.getMonth() + direction);
  else dt.setDate(dt.getDate() + direction * 14);
  return dt;
}

function parseCalendarDateTime(isoString) {
  if (!isoString || typeof isoString !== 'string') return new Date(isoString);
  const hasExplicitOffset = /([zZ]|[+-]\d{2}:\d{2})$/.test(isoString);
  if (hasExplicitOffset) return new Date(isoString);

  const match = isoString.match(
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?/
  );
  if (!match) return new Date(isoString);

  const [, y, mo, d, h, mi, s] = match;
  return new Date(
    Number(y),
    Number(mo) - 1,
    Number(d),
    Number(h),
    Number(mi),
    Number(s || '0'),
    0
  );
}

function formatClockLabel(dt) {
  return dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function minutesSinceMidnight(isoString) {
  const dt = parseCalendarDateTime(isoString);
  return dt.getHours() * 60 + dt.getMinutes();
}

function formatTimeRange(startIso, endIso) {
  const start = formatClockLabel(parseCalendarDateTime(startIso));
  const end = formatClockLabel(parseCalendarDateTime(endIso));
  return `${start} - ${end}`;
}

function formatEventDateLine(startIso, endIso) {
  const start = parseCalendarDateTime(startIso);
  const end = parseCalendarDateTime(endIso);
  const dayPart = start.toLocaleDateString([], { month: 'short', day: 'numeric' });
  const yearPart = start.getFullYear();
  return `${dayPart} • ${yearPart}, ${formatClockLabel(start)} - ${formatClockLabel(end)}`;
}

function getEventStatusUi(status) {
  if (status === 'live') return { label: 'Live', className: 'status-live' };
  if (status === 'completed') return { label: 'Completed', className: 'status-completed' };
  if (status === 'cancelled') return { label: 'Cancelled', className: 'status-cancelled' };
  return { label: 'Upcoming', className: 'status-upcoming' };
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
  const now = new Date();
  const todayKey = formatDateLocal(now);

  return items.map((item) => {
    const uid = item.session_id ? `session-${item.session_id}` : `batch-${item.batch_id}-${item.start_datetime}`;
    const startMinutes = minutesSinceMidnight(item.start_datetime);
    const startDt = parseCalendarDateTime(item.start_datetime);
    const endDt = parseCalendarDateTime(item.end_datetime);
    const serverStatus = item.status || 'upcoming';
    const normalizedStatus = serverStatus === 'cancelled'
      ? 'cancelled'
      : (startDt <= now && endDt >= now ? 'live' : (endDt < now ? 'completed' : 'upcoming'));

    let colorClass = 'calendar-tone-default';
    const isCurrent = startDt <= now && endDt >= now;
    const isPast = endDt < now;
    const isUpcomingToday = formatDateLocal(startDt) === todayKey && startDt > now;
    if (isCurrent) {
      colorClass = 'calendar-tone-current';
    } else if (isPast) {
      colorClass = 'calendar-tone-past';
    } else if (isUpcomingToday) {
      colorClass = 'calendar-tone-today-upcoming';
    }

    return {
      ...item,
      status: normalizedStatus,
      uid,
      is_current: isCurrent,
      start_minutes: startMinutes,
      time_label: formatTimeRange(item.start_datetime, item.end_datetime),
      color_class: colorClass
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
  const navigate = useNavigate();
  const { isAdmin, loading: roleLoading } = useRole();
  const [view, setView] = React.useState('week');
  const [anchorDate, setAnchorDate] = React.useState(() => new Date());
  const [teacherId, setTeacherId] = React.useState('');
  const [filters, setFilters] = React.useState({ search: '', subject: '', academicLevel: '', room: '' });
  const [items, setItems] = React.useState([]);
  const [batchCatalog, setBatchCatalog] = React.useState([]);
  const [holidays, setHolidays] = React.useState([]);
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

  const slotHeight = 30;
  const gridScrollRef = React.useRef(null);
  const monthTodayRef = React.useRef(null);
  const dragSnapshot = React.useRef(null);
  const conflictTimer = React.useRef(null);
  const holidaySyncDoneRef = React.useRef(false);

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
  const isCompact = viewportWidth <= 480;
  const timeColWidth = isCompact ? 48 : (isNarrow ? 56 : 80);
  const sidebarWidth = viewportWidth >= 1024 ? 280 : 0;
  const horizontalChrome = viewportWidth <= 720 ? 28 : 64;
  const availableWidth = Math.max(280, viewportWidth - sidebarWidth - horizontalChrome);
  const dayCount = view === 'day' ? 1 : 7;
  const minDayWidth = isCompact ? 88 : (isNarrow ? 108 : 170);
  const computedDayWidth = Math.floor((availableWidth - timeColWidth) / dayCount);
  const dayWidth = view === 'day'
    ? Math.max(minDayWidth, availableWidth - timeColWidth)
    : Math.max(minDayWidth, computedDayWidth);

  const dateRange = React.useMemo(() => rangeForView(anchorDate, view), [anchorDate, view]);
  const headerDateLabel = React.useMemo(() => {
    return compactDateRangeLabel(dateRange.start, dateRange.end, view);
  }, [dateRange, view]);
  const anchorDateLabel = React.useMemo(() => formatDateLocal(anchorDate), [anchorDate]);
  const todayKey = React.useMemo(() => formatDateLocal(new Date()), []);
  const periodPillLabel = React.useMemo(() => {
    if (view === 'day') {
      const dayStamp = anchorDate.toLocaleDateString([], { day: '2-digit', month: 'short' });
      return anchorDateLabel === todayKey ? `Today • ${dayStamp}` : dayStamp;
    }
    if (view === 'week') {
      const weekNumber = getWeekOfMonth(dateRange.start);
      const startMonth = dateRange.start.toLocaleDateString([], { month: 'short' });
      const endMonth = dateRange.end.toLocaleDateString([], { month: 'short' });
      const monthText = startMonth === endMonth ? startMonth : `${startMonth}/${endMonth}`;
      return `Week ${weekNumber} • ${monthText}`;
    }
    if (view === 'month') {
      return anchorDate.toLocaleDateString([], { month: 'long' });
    }
    return 'Agenda';
  }, [anchorDate, anchorDateLabel, dateRange.end, dateRange.start, todayKey, view]);

  const loadCalendar = React.useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      if (!holidaySyncDoneRef.current) {
        try {
          await syncCalendarHolidays({
            startYear: new Date().getFullYear(),
            years: 5,
            countryCode: 'IN',
          });
        } catch {
          // Keep calendar usable even if holiday sync endpoint/API is temporarily unavailable.
        } finally {
          holidaySyncDoneRef.current = true;
        }
      }

      const [data, batchesPayload] = await Promise.all([
        fetchTeacherCalendar({
          start: formatDateLocal(dateRange.start),
          end: formatDateLocal(dateRange.end),
          view,
          teacherId: isAdmin ? teacherId : undefined,
          bypassCache: true,
        }),
        fetchBatches().catch(() => []),
      ]);
      setPreferences(parsePreferences(data.preferences));
      setItems(buildEvents(data.items || []));
      setHolidays(Array.isArray(data.holidays) ? data.holidays : []);
      setBatchCatalog(Array.isArray(batchesPayload) ? batchesPayload : []);
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
    if (roleLoading) return undefined;
    const intervalId = window.setInterval(() => {
      if (document.visibilityState !== 'visible') return;
      loadCalendar().catch(() => null);
    }, 60000);
    return () => window.clearInterval(intervalId);
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
      return true;
    });
  }, [items, filters]);

  const filterOptions = React.useMemo(() => ({
    batches: [...new Set([
      ...(items || []).map((item) => item.batch_name).filter(Boolean),
      ...(batchCatalog || []).map((row) => row?.name).filter(Boolean),
    ])].sort(),
    subjects: [...new Set((items || []).map((item) => item.subject).filter(Boolean))].sort(),
    academicLevels: [...new Set((items || []).map((item) => item.academic_level).filter(Boolean))].sort(),
  }), [batchCatalog, items]);

  const eventsByDate = React.useMemo(() => groupEventsByDate(filteredEvents), [filteredEvents]);
  const holidaysByDate = React.useMemo(() => {
    const map = {};
    for (const row of holidays) {
      const day = row?.date;
      const name = (row?.local_name || row?.name || '').trim();
      if (!day || !name) continue;
      if (!map[day]) map[day] = [];
      if (!map[day].includes(name)) map[day].push(name);
    }
    return map;
  }, [holidays]);

  React.useEffect(() => {
    if (!selectedEvent?.uid) return;
    const latest = items.find((item) => item.uid === selectedEvent.uid);
    if (!latest) return;
    const hasChanged =
      latest.status !== selectedEvent.status ||
      latest.is_current !== selectedEvent.is_current ||
      latest.start_datetime !== selectedEvent.start_datetime ||
      latest.end_datetime !== selectedEvent.end_datetime ||
      latest.time_label !== selectedEvent.time_label;
    if (hasChanged) {
      setSelectedEvent((prev) => (prev ? { ...prev, ...latest } : prev));
    }
  }, [items, selectedEvent]);
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

  React.useEffect(() => {
    if (loading || roleLoading) return undefined;
    let cancelled = false;
    let attempts = 0;
    const maxAttempts = 60;
    let timeoutId = null;

    const scheduleRetry = () => {
      if (cancelled || attempts >= maxAttempts) return;
      timeoutId = window.setTimeout(focusNow, 100);
    };

    const focusNow = () => {
      if (cancelled) return;
      attempts += 1;
      try {
        if (view === 'day' || view === 'week') {
          const container = gridScrollRef.current;
          if (!container || container.clientHeight <= 0 || container.scrollHeight <= container.clientHeight + 4) {
            scheduleRetry();
            return;
          }
          const target = Math.max(0, currentTimeLine - (container.clientHeight * 0.35));
          container.scrollTop = target;
          if (typeof container.scrollTo === 'function') {
            container.scrollTo({ top: target, behavior: 'smooth' });
          }
        } else if (view === 'month') {
          if (!monthTodayRef.current?.scrollIntoView) {
            scheduleRetry();
            return;
          }
          monthTodayRef.current.scrollIntoView({
            behavior: 'smooth',
            block: 'center',
            inline: 'nearest',
          });
        }
      } catch {
        // Fallback for browsers with partial scroll API support
        const container = gridScrollRef.current;
        if (container && (view === 'day' || view === 'week')) {
          const target = Math.max(0, currentTimeLine - (container.clientHeight * 0.35));
          container.scrollTop = target;
        } else {
          scheduleRetry();
        }
      }
    };
    if (typeof window === 'undefined') return undefined;
    const rafId = window.requestAnimationFrame(focusNow);
    return () => {
      cancelled = true;
      if (timeoutId) window.clearTimeout(timeoutId);
      window.cancelAnimationFrame(rafId);
    };
  }, [anchorDateLabel, currentTimeLine, loading, roleLoading, view]);

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

  const handleOpenAttendance = React.useCallback(async () => {
    if (!selectedEvent) return;
    const attendanceDate = selectedEvent.start_datetime?.slice(0, 10);
    const batchParam = selectedEvent.batch_id ? `batch_id=${encodeURIComponent(String(selectedEvent.batch_id))}` : '';
    const dateParam = attendanceDate ? `date=${encodeURIComponent(attendanceDate)}` : '';
    const contextQuery = [batchParam, dateParam].filter(Boolean).join('&');
    const contextSuffix = contextQuery ? `&${contextQuery}` : '';
    try {
      if (selectedEvent.session_id) {
        navigate(`/attendance?session_id=${encodeURIComponent(String(selectedEvent.session_id))}${contextSuffix}`);
        return;
      }
      if (!attendanceDate || !selectedEvent.batch_id) {
        navigate('/attendance');
        return;
      }
      const payload = await openAttendanceSession({
        batch_id: Number(selectedEvent.batch_id),
        schedule_id: null,
        attendance_date: attendanceDate
      });
      const nextId = String(payload?.session_id || '');
      navigate(nextId ? `/attendance?session_id=${encodeURIComponent(nextId)}${contextSuffix}` : `/attendance?${contextQuery}`);
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to open attendance');
    }
  }, [navigate, selectedEvent]);

  const handleViewBatch = React.useCallback(() => {
    if (!selectedEvent?.batch_id) {
      navigate('/batches');
      return;
    }
    navigate(`/batches?batch_id=${encodeURIComponent(String(selectedEvent.batch_id))}`);
  }, [navigate, selectedEvent]);

  const handleCancelClass = React.useCallback(async () => {
    if (!selectedEvent) return;
    const confirmed = window.confirm('Cancel this class? This will create/update a calendar override.');
    if (!confirmed) return;
    try {
      const start = new Date(selectedEvent.start_datetime);
      const payload = {
        batch_id: Number(selectedEvent.batch_id),
        override_date: selectedEvent.start_datetime.slice(0, 10),
        new_start_time: `${String(start.getHours()).padStart(2, '0')}:${String(start.getMinutes()).padStart(2, '0')}`,
        new_duration_minutes: Number(selectedEvent.duration_minutes || 60),
        cancelled: true,
        reason: 'Cancelled from calendar modal'
      };
      if (selectedEvent.override_id) {
        await updateCalendarOverride(Number(selectedEvent.override_id), payload);
      } else {
        await createCalendarOverride(payload);
      }
      closeEventModal();
      await loadCalendar();
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to cancel class');
    }
  }, [closeEventModal, loadCalendar, selectedEvent]);

  const handleSendReminder = React.useCallback(() => {
    if (!selectedEvent?.batch_id) {
      navigate('/actions');
      return;
    }
    navigate(`/actions?batch_id=${encodeURIComponent(String(selectedEvent.batch_id))}`);
  }, [navigate, selectedEvent]);

  const selectedEventDate = selectedEvent?.start_datetime?.slice(0, 10) || '';
  const todayDate = toToday();
  const isSelectedEventFuture = Boolean(selectedEventDate && selectedEventDate > todayDate);
  const isSelectedEventPast = Boolean(selectedEventDate && selectedEventDate < todayDate);
  const isSelectedEventFinalized = selectedEvent?.status === 'completed' || selectedEvent?.status === 'cancelled';
  const selectedEventStatusUi = getEventStatusUi(selectedEvent?.status || 'upcoming');

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
                      <span className="calendar-event-title-wrap">
                        {event.is_current ? <span className="calendar-active-zap" title="Currently running"><FiZap /></span> : null}
                        <p className="calendar-event-title">{event.batch_name}</p>
                      </span>
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
            const dayHolidayNames = holidaysByDate[dayKey] || [];
            const visibleEvents = dayEvents.slice(0, 3);
            const moreCount = Math.max(0, dayEvents.length - visibleEvents.length);
            return (
              <div
                key={dayKey}
                ref={dayKey === todayKey ? monthTodayRef : null}
                className={`calendar-month-cell ${isOutside ? 'outside' : ''} ${dayKey === todayKey ? 'today' : ''}`}
              >
                <div className="calendar-month-date">{day.getDate()}</div>
                {dayHolidayNames.length ? (
                  <div className="calendar-month-holiday" title={dayHolidayNames.join(', ')}>
                    {dayHolidayNames[0]}
                  </div>
                ) : null}
                <div className="calendar-month-items">
                  {visibleEvents.map((event) => (
                    <button
                      key={event.uid}
                      type="button"
                      className={`calendar-event-card ${event.color_class || ''} compact`}
                      onClick={() => openEvent(event)}
                    >
                      <div className="calendar-event-head">
                        <span className="calendar-event-title-wrap">
                          {event.is_current ? <span className="calendar-active-zap" title="Currently running"><FiZap /></span> : null}
                          <p className="calendar-event-title">{event.batch_name}</p>
                        </span>
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
        heatmapByDay={heatmapByDay}
        heatmapEnabled={heatmapEnabled}
        holidaysByDate={holidaysByDate}
        showHolidays={view === 'week'}
        scrollContainerRef={gridScrollRef}
      />
    );
  };

  return (
    <section className="teacher-calendar-page">
      <CalendarHeader
        currentDate={headerDateLabel}
        anchorDate={anchorDateLabel}
        onAnchorDateChange={(value) => {
          if (!value) return;
          const next = new Date(value);
          if (Number.isNaN(next.getTime())) return;
          setAnchorDate(next);
        }}
        view={view}
        onViewChange={setView}
        onPrev={() => setAnchorDate((prev) => nextAnchor(prev, view, -1))}
        onNext={() => setAnchorDate((prev) => nextAnchor(prev, view, 1))}
        onToday={() => setAnchorDate(new Date())}
        filters={filters}
        onFiltersChange={setFilters}
        filterOptions={filterOptions}
        isAdmin={isAdmin}
        teacherId={teacherId}
        onTeacherIdChange={setTeacherId}
        heatmapEnabled={heatmapEnabled}
        onHeatmapToggle={setHeatmapEnabled}
      />

      <ErrorState message={error} />

      <div className="calendar-content-shell">
        <div className="calendar-content-topbar">
          <button type="button" className="calendar-refresh-btn" onClick={() => loadCalendar().catch(() => null)}>
            <FiRefreshCw /> Refresh
          </button>
          <div className="calendar-period-pill" aria-live="polite">
            <span className="calendar-period-pill-kicker">{view[0].toUpperCase() + view.slice(1)} view</span>
            <span className="calendar-period-pill-value">{periodPillLabel}</span>
          </div>
        </div>
        {mainContent()}
      </div>

      <button type="button" className="calendar-fab" onClick={startAddClass}>
        <FiPlus /> Add Class
      </button>

      <LiveClassPanel
        liveEvent={liveEvent}
        onOpenLiveEvent={openEvent}
      />

      <Modal
        open={Boolean(selectedEvent)}
        title={selectedEvent ? (
          <div className="calendar-event-modal-title-row">
            <span className={`${selectedEvent.is_current ? 'calendar-active-zap' : 'calendar-title-icon'} calendar-title-zap`}>
              <FiClock />
            </span>
            <span>{selectedEvent.batch_name}</span>
            <span className={`calendar-event-status-pill ${selectedEventStatusUi.className}`}>
              {selectedEventStatusUi.label}
            </span>
          </div>
        ) : 'Class'}
        onClose={closeEventModal}
        closeButtonText="×"
        closeButtonAriaLabel="Close event details"
        panelClassName="calendar-event-modal-panel"
        headerClassName="calendar-event-modal-header"
        titleClassName="calendar-event-modal-title"
        closeButtonClassName="calendar-event-modal-close"
        bodyClassName="calendar-event-modal-body-wrap"
      >
        {selectedEvent ? (
          <div className="calendar-modal-body">
            <p className="calendar-event-modal-time">
              <FiCalendar />
              <span>{formatEventDateLine(selectedEvent.start_datetime, selectedEvent.end_datetime)}</span>
            </p>
            <div className="calendar-event-modal-metrics">
              <span className="metric-students"><FiUsers /> {selectedEvent.student_count} Students</span>
              <span className="metric-fee"><FaIndianRupeeSign /> {selectedEvent.fee_due_count} Fee Due</span>
              <span className="metric-risk"><FiAlertTriangle /> {selectedEvent.risk_count} Risk</span>
            </div>
            {selectedSession?.topic_planned ? <p className="calendar-event-modal-plan"><strong>Plan:</strong> {selectedSession.topic_planned}</p> : null}
            <div className="calendar-modal-actions calendar-modal-actions-primary">
              {!isSelectedEventFuture ? (
                <button type="button" className="calendar-action-btn calendar-event-cta" onClick={handleOpenAttendance}>
                  {isSelectedEventPast ? 'Attendance Review' : 'Open Attendance'}
                </button>
              ) : null}
              <button type="button" className="calendar-action-btn" onClick={handleViewBatch}>View Batch</button>
              {!isSelectedEventFinalized ? (
                <button type="button" className="calendar-action-btn" onClick={startEditFromSelection}>Edit Schedule</button>
              ) : null}
            </div>
            {!isSelectedEventFinalized ? (
              <div className="calendar-modal-actions calendar-modal-actions-secondary">
                <button type="button" className="calendar-action-btn calendar-action-btn-icon" onClick={handleSendReminder}>
                  <FiBell /> Send Reminder
                </button>
                <button type="button" className="calendar-action-btn danger calendar-action-btn-icon" onClick={handleCancelClass}>
                  <FiAlertTriangle /> Cancel Class
                </button>
              </div>
            ) : null}
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

