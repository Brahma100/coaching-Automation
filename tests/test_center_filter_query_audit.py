from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]

TARGET_FILES = [
    Path('app/services/dashboard_today_service.py'),
    Path('app/services/admin_ops_dashboard_service.py'),
    Path('app/services/student_digest_service.py'),
    Path('app/services/student_risk_service.py'),
    Path('app/services/inbox_automation.py'),
    Path('app/services/notes_service.py'),
    Path('app/services/time_capacity_service.py'),
    Path('app/services/teacher_calendar_service.py'),
    Path('app/domain/services/notes_service.py'),
]

MISSING_CENTER_FALLBACK = re.compile(r'center_id\s*==.*if\s+.*else\s+True')


RISK_MODELS = ('PendingAction', 'ClassSession', 'Batch', 'Student', 'StudentRiskProfile')


def test_no_conditional_center_filter_shortcuts() -> None:
    offenders: list[str] = []
    for rel in TARGET_FILES:
        text = (ROOT / rel).read_text(encoding='utf-8')
        if MISSING_CENTER_FALLBACK.search(text):
            offenders.append(str(rel))
    assert not offenders, f'Conditional center filters found: {offenders}'


def test_risky_queries_have_center_filter_or_warning_exception() -> None:
    offenders: list[str] = []
    for rel in TARGET_FILES:
        lines = (ROOT / rel).read_text(encoding='utf-8').splitlines()
        for idx, line in enumerate(lines):
            if 'db.query(' not in line:
                continue
            if not any(re.search(rf'\b{model}\b', line) for model in RISK_MODELS):
                continue
            window = '\n'.join(lines[idx : min(len(lines), idx + 25)])
            if 'center_id' in window or '_warn_missing_center_filter' in window:
                continue
            offenders.append(f'{rel}:{idx + 1}')
    assert not offenders, 'Risky query blocks without center filter:\n' + '\n'.join(offenders)
