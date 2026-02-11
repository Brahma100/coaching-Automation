import React from 'react';
import { FiChevronLeft, FiChevronRight, FiFilter } from 'react-icons/fi';

const VIEW_OPTIONS = ['day', 'week', 'month', 'agenda'];

const CalendarHeader = React.memo(function CalendarHeader({
  currentDate,
  view,
  onViewChange,
  onPrev,
  onNext,
  onToday,
  filters,
  onFiltersChange,
  isAdmin,
  teacherId,
  onTeacherIdChange,
  heatmapEnabled,
  onHeatmapToggle
}) {
  return (
    <header className="calendar-header-shell">
      <div className="calendar-header-top">
        <div>
          <p className="calendar-eyebrow">Teacher Calendar</p>
          <h2 className="calendar-title">Coaching Schedule Planner</h2>
        </div>
        <div className="calendar-header-actions">
          <button type="button" className="calendar-nav-btn" onClick={onPrev} aria-label="Previous period">
            <FiChevronLeft />
          </button>
          <button type="button" className="calendar-nav-btn" onClick={onToday}>Today</button>
          <button type="button" className="calendar-nav-btn" onClick={onNext} aria-label="Next period">
            <FiChevronRight />
          </button>
        </div>
      </div>

      <div className="calendar-header-bottom">
        <div className="calendar-view-switch" role="tablist" aria-label="Calendar view switch">
          {VIEW_OPTIONS.map((option) => (
            <button
              key={option}
              type="button"
              className={`calendar-view-btn ${view === option ? 'active' : ''}`}
              onClick={() => onViewChange(option)}
            >
              {option[0].toUpperCase() + option.slice(1)}
            </button>
          ))}
        </div>

        <div className="calendar-filter-bar">
          <div className="calendar-filter-chip">
            <FiFilter />
            <span>{currentDate}</span>
          </div>
          <button
            type="button"
            className={`calendar-view-btn ${heatmapEnabled ? 'active' : ''}`}
            onClick={() => onHeatmapToggle?.(!heatmapEnabled)}
          >
            {heatmapEnabled ? 'Heatmap On' : 'Heatmap'}
          </button>
          <input
            value={filters.search}
            onChange={(event) => onFiltersChange({ ...filters, search: event.target.value })}
            placeholder="Search batch"
            className="calendar-filter-input"
          />
          <input
            value={filters.subject}
            onChange={(event) => onFiltersChange({ ...filters, subject: event.target.value })}
            placeholder="Subject"
            className="calendar-filter-input"
          />
          <input
            value={filters.academicLevel}
            onChange={(event) => onFiltersChange({ ...filters, academicLevel: event.target.value })}
            placeholder="Academic level"
            className="calendar-filter-input"
          />
          <label className="calendar-filter-toggle">
            <input
              type="checkbox"
              checked={filters.hideInactive}
              onChange={(event) => onFiltersChange({ ...filters, hideInactive: event.target.checked })}
            />
            Hide inactive
          </label>
          {isAdmin ? (
            <input
              value={teacherId}
              onChange={(event) => onTeacherIdChange(event.target.value)}
              placeholder="Teacher ID"
              className="calendar-filter-input calendar-teacher-input"
            />
          ) : null}
        </div>
      </div>
    </header>
  );
});

export default CalendarHeader;
