from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'app/domain/jobs/runtime.py'
JOB_LOCK = ROOT / 'app/domain/jobs/job_lock.py'
JOBS_DIR = ROOT / 'app/domain/jobs'

RISK_MODELS = (
    'AuthUser',
    'Batch',
    'ClassSession',
    'Student',
    'PendingAction',
    'Center',
)


def test_runtime_iterates_centers_explicitly() -> None:
    text = RUNTIME.read_text(encoding='utf-8')
    assert 'db.query(Center.id)' in text
    assert 'for center_id in center_ids' in text


def test_job_lock_is_scoped_by_center() -> None:
    text = JOB_LOCK.read_text(encoding='utf-8')
    assert "f'{job_label}:{int(center_id or 0)}'" in text


def test_job_queries_include_center_filter() -> None:
    offenders: list[str] = []
    for path in sorted(JOBS_DIR.glob('*.py')):
        if path.name in {'__init__.py', 'runtime.py', 'job_lock.py'}:
            continue
        lines = path.read_text(encoding='utf-8').splitlines()
        for idx, line in enumerate(lines):
            if 'db.query(' not in line:
                continue
            if not any(re.search(rf'\b{model}\b', line) for model in RISK_MODELS):
                continue
            window = '\n'.join(lines[idx : min(len(lines), idx + 22)])
            if 'center_id' in window:
                continue
            offenders.append(f'{path.relative_to(ROOT)}:{idx + 1}')
    assert not offenders, 'Job query missing center filter:\n' + '\n'.join(offenders)
