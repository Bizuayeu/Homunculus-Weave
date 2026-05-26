#!/bin/bash
# TelegramSecretary bootstrap — idempotent setup for Cloud Routine / manual runs.
#
# Use:
#   source Expertises/TelegramSecretary/bootstrap.sh
#     → exports TELEGRAM_SECRETARY_SESSION_ID into the parent shell so subsequent
#       lease/watch/send-reply commands share the same owner (運用律 B 案)
#   bash   Expertises/TelegramSecretary/bootstrap.sh
#     → installs only, env exports do not persist
#
# Single source of truth for runtime deps: Expertises/TelegramSecretary/pyproject.toml
# NewsCaster bootstrap pattern と同型 (source/exec デュアル対応).

set -u

# Detect source vs exec so we can use `return` when sourced, `exit` when executed.
_ts_sourced=0
if [ "${BASH_SOURCE[0]:-}" != "${0:-}" ]; then
    _ts_sourced=1
fi

_ts_die() {
    echo "[telegram-secretary-bootstrap] FAIL: $*" >&2
    if [ "$_ts_sourced" = "1" ]; then
        return 1
    else
        exit 1
    fi
}

_ts_log() { echo "[telegram-secretary-bootstrap] $*"; }

# Resolve script dir robustly whether sourced or executed.
_ts_script_path="${BASH_SOURCE[0]:-$0}"
_ts_script_dir="$(cd "$(dirname "$_ts_script_path")" && pwd)"

# --- 依存導入 ---
if ! python -c "import httpx" 2>/dev/null; then
    _ts_log "installing httpx..."
    python -m pip install --quiet httpx || _ts_die "httpx install failed"
fi
python -c "import httpx" >/dev/null || _ts_die "httpx import failed after install"

# --- Session ID 自動 export (運用律 B 案) ---
# lease acquire / watch / send-reply / lease renew が同じ owner を共有するように、
# bootstrap で session_id を session 全体に固定する。既に設定されていれば尊重 (冪等)。
export TELEGRAM_SECRETARY_SESSION_ID="${TELEGRAM_SECRETARY_SESSION_ID:-session-$(python -c 'import uuid; print(uuid.uuid4().hex[:8])')}"
_ts_log "session_id=$TELEGRAM_SECRETARY_SESSION_ID"

# --- 設定検証 (env 欠損なら exit 2 で fail-fast) ---
(cd "$_ts_script_dir" && python scripts/main.py validate-config) || _ts_die "validate-config failed"

_ts_log "ready"
