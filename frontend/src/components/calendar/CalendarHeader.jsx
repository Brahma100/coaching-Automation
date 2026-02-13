import React from 'react';
import { FiChevronLeft, FiChevronRight, FiFilter } from 'react-icons/fi';
import Modal from '../Modal.jsx';

const VIEW_OPTIONS = ['day', 'week', 'month', 'agenda'];
const VIEW_LABELS = {
  day: '1D',
  week: '7D',
  month: '30D',
  agenda: 'Agenda',
};

const CalendarHeader = React.memo(function CalendarHeader({
  currentDate,
  view,
  onViewChange,
  onPrev,
  onNext,
  onToday,
  anchorDate,
  onAnchorDateChange,
  filters,
  onFiltersChange,
  filterOptions,
  isAdmin,
  teacherId,
  onTeacherIdChange,
  heatmapEnabled,
  onHeatmapToggle
}) {
  const [filterModalOpen, setFilterModalOpen] = React.useState(false);
  const [draftAnchorDate, setDraftAnchorDate] = React.useState(anchorDate || '');
  const [draftFilters, setDraftFilters] = React.useState(filters);
  const [draftTeacherId, setDraftTeacherId] = React.useState(teacherId || '');
  const [draftHeatmapEnabled, setDraftHeatmapEnabled] = React.useState(Boolean(heatmapEnabled));

  React.useEffect(() => {
    if (!filterModalOpen) return;
    setDraftAnchorDate(anchorDate || '');
    setDraftFilters(filters);
    setDraftTeacherId(teacherId || '');
    setDraftHeatmapEnabled(Boolean(heatmapEnabled));
  }, [anchorDate, filterModalOpen, filters, heatmapEnabled, teacherId]);

  const applyFilters = () => {
    onAnchorDateChange?.(draftAnchorDate);
    onFiltersChange?.(draftFilters);
    onTeacherIdChange?.(draftTeacherId);
    onHeatmapToggle?.(draftHeatmapEnabled);
    setFilterModalOpen(false);
  };

  const hasActiveFilters = Boolean(
    filters.search
    || filters.subject
    || filters.academicLevel
    || (isAdmin && teacherId)
    || heatmapEnabled
  );

  return (
    <header className="calendar-header-shell">
      <div className="calendar-header-top">
        <div className="calendar-view-switch" role="tablist" aria-label="Calendar view switch">
          {VIEW_OPTIONS.map((option) => (
            <button
              key={option}
              type="button"
              className={`calendar-view-btn ${view === option ? 'active' : ''}`}
              onClick={() => onViewChange(option)}
            >
              {VIEW_LABELS[option] || option}
            </button>
          ))}
          <button
            type="button"
            className={`calendar-view-btn ${hasActiveFilters ? 'active' : ''}`}
            onClick={() => setFilterModalOpen(true)}
            aria-label="Open filters"
            title="Open filters"
          >
            <FiFilter />
          </button>
        </div>
        <div className="calendar-header-actions">
          <button type="button" className="calendar-nav-btn" onClick={onPrev} aria-label="Previous period">
            <FiChevronLeft />
          </button>
          <button type="button" className="calendar-nav-btn calendar-nav-date-btn" onClick={onToday} title="Jump to today">
            {currentDate}
          </button>
          <button type="button" className="calendar-nav-btn" onClick={onNext} aria-label="Next period">
            <FiChevronRight />
          </button>
        </div>
      </div>

      <Modal
        open={filterModalOpen}
        title="Calendar Filters"
        onClose={() => setFilterModalOpen(false)}
        panelClassName="calendar-filter-modal-panel"
        headerClassName="calendar-filter-modal-header"
        closeButtonClassName="calendar-filter-modal-close"
        bodyClassName="calendar-filter-modal-body"
        footerClassName="calendar-filter-modal-footer"
        footer={(
          <div className="calendar-filter-modal-actions">
            <button type="button" className="calendar-action-btn calendar-filter-cancel-btn" onClick={() => setFilterModalOpen(false)}>
              Cancel
            </button>
            <button type="button" className="calendar-action-btn calendar-filter-apply-btn" onClick={applyFilters}>
              Apply
            </button>
          </div>
        )}
      >
        <div className="calendar-filter-modal-intro">
          Adjust calendar visibility and narrow sessions quickly.
        </div>
        <div className="calendar-filter-modal-grid">
          <label className="calendar-filter-field">
            Date
            <input
              type="date"
              className="calendar-filter-input"
              value={draftAnchorDate}
              onChange={(event) => setDraftAnchorDate(event.target.value)}
            />
          </label>
          <label className="calendar-filter-field">
            Heatmap
            <select
              className="calendar-filter-input"
              value={draftHeatmapEnabled ? 'on' : 'off'}
              onChange={(event) => setDraftHeatmapEnabled(event.target.value === 'on')}
            >
              <option value="off">Off</option>
              <option value="on">On</option>
            </select>
          </label>
          <label className="calendar-filter-field">
            Batch
            <select
              className="calendar-filter-input"
              value={draftFilters.search || ''}
              onChange={(event) => setDraftFilters((prev) => ({ ...prev, search: event.target.value }))}
            >
              <option value="">All</option>
              {(filterOptions?.batches || []).map((value) => (
                <option key={`batch-${value}`} value={value}>{value}</option>
              ))}
            </select>
          </label>
          <label className="calendar-filter-field">
            Subject
            <select
              className="calendar-filter-input"
              value={draftFilters.subject || ''}
              onChange={(event) => setDraftFilters((prev) => ({ ...prev, subject: event.target.value }))}
            >
              <option value="">All</option>
              {(filterOptions?.subjects || []).map((value) => (
                <option key={`subject-${value}`} value={value}>{value}</option>
              ))}
            </select>
          </label>
          <label className="calendar-filter-field">
            Academic level
            <select
              className="calendar-filter-input"
              value={draftFilters.academicLevel || ''}
              onChange={(event) => setDraftFilters((prev) => ({ ...prev, academicLevel: event.target.value }))}
            >
              <option value="">All</option>
              {(filterOptions?.academicLevels || []).map((value) => (
                <option key={`level-${value}`} value={value}>{value}</option>
              ))}
            </select>
          </label>
          {isAdmin ? (
            <label className="calendar-filter-field">
              Teacher ID
              <input
                className="calendar-filter-input"
                value={draftTeacherId}
                onChange={(event) => setDraftTeacherId(event.target.value)}
                placeholder="Teacher ID"
              />
            </label>
          ) : null}
        </div>
      </Modal>
    </header>
  );
});

export default CalendarHeader;
