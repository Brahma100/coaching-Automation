#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/coaching_automation"
DB_PATH="${APP_DIR}/coaching.db"
BACKUP_DIR="/var/backups/coaching_automation"
RETENTION_DAYS=14

mkdir -p "${BACKUP_DIR}"
timestamp="$(date -u +'%Y%m%d_%H%M%S')"
backup_file="${BACKUP_DIR}/coaching_${timestamp}.db"

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "sqlite3 not found in PATH" >&2
  exit 1
fi

sqlite3 "${DB_PATH}" ".backup '${backup_file}'"

find "${BACKUP_DIR}" -type f -name "coaching_*.db" -mtime +"${RETENTION_DAYS}" -print -delete
