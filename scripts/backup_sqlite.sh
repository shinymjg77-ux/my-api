#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/srv/my-api}"
DB_PATH="${DB_PATH:-$APP_ROOT/data/app.db}"
BACKUP_DIR="${BACKUP_DIR:-$APP_ROOT/backups/sqlite}"
KEEP_DAYS="${KEEP_DAYS:-14}"
PYTHON_BIN="${PYTHON_BIN:-$APP_ROOT/.venv/bin/python}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

alert_failure() {
  "$SCRIPT_DIR/send_alert.sh" "SQLite backup failed" "host=$(hostname) db=$DB_PATH" || true
}

trap alert_failure ERR

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
tmp_backup="$BACKUP_DIR/app-$timestamp.sqlite3"
final_backup="$tmp_backup.gz"

mkdir -p "$BACKUP_DIR"

if [[ ! -f "$DB_PATH" ]]; then
  echo "[backup] database file not found: $DB_PATH" >&2
  exit 1
fi

"$PYTHON_BIN" - "$DB_PATH" "$tmp_backup" <<'PY'
import sqlite3
import sys

source_path = sys.argv[1]
backup_path = sys.argv[2]

source = sqlite3.connect(source_path)
target = sqlite3.connect(backup_path)
try:
    source.backup(target)
finally:
    target.close()
    source.close()
PY

gzip -f "$tmp_backup"
find "$BACKUP_DIR" -type f -name '*.gz' -mtime +"$KEEP_DAYS" -delete
"$SCRIPT_DIR/upload_backup.sh" "$final_backup"

echo "[backup] created $final_backup"
