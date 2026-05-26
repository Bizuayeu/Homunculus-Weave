#!/usr/bin/env bash
# TelegramSecretary bootstrap: 依存導入と疎通確認の最小セット。
# Cloud Routine 起動時の冪等な準備手順。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# httpx を確実に入れる（pyproject.toml と整合）
if ! python -c "import httpx" 2>/dev/null; then
    python -m pip install --quiet httpx
fi

# 設定検証（env 揃ってない場合は exit 2 で fail-fast）
python scripts/main.py validate-config

echo "[telegram-secretary-bootstrap] ready"
