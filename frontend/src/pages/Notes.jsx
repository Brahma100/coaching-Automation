import React from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { FiCalendar, FiCheckCircle, FiClock, FiDownload, FiEdit2, FiFileText, FiGrid, FiInfo, FiLink, FiList, FiSearch, FiTrash2, FiUpload, FiX } from 'react-icons/fi';

import SkeletonBlock from '../components/Skeleton.jsx';
import Accordion from '../components/ui/Accordion.jsx';
import ConfirmModal from '../components/ui/ConfirmModal.jsx';
import Toast from '../components/ui/Toast.jsx';
import {
  deleteNote,
  disconnectDrive,
  downloadNote,
  fetchDriveStatus,
  fetchTeacherProfile,
  fetchNotes,
  fetchNotesAnalytics,
  fetchNotesMetadata,
  updateNote,
  uploadNote
} from '../services/api';
import useRole from '../hooks/useRole';

function bytesToDisplay(bytes) {
  const value = Number(bytes || 0);
  if (!value) return '0 KB';
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / (1024 * 1024)).toFixed(2)} MB`;
}

function formatDateTime(value) {
  if (!value) return '-';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '-';
  return parsed.toLocaleString();
}

function toDateTimeLocalValue(value) {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '';
  const shifted = new Date(parsed.getTime() - parsed.getTimezoneOffset() * 60000);
  return shifted.toISOString().slice(0, 16);
}

function normalizeTags(rawTags) {
  if (!Array.isArray(rawTags)) return [];
  const values = rawTags
    .map((entry) => {
      if (typeof entry === 'string') return entry.trim();
      if (entry && typeof entry.name === 'string') return entry.name.trim();
      return '';
    })
    .filter(Boolean);
  return [...new Set(values)];
}

function ModernProgress({ value = 0, indeterminate = false, tone = 'blue' }) {
  const fillTone = tone === 'emerald' ? 'from-emerald-500 to-teal-500' : 'from-[#2f7bf6] to-sky-500';
  return (
    <div className="relative h-2.5 overflow-hidden rounded-full bg-slate-200/90 ring-1 ring-slate-300/40">
      {indeterminate ? (
        <motion.div
          className={`absolute inset-y-0 w-1/3 rounded-full bg-gradient-to-r ${fillTone}`}
          initial={{ x: '-140%' }}
          animate={{ x: '320%' }}
          transition={{ repeat: Infinity, duration: 1.1, ease: 'linear' }}
        />
      ) : (
        <motion.div
          className={`absolute inset-y-0 left-0 rounded-full bg-gradient-to-r ${fillTone} bg-[length:220%_100%]`}
          animate={{ width: `${Math.max(0, Math.min(100, value))}%`, backgroundPosition: ['0% 50%', '100% 50%'] }}
          transition={{ width: { duration: 0.25, ease: 'easeOut' }, backgroundPosition: { repeat: Infinity, duration: 1.8, ease: 'linear' } }}
        />
      )}
    </div>
  );
}

function Notes() {
  const { isTeacher, isAdmin } = useRole();
  const canUpload = isTeacher || isAdmin;

  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');
  const [notes, setNotes] = React.useState([]);
  const [metadata, setMetadata] = React.useState({ subjects: [], chapters: [], topics: [], tags: [], batches: [] });
  const [analytics, setAnalytics] = React.useState({ total_notes: 0, total_subjects: 0, total_tags: 0, total_downloads: 0 });
  const [viewMode, setViewMode] = React.useState('grid');
  const [showUpload, setShowUpload] = React.useState(false);
  const [editingNoteId, setEditingNoteId] = React.useState(null);
  const [uploading, setUploading] = React.useState(false);
  const [uploadState, setUploadState] = React.useState({ progress: 0, phase: 'idle' });
  const [downloadingId, setDownloadingId] = React.useState(null);
  const [downloadState, setDownloadState] = React.useState({});
  const [deleteTarget, setDeleteTarget] = React.useState(null);
  const [deletingId, setDeletingId] = React.useState(null);
  const [toast, setToast] = React.useState({ open: false, tone: 'info', message: '' });
  const [autoDeleteOnExpiryEnabled, setAutoDeleteOnExpiryEnabled] = React.useState(false);
  const [driveConnected, setDriveConnected] = React.useState(false);
  const [driveStatusLoading, setDriveStatusLoading] = React.useState(false);
  const [driveDisconnecting, setDriveDisconnecting] = React.useState(false);
  const [expiryTick, setExpiryTick] = React.useState(Date.now());
  const autoDeleteInFlightRef = React.useRef(false);
  const autoDeleteHandledRef = React.useRef(new Set());
  const [pagination, setPagination] = React.useState({ page: 1, page_size: 12, total: 0, total_pages: 1 });

  const [filters, setFilters] = React.useState({
    search: '',
    batch_id: '',
    subject_id: '',
    topic_id: '',
    tag: '',
    page: 1,
    page_size: 12
  });

  const [form, setForm] = React.useState({
    title: '',
    description: '',
    subject_id: '',
    subject_name: '',
    chapter_id: '',
    chapter_name: '',
    topic_id: '',
    topic_name: '',
    batch_ids: [],
    tags: [],
    custom_tags: '',
    visible_to_students: true,
    visible_to_parents: false,
    release_at: '',
    expire_at: '',
    file: null
  });

  const subjectOptions = metadata.subjects || [];
  const hasSubjectList = subjectOptions.length > 0;
  const hasChapterList = (metadata.chapters || []).length > 0;
  const hasTopicList = (metadata.topics || []).length > 0;
  const chapterOptions = React.useMemo(
    () => {
      const subjectRef = String(form.subject_id || '');
      if (!subjectRef) return metadata.chapters || [];
      return (metadata.chapters || []).filter((row) => String(row.subject_id) === subjectRef);
    },
    [metadata.chapters, form.subject_id]
  );
  const topicOptions = React.useMemo(() => {
    if (form.chapter_id) {
      return (metadata.topics || []).filter((row) => String(row.chapter_id) === String(form.chapter_id));
    }
    if (!form.subject_id) {
      return metadata.topics || [];
    }
    return (metadata.topics || []).filter((row) => {
      const chapter = (metadata.chapters || []).find((candidate) => candidate.id === row.chapter_id);
      return chapter && String(chapter.subject_id) === String(form.subject_id || '');
    });
  }, [metadata.topics, metadata.chapters, form.chapter_id, form.subject_id]);

  const topicFilterOptions = React.useMemo(() => {
    if (!filters.subject_id) return metadata.topics || [];
    return (metadata.topics || []).filter((topic) => {
      const chapter = (metadata.chapters || []).find((candidate) => candidate.id === topic.chapter_id);
      return chapter && String(chapter.subject_id) === String(filters.subject_id);
    });
  }, [metadata.topics, metadata.chapters, filters.subject_id]);

  const totalTagCount = React.useMemo(() => {
    const analyticsCount = Number(analytics.total_tags || 0);
    const metadataCount = Array.isArray(metadata.tags) ? metadata.tags.length : 0;
    const notesCount = new Set((notes || []).flatMap((note) => normalizeTags(note.tags))).size;
    return Math.max(analyticsCount, metadataCount, notesCount);
  }, [analytics.total_tags, metadata.tags, notes]);

  const loadAll = React.useCallback(async () => {
    setError('');
    try {
      const [notePayload, metaPayload, analyticsPayload] = await Promise.all([
        fetchNotes(filters),
        fetchNotesMetadata(),
        fetchNotesAnalytics()
      ]);
      setNotes(notePayload?.items || []);
      setPagination(notePayload?.pagination || { page: 1, page_size: 12, total: 0, total_pages: 1 });
      setMetadata(metaPayload || { subjects: [], chapters: [], topics: [], tags: [], batches: [] });
      setAnalytics(analyticsPayload || { total_notes: 0, total_subjects: 0, total_tags: 0, total_downloads: 0 });
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to load notes');
    } finally {
      setLoading(false);
    }
  }, [filters]);

  React.useEffect(() => {
    let mounted = true;
    (async () => {
      if (!mounted) return;
      await loadAll();
    })();
    return () => {
      mounted = false;
    };
  }, [loadAll]);

  React.useEffect(() => {
    let mounted = true;
    if (!canUpload) {
      setAutoDeleteOnExpiryEnabled(false);
      return () => {
        mounted = false;
      };
    }
    (async () => {
      try {
        const profile = await fetchTeacherProfile();
        if (!mounted) return;
        setAutoDeleteOnExpiryEnabled(Boolean(profile?.enable_auto_delete_notes_on_expiry));
      } catch {
        if (!mounted) return;
        setAutoDeleteOnExpiryEnabled(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [canUpload]);

  React.useEffect(() => {
    let mounted = true;
    if (!isAdmin) {
      setDriveConnected(false);
      return () => {
        mounted = false;
      };
    }
    (async () => {
      setDriveStatusLoading(true);
      try {
        const status = await fetchDriveStatus();
        if (!mounted) return;
        setDriveConnected(Boolean(status?.connected));
      } catch {
        if (!mounted) return;
        setDriveConnected(false);
      } finally {
        if (mounted) setDriveStatusLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [isAdmin]);

  React.useEffect(() => {
    if (!isAdmin) return undefined;
    const refreshOnFocus = async () => {
      try {
        const status = await fetchDriveStatus();
        setDriveConnected(Boolean(status?.connected));
      } catch {
        setDriveConnected(false);
      }
    };
    window.addEventListener('focus', refreshOnFocus);
    return () => window.removeEventListener('focus', refreshOnFocus);
  }, [isAdmin]);

  React.useEffect(() => {
    if (!canUpload || !autoDeleteOnExpiryEnabled) return undefined;
    const timer = window.setInterval(() => setExpiryTick(Date.now()), 30000);
    return () => window.clearInterval(timer);
  }, [autoDeleteOnExpiryEnabled, canUpload]);

  React.useEffect(() => {
    if (!canUpload || !autoDeleteOnExpiryEnabled || loading || autoDeleteInFlightRef.current) return;
    const now = Number(expiryTick || Date.now());
    const expiredIds = (notes || [])
      .filter((note) => {
        if (!note?.expire_at) return false;
        const when = new Date(note.expire_at).getTime();
        if (!Number.isFinite(when)) return false;
        return when <= now && !autoDeleteHandledRef.current.has(note.id);
      })
      .map((note) => note.id);

    if (!expiredIds.length) return;
    autoDeleteInFlightRef.current = true;
    expiredIds.forEach((id) => autoDeleteHandledRef.current.add(id));

    (async () => {
      const results = await Promise.allSettled(expiredIds.map((id) => deleteNote(id)));
      const successCount = results.filter((row) => row.status === 'fulfilled').length;
      const failedCount = results.length - successCount;

      if (successCount > 0) {
        setToast({
          open: true,
          tone: 'info',
          message: `${successCount} expired note${successCount > 1 ? 's were' : ' was'} auto-deleted.`,
        });
        await loadAll();
      }

      if (failedCount > 0) {
        setToast({
          open: true,
          tone: 'error',
          message: `${failedCount} expired note${failedCount > 1 ? 's' : ''} could not be auto-deleted.`,
        });
      }
    })().finally(() => {
      autoDeleteInFlightRef.current = false;
    });
  }, [autoDeleteOnExpiryEnabled, canUpload, expiryTick, loadAll, loading, notes]);

  const updateFilter = (key, value) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value,
      page: key === 'page' ? value : 1
    }));
  };

  const toggleBatch = (batchId) => {
    setForm((prev) => {
      const exists = prev.batch_ids.includes(batchId);
      return {
        ...prev,
        batch_ids: exists ? prev.batch_ids.filter((id) => id !== batchId) : [...prev.batch_ids, batchId]
      };
    });
  };

  const toggleTag = (tagName) => {
    setForm((prev) => {
      const exists = prev.tags.includes(tagName);
      return {
        ...prev,
        tags: exists ? prev.tags.filter((name) => name !== tagName) : [...prev.tags, tagName]
      };
    });
  };

  const resetForm = () => {
    setForm({
      title: '',
      description: '',
      subject_id: '',
      subject_name: '',
      chapter_id: '',
      chapter_name: '',
      topic_id: '',
      topic_name: '',
      batch_ids: [],
      tags: [],
      custom_tags: '',
      visible_to_students: true,
      visible_to_parents: false,
      release_at: '',
      expire_at: '',
      file: null
    });
    setUploadState({ progress: 0, phase: 'idle' });
  };

  const openUploadModal = () => {
    setError('');
    setEditingNoteId(null);
    resetForm();
    setShowUpload(true);
  };

  const closeUploadModal = () => {
    if (uploading) return;
    setShowUpload(false);
    setEditingNoteId(null);
    resetForm();
  };

  const openEditModal = (note) => {
    setError('');
    setEditingNoteId(note.id);
    setForm({
      title: note.title || '',
      description: note.description || '',
      subject_id: note.subject_id ? String(note.subject_id) : '',
      subject_name: '',
      chapter_id: note.chapter_id ? String(note.chapter_id) : '',
      chapter_name: '',
      topic_id: note.topic_id ? String(note.topic_id) : '',
      topic_name: '',
      batch_ids: (note.batches || []).map((batch) => Number(batch.id)).filter((id) => Number.isFinite(id)),
      tags: normalizeTags(note.tags),
      custom_tags: '',
      visible_to_students: Boolean(note.visible_to_students),
      visible_to_parents: Boolean(note.visible_to_parents),
      release_at: toDateTimeLocalValue(note.release_at),
      expire_at: toDateTimeLocalValue(note.expire_at),
      file: null
    });
    setUploadState({ progress: 0, phase: 'idle' });
    setShowUpload(true);
  };

  const handleUpload = async (event) => {
    event.preventDefault();
    const isEditing = Boolean(editingNoteId);
    if (!isEditing && !form.file) {
      setError('Please choose a PDF file');
      return;
    }
    if (!form.batch_ids.length) {
      setError('Please select at least one batch');
      return;
    }

    setError('');
    setUploading(true);
    setUploadState({ progress: 0, phase: 'uploading' });

    try {
      const payload = new FormData();
      payload.append('title', form.title);
      payload.append('description', form.description || '');
      if (form.subject_id) payload.append('subject_id', String(form.subject_id));
      if (form.subject_name.trim()) payload.append('subject_name', form.subject_name.trim());
      if (form.chapter_id) payload.append('chapter_id', String(form.chapter_id));
      if (form.chapter_name.trim()) payload.append('chapter_name', form.chapter_name.trim());
      if (form.topic_id) payload.append('topic_id', String(form.topic_id));
      if (form.topic_name.trim()) payload.append('topic_name', form.topic_name.trim());
      payload.append('batch_ids', JSON.stringify(form.batch_ids));

      const customTags = form.custom_tags
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean);
      payload.append('tags', JSON.stringify([...form.tags, ...customTags]));
      payload.append('visible_to_students', form.visible_to_students ? 'true' : 'false');
      payload.append('visible_to_parents', form.visible_to_parents ? 'true' : 'false');
      if (form.release_at) payload.append('release_at', new Date(form.release_at).toISOString());
      if (form.expire_at) payload.append('expire_at', new Date(form.expire_at).toISOString());
      if (form.file) payload.append('file', form.file);

      const applyProgress = (value) => {
        const bounded = Math.max(0, Math.min(100, Number(value) || 0));
        setUploadState({
          progress: bounded >= 99 ? 99 : bounded,
          phase: bounded >= 99 ? 'processing' : 'uploading'
        });
      };
      const result = isEditing
        ? await updateNote(editingNoteId, payload, applyProgress)
        : await uploadNote(payload, applyProgress);
      setUploadState({ progress: 100, phase: 'done' });
      await new Promise((resolve) => setTimeout(resolve, 260));
      await loadAll();
      setShowUpload(false);
      setEditingNoteId(null);
      resetForm();
      setToast({
        open: true,
        tone: 'success',
        message: result?.warning || (isEditing ? 'Note updated successfully' : 'Note uploaded successfully')
      });
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || (isEditing ? 'Update failed' : 'Upload failed'));
      setUploadState((prev) => ({ ...prev, phase: 'error' }));
    } finally {
      setUploading(false);
      setTimeout(() => setUploadState({ progress: 0, phase: 'idle' }), 400);
    }
  };

  const handleDownload = async (noteId) => {
    setDownloadingId(noteId);
    setDownloadState((prev) => ({ ...prev, [noteId]: { progress: 0, phase: 'downloading' } }));
    try {
      await downloadNote(noteId, (value) => {
        const bounded = Math.max(0, Math.min(100, Number(value) || 0));
        setDownloadState((prev) => ({
          ...prev,
          [noteId]: {
            progress: bounded >= 99 ? 99 : bounded,
            phase: bounded >= 99 ? 'processing' : 'downloading'
          }
        }));
      });
      setDownloadState((prev) => ({ ...prev, [noteId]: { progress: 100, phase: 'done' } }));
      await loadAll();
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Download failed');
      setDownloadState((prev) => ({ ...prev, [noteId]: { progress: 0, phase: 'error' } }));
    } finally {
      setDownloadingId(null);
      setTimeout(() => {
        setDownloadState((prev) => {
          const next = { ...prev };
          delete next[noteId];
          return next;
        });
      }, 850);
    }
  };

  const openDeleteModal = (note) => {
    setDeleteTarget(note);
  };

  const closeDeleteModal = () => {
    if (deletingId) return;
    setDeleteTarget(null);
  };

  const confirmDelete = async () => {
    if (!deleteTarget?.id) return;
    setDeletingId(deleteTarget.id);
    setError('');
    try {
      await deleteNote(deleteTarget.id);
      setToast({ open: true, tone: 'success', message: 'Note deleted successfully' });
      setDeleteTarget(null);
      await loadAll();
    } catch (err) {
      const message = err?.response?.data?.detail || err?.message || 'Delete failed';
      setError(message);
      setToast({ open: true, tone: 'error', message });
    } finally {
      setDeletingId(null);
    }
  };

  const handleDisconnectDrive = async () => {
    if (!isAdmin || driveDisconnecting) return;
    const confirmed = window.confirm('Disconnect Google Drive? Upload/download via Drive will stop until reconnect.');
    if (!confirmed) return;
    setDriveDisconnecting(true);
    try {
      await disconnectDrive();
      setDriveConnected(false);
      setToast({ open: true, tone: 'info', message: 'Google Drive disconnected' });
    } catch (err) {
      const message = err?.response?.data?.detail || err?.message || 'Could not disconnect Drive';
      setToast({ open: true, tone: 'error', message });
    } finally {
      setDriveDisconnecting(false);
    }
  };

  const renderSkeleton = () => (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {[...Array(6)].map((_, index) => (
        <div key={`skeleton-${index}`} className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
          <SkeletonBlock className="mb-3 h-5 w-2/3" />
          <SkeletonBlock className="mb-2 h-4 w-1/2" />
          <SkeletonBlock className="mb-4 h-4 w-1/3" />
          <SkeletonBlock className="h-9 w-full" />
        </div>
      ))}
    </div>
  );

  return (
    <section className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-[30px] font-extrabold text-slate-900">Notes</h2>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setViewMode('grid')}
              title="Grid view"
              aria-label="Grid view"
              className={`rounded-lg border px-3 py-2 text-sm font-semibold ${viewMode === 'grid' ? 'border-[#2f7bf6] bg-[#e6f0ff] text-[#2f7bf6]' : 'border-slate-300 text-slate-700'}`}
            >
              <FiGrid className="inline" />
              <span className="ml-1 hidden sm:inline">Grid</span>
            </button>
            <button
              type="button"
              onClick={() => setViewMode('list')}
              title="List view"
              aria-label="List view"
              className={`rounded-lg border px-3 py-2 text-sm font-semibold ${viewMode === 'list' ? 'border-[#2f7bf6] bg-[#e6f0ff] text-[#2f7bf6]' : 'border-slate-300 text-slate-700'}`}
            >
              <FiList className="inline" />
              <span className="ml-1 hidden sm:inline">List</span>
            </button>
            {canUpload ? (
              <button
                type="button"
                onClick={openUploadModal}
                title="Upload note"
                aria-label="Upload note"
                className="rounded-lg bg-[#2f7bf6] px-4 py-2 text-sm font-semibold text-white"
              >
                <FiUpload className="inline" />
                <span className="ml-1 hidden sm:inline">Upload</span>
              </button>
            ) : null}
            {isAdmin ? (
              driveConnected ? (
                <div className="inline-flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-700">
                  <FiCheckCircle className="inline" />
                  <span className="hidden sm:inline">Drive Connected</span>
                  <button
                    type="button"
                    title="Disconnect Google Drive"
                    aria-label="Disconnect Google Drive"
                    disabled={driveDisconnecting || driveStatusLoading}
                    onClick={handleDisconnectDrive}
                    className="inline-flex h-6 w-6 items-center justify-center rounded-md border border-rose-200 bg-rose-50 text-rose-600 hover:bg-rose-100 disabled:opacity-60"
                  >
                    <FiX className="h-3.5 w-3.5" />
                  </button>
                </div>
              ) : (
                <a
                  href="/backend/api/drive/oauth/start"
                  target="_blank"
                  rel="noreferrer"
                  title="Connect Google Drive"
                  aria-label="Connect Google Drive"
                  className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                >
                  <FiLink className="inline" />
                  <span className="ml-1 hidden sm:inline">Connect Google Drive</span>
                </a>
              )
            ) : null}
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-xl bg-blue-50 p-3">
            <p className="text-xs text-blue-700">Total Notes</p>
            <p className="text-2xl font-bold text-blue-800">{analytics.total_notes || 0}</p>
          </div>
          <div className="rounded-xl bg-emerald-50 p-3">
            <p className="text-xs text-emerald-700">Subjects</p>
            <p className="text-2xl font-bold text-emerald-800">{analytics.total_subjects || 0}</p>
          </div>
          <div className="rounded-xl bg-amber-50 p-3">
            <p className="text-xs text-amber-700">Tags</p>
            <p className="text-2xl font-bold text-amber-800">{totalTagCount}</p>
          </div>
          <div className="rounded-xl bg-slate-100 p-3">
            <p className="text-xs text-slate-600">Downloads</p>
            <p className="text-2xl font-bold text-slate-700">{analytics.total_downloads || 0}</p>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <div className="grid gap-3 md:grid-cols-5">
          <label className="relative md:col-span-2">
            <FiSearch className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              value={filters.search}
              onChange={(event) => updateFilter('search', event.target.value)}
              placeholder="Search notes"
              className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm"
            />
          </label>
          <select className="rounded-lg border border-slate-300 px-3 py-2 text-sm" value={filters.subject_id} onChange={(event) => updateFilter('subject_id', event.target.value)}>
            <option value="">All subjects</option>
            {subjectOptions.map((subject) => (
              <option key={subject.id} value={subject.id}>{subject.name}</option>
            ))}
          </select>
          <select className="rounded-lg border border-slate-300 px-3 py-2 text-sm" value={filters.topic_id} onChange={(event) => updateFilter('topic_id', event.target.value)}>
            <option value="">All topics</option>
            {topicFilterOptions.map((topic) => (
              <option key={topic.id} value={topic.id}>{topic.name}</option>
            ))}
          </select>
          <select className="rounded-lg border border-slate-300 px-3 py-2 text-sm" value={filters.batch_id} onChange={(event) => updateFilter('batch_id', event.target.value)}>
            <option value="">All batches</option>
            {(metadata.batches || []).map((batch) => (
              <option key={batch.id} value={batch.id}>{batch.name}</option>
            ))}
          </select>
        </div>
      </div>

      {error ? <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p> : null}

      {loading ? renderSkeleton() : null}

      {!loading ? (
        <div className={viewMode === 'grid' ? 'grid items-start gap-4 sm:grid-cols-2 xl:grid-cols-3' : 'space-y-3'}>
          <AnimatePresence>
            {notes.map((note) => {
              const state = downloadState[note.id] || { progress: 0, phase: 'idle' };
              const progress = state.progress || 0;
              const indeterminate = state.phase === 'processing';
              const noteTags = normalizeTags(note.tags);
              return (
                <motion.article
                  key={note.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.2 }}
                  className="self-start overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-md dark:border-slate-800 dark:bg-slate-900"
                >
                  <div className={`p-4 ${viewMode === 'list' ? 'flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between' : ''}`}>
                    <div className={viewMode === 'list' ? 'min-w-0 flex-1' : ''}>
                      <h3 className="truncate text-base font-bold text-slate-900">{note.title}</h3>
                      <p className="mt-1 text-xs text-slate-500">
                        {note.subject || 'General'}
                        {note.chapter ? ` • ${note.chapter}` : ''}
                        {note.topic ? ` • ${note.topic}` : ''}
                      </p>
                      <div className="mt-2 flex flex-wrap gap-1">
                        {noteTags.map((tag) => (
                          <span key={`${note.id}-${tag}`} className="rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-700 ring-1 ring-amber-100">
                            {tag}
                          </span>
                        ))}
                      </div>
                      <div className="mt-2 flex flex-wrap gap-1">
                        {(note.batches || []).map((batch) => (
                          <span key={`${note.id}-batch-${batch.id}`} className="rounded-md bg-blue-50 px-2 py-0.5 text-[11px] font-semibold text-blue-700 ring-1 ring-blue-100">
                            {batch.name}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div className={viewMode === 'list' ? 'w-full sm:w-auto sm:shrink-0 sm:self-start' : 'mt-3'}>
                      <div className="flex items-center justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => handleDownload(note.id)}
                          disabled={downloadingId === note.id}
                          title="Download note"
                          aria-label="Download note"
                          className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-gradient-to-r from-[#2f7bf6] to-sky-500 text-white shadow-sm transition hover:from-[#246be0] hover:to-sky-600 disabled:opacity-60"
                        >
                          <FiDownload />
                        </button>
                        {canUpload ? (
                          <button
                            type="button"
                            title="Edit note"
                            aria-label="Edit note"
                            onClick={() => openEditModal(note)}
                            disabled={Boolean(deletingId)}
                            className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-slate-50 text-slate-600 transition hover:bg-slate-100 disabled:opacity-60"
                          >
                            <FiEdit2 />
                          </button>
                        ) : null}
                        {canUpload ? (
                          <button
                            type="button"
                            title="Delete note"
                            aria-label="Delete note"
                            onClick={() => openDeleteModal(note)}
                            disabled={Boolean(deletingId)}
                            className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-rose-200 bg-rose-50 text-rose-600 transition hover:bg-rose-100 disabled:opacity-60"
                          >
                            <FiTrash2 />
                          </button>
                        ) : null}
                      </div>
                      {downloadingId === note.id ? (
                        <p className="mt-1 text-right text-[11px] font-medium text-slate-500">
                          Downloading...
                        </p>
                      ) : null}
                      <AnimatePresence>
                        {downloadingId === note.id || state.phase === 'done' ? (
                          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="mt-2">
                            <p className="mb-1 text-[11px] font-medium text-slate-500">
                              {indeterminate ? 'Finalizing...' : `Download ${Math.round(progress)}%`}
                            </p>
                            <ModernProgress value={progress} indeterminate={indeterminate} />
                          </motion.div>
                        ) : null}
                      </AnimatePresence>
                    </div>
                  </div>

                  <Accordion
                    title="Note Details"
                    icon={<FiInfo />}
                    flush
                    className="w-full border-t border-slate-200 bg-slate-50"
                    contentClassName="bg-white"
                  >
                    <div className="grid gap-1 text-[11px] text-slate-600 sm:grid-cols-2">
                      <p className="sm:col-span-2">
                        <span className="font-semibold text-slate-700">Description:</span>{' '}
                        {note.description?.trim() || '-'}
                      </p>
                      <p className="inline-flex items-center gap-1.5"><FiFileText className="text-blue-500" /> {bytesToDisplay(note.file_size)}</p>
                      <p className="inline-flex items-center gap-1.5"><FiCalendar className="text-emerald-500" /> Created: {formatDateTime(note.created_at)}</p>
                      <p className="inline-flex items-center gap-1.5"><FiClock className="text-amber-500" /> Release: {formatDateTime(note.release_at)}</p>
                      <p className="inline-flex items-center gap-1.5"><FiClock className="text-rose-500" /> Expires: {formatDateTime(note.expire_at)}</p>
                    </div>
                  </Accordion>
                </motion.article>
              );
            })}
          </AnimatePresence>

          {!notes.length ? <p className="rounded-xl border border-slate-200 bg-white px-4 py-8 text-center text-sm text-slate-500">No notes found for these filters.</p> : null}
        </div>
      ) : null}

      <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-800 dark:bg-slate-900">
        <span className="text-slate-600">Page {pagination.page} of {pagination.total_pages}</span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={pagination.page <= 1}
            onClick={() => updateFilter('page', pagination.page - 1)}
            className="rounded border border-slate-300 px-3 py-1.5 disabled:opacity-50"
          >
            Prev
          </button>
          <button
            type="button"
            disabled={pagination.page >= pagination.total_pages}
            onClick={() => updateFilter('page', pagination.page + 1)}
            className="rounded border border-slate-300 px-3 py-1.5 disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>

      <AnimatePresence>
        {showUpload ? (
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.form
              onSubmit={handleUpload}
              initial={{ scale: 0.96, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.96, opacity: 0 }}
              className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl"
            >
              <div className="mb-4 flex items-center justify-between">
                <h3 className="text-xl font-bold text-slate-900">{editingNoteId ? 'Edit Note' : 'Upload Note'}</h3>
                <button type="button" onClick={closeUploadModal} className="rounded-lg border border-slate-300 p-2 text-slate-600">
                  <FiX />
                </button>
              </div>

              <div className="grid gap-3 md:grid-cols-2">
                <input required placeholder="Title" value={form.title} onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
                <div className="space-y-1">
                  {hasSubjectList ? (
                    <select value={form.subject_id} onChange={(event) => setForm((prev) => ({ ...prev, subject_id: event.target.value, chapter_id: '', topic_id: '' }))} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">
                      <option value="">Select subject (optional)</option>
                      {subjectOptions.map((subject) => (
                        <option key={subject.id} value={subject.id}>{subject.name}</option>
                      ))}
                    </select>
                  ) : null}
                  <input placeholder={hasSubjectList ? 'Or type subject manually (optional)' : 'Subject (optional)'} value={form.subject_name} onChange={(event) => setForm((prev) => ({ ...prev, subject_name: event.target.value }))} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
                </div>
                <div className="space-y-1">
                  {hasChapterList ? (
                    <select value={form.chapter_id} onChange={(event) => setForm((prev) => ({ ...prev, chapter_id: event.target.value, topic_id: '' }))} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">
                      <option value="">Select chapter (optional)</option>
                      {chapterOptions.map((chapter) => (
                        <option key={chapter.id} value={chapter.id}>{chapter.name}</option>
                      ))}
                    </select>
                  ) : null}
                  <input placeholder={hasChapterList ? 'Or type chapter manually (optional)' : 'Chapter (optional)'} value={form.chapter_name} onChange={(event) => setForm((prev) => ({ ...prev, chapter_name: event.target.value }))} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
                </div>
                <div className="space-y-1">
                  {hasTopicList ? (
                    <select value={form.topic_id} onChange={(event) => setForm((prev) => ({ ...prev, topic_id: event.target.value }))} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">
                      <option value="">Select topic (optional)</option>
                      {topicOptions.map((topic) => (
                        <option key={topic.id} value={topic.id}>{topic.name}</option>
                      ))}
                    </select>
                  ) : null}
                  <input placeholder={hasTopicList ? 'Or type topic manually (optional)' : 'Topic (optional)'} value={form.topic_name} onChange={(event) => setForm((prev) => ({ ...prev, topic_name: event.target.value }))} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
                </div>
                <textarea placeholder="Description" value={form.description} onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm md:col-span-2" rows={3} />
                <label className="space-y-1 text-xs text-slate-600">
                  <span>Release at</span>
                  <input type="datetime-local" value={form.release_at} onChange={(event) => setForm((prev) => ({ ...prev, release_at: event.target.value }))} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
                </label>
                <label className="space-y-1 text-xs text-slate-600">
                  <span>Expire at</span>
                  <input type="datetime-local" value={form.expire_at} onChange={(event) => setForm((prev) => ({ ...prev, expire_at: event.target.value }))} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
                </label>
              </div>

              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <div className="rounded-xl border border-slate-200 p-3">
                  <p className="mb-2 text-sm font-semibold text-slate-700">Batches</p>
                  <div className="max-h-36 space-y-1 overflow-y-auto">
                    {(metadata.batches || []).map((batch) => (
                      <label key={batch.id} className="flex items-center gap-2 text-sm text-slate-700">
                        <input type="checkbox" checked={form.batch_ids.includes(batch.id)} onChange={() => toggleBatch(batch.id)} />
                        {batch.name}
                      </label>
                    ))}
                  </div>
                </div>

                <div className="rounded-xl border border-slate-200 p-3">
                  <p className="mb-2 text-sm font-semibold text-slate-700">Tags</p>
                  <div className="max-h-24 space-y-1 overflow-y-auto">
                    {(metadata.tags || []).map((tag) => (
                      <label key={tag.id} className="flex items-center gap-2 text-sm text-slate-700">
                        <input type="checkbox" checked={form.tags.includes(tag.name)} onChange={() => toggleTag(tag.name)} />
                        {tag.name}
                      </label>
                    ))}
                  </div>
                  <input
                    placeholder="Extra tags (comma separated)"
                    value={form.custom_tags}
                    onChange={(event) => setForm((prev) => ({ ...prev, custom_tags: event.target.value }))}
                    className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                </div>
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-4">
                <label className="flex items-center gap-2 text-sm text-slate-700"><input type="checkbox" checked={form.visible_to_students} onChange={(event) => setForm((prev) => ({ ...prev, visible_to_students: event.target.checked }))} /> Visible to students</label>
                <label className="flex items-center gap-2 text-sm text-slate-700"><input type="checkbox" checked={form.visible_to_parents} onChange={(event) => setForm((prev) => ({ ...prev, visible_to_parents: event.target.checked }))} /> Visible to parents</label>
              </div>

              <div className="mt-4">
                {editingNoteId ? (
                  <p className="mb-2 text-xs text-slate-500">Choose a PDF only if you want to replace the existing file.</p>
                ) : null}
                <input type="file" accept="application/pdf,.pdf" onChange={(event) => setForm((prev) => ({ ...prev, file: event.target.files?.[0] || null }))} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
              </div>

              <AnimatePresence>
                {uploading || uploadState.phase === 'done' ? (
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="mt-4">
                    <div className="mb-1 flex items-center justify-between text-xs font-semibold text-slate-600">
                      <span>
                        {uploadState.phase === 'processing'
                          ? 'Processing on server...'
                          : uploadState.phase === 'done'
                            ? 'Upload complete'
                            : 'Uploading...'}
                      </span>
                      <span>{Math.round(uploadState.progress)}%</span>
                    </div>
                    <ModernProgress
                      value={uploadState.progress}
                      indeterminate={uploadState.phase === 'processing'}
                      tone={uploadState.phase === 'done' ? 'emerald' : 'blue'}
                    />
                  </motion.div>
                ) : null}
              </AnimatePresence>

              <div className="mt-5 flex items-center justify-end gap-2">
                <button type="button" onClick={closeUploadModal} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700">Cancel</button>
                <button type="submit" disabled={uploading} className="rounded-lg bg-[#2f7bf6] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">{uploading ? (editingNoteId ? 'Saving...' : 'Uploading...') : (editingNoteId ? 'Save Changes' : 'Upload Note')}</button>
              </div>
            </motion.form>
          </motion.div>
        ) : null}
      </AnimatePresence>
      <ConfirmModal
        open={Boolean(deleteTarget)}
        title="Delete Note"
        message={`Delete "${deleteTarget?.title || 'this note'}"? This removes file(s) from Google Drive first, then deletes the note record.`}
        confirmText="Delete"
        loading={Boolean(deletingId)}
        onClose={closeDeleteModal}
        onConfirm={confirmDelete}
      />
      <Toast
        open={toast.open}
        tone={toast.tone}
        message={toast.message}
        duration={5000}
        onClose={() => setToast((prev) => ({ ...prev, open: false }))}
      />
    </section>
  );
}

export default Notes;
