from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"

PATTERNS = (
    r"\bdatetime\.now\(",
    r"\bdatetime\.utcnow\(",
    r"\bdate\.today\(",
    r"\bdatetime\.today\(",
)
COMPILED = [re.compile(pattern) for pattern in PATTERNS]


def _is_excluded(path: Path) -> bool:
    path_str = path.as_posix()
    if path_str.endswith("app/core/time_provider.py"):
        return True
    if "/migrations/" in path_str or "/alembic/" in path_str:
        return True
    if "/tests/" in path_str:
        return True
    return False


def test_no_direct_datetime_usage_in_app() -> None:
    violations: list[tuple[str, int, str]] = []
    for file_path in APP_DIR.rglob("*.py"):
        if _is_excluded(file_path):
            continue
        text = file_path.read_text(encoding="utf-8")
        for idx, line in enumerate(text.splitlines(), start=1):
            for regex in COMPILED:
                if regex.search(line):
                    violations.append((str(file_path.relative_to(ROOT)), idx, line.strip()))

    assert not violations, "Direct datetime usage found:\n" + "\n".join(
        f"{path}:{line_no}: {line}" for path, line_no, line in violations
    )
