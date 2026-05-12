#!/usr/bin/env bash
# Cloud Routine 環境での依存解決スクリプト
# BlueberrySprite と同じ Python 環境を想定（pip install で依存導入）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[bootstrap] installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet \
    "google-api-python-client>=2.0" \
    "google-auth>=2.0" \
    "google-auth-oauthlib>=1.0"

echo "[bootstrap] done"
