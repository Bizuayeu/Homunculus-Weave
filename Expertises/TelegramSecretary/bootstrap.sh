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

# --- D: deadline 駆動ロングポーリング運用変数 (Stage 10.3 / D 改修) ---
# 「2時間枠 (deadline)」と「ポーリング回数 (メッセージ頻度で可変)」を分離する。
# 停止主軸は TS_SESSION_DEADLINE_EPOCH (時刻)。回数は数えない (早期 exit→返信→再起動)。
# テスト時は env 上書きで短縮可能（既存 session_id と同型の :- 冪等パターン）。
export TS_SESSION_DURATION_SEC="${TS_SESSION_DURATION_SEC:-7200}"    # session 総枠 (2h)、deadline 計算の元
export TS_SESSION_DEADLINE_EPOCH="${TS_SESSION_DEADLINE_EPOCH:-$(( $(date +%s) + TS_SESSION_DURATION_SEC ))}"  # 停止主軸: この epoch 秒を過ぎたら /goal 停止
export TS_POLL_SET_SEC="${TS_POLL_SET_SEC:-580}"                     # メッセージ無し時の 1 窓上限 (bash timeout より短く)
export TS_POLL_BASH_TIMEOUT_MS="${TS_POLL_BASH_TIMEOUT_MS:-600000}"  # ポーリング call の bash tool timeout (=BASH_MAX_TIMEOUT_MS)
export TS_MAX_TURNS="${TS_MAX_TURNS:-300}"                           # /goal turn 安全弁 (deadline 異常時の暴走防止、2h/30s≈240+バッファ)
_ts_log "deadline-driven poll: deadline=$TS_SESSION_DEADLINE_EPOCH (now+${TS_SESSION_DURATION_SEC}s), window<=${TS_POLL_SET_SEC}s, max_turns=${TS_MAX_TURNS}, bash timeout ${TS_POLL_BASH_TIMEOUT_MS}ms"

# --- 設定検証 (env 欠損なら exit 2 で fail-fast) ---
(cd "$_ts_script_dir" && python scripts/main.py validate-config) || _ts_die "validate-config failed"

_ts_log "ready"
