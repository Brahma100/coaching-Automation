import React from 'react';

const SUBJECT_TONES = [
  'calendar-tone-math',
  'calendar-tone-science',
  'calendar-tone-language',
  'calendar-tone-social',
  'calendar-tone-default',
];

function toneForSubject(subject = '') {
  let hash = 0;
  for (let i = 0; i < subject.length; i += 1) {
    hash = (hash + subject.charCodeAt(i)) % SUBJECT_TONES.length;
  }
  return SUBJECT_TONES[hash] || SUBJECT_TONES[SUBJECT_TONES.length - 1];
}

const CalendarEventCard = React.memo(function CalendarEventCard({ event, compact = false, onClick }) {
  const toneClass = toneForSubject(event.subject || 'General');
  const startLabel = new Date(event.start_datetime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const endLabel = new Date(event.end_datetime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <button
      type="button"
      onClick={() => onClick(event)}
      className={`calendar-event-card ${toneClass} ${compact ? 'compact' : ''}`}
    >
      <div className="calendar-event-head">
        <p className="calendar-event-title">{event.batch_name}</p>
        {event.status === 'live' ? <span className="calendar-live-pill">LIVE</span> : null}
      </div>
      <p className="calendar-event-time">{startLabel} - {endLabel}</p>
      <p className="calendar-event-meta">{event.student_count} students</p>
      <div className="calendar-event-badges">
        {event.fee_due_count > 0 ? <span className="calendar-badge fee">Fee {event.fee_due_count}</span> : null}
        {event.risk_count > 0 ? <span className="calendar-badge risk">Risk {event.risk_count}</span> : null}
      </div>
    </button>
  );
});

export default CalendarEventCard;
