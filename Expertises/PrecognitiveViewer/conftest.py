"""pytest 設定 — PrecognitiveViewer を package として import 可能にする。

`PrecognitiveViewer.Report.domain` のような絶対 import で名前空間衝突を回避する
（sandbox 配下に同名 `domain` パッケージが存在するため）。
"""
from __future__ import annotations

import sys
from pathlib import Path

# Expertises/ を sys.path に追加して PrecognitiveViewer package を import 可能にする
EXPERTISES_DIR = Path(__file__).parent.parent
if str(EXPERTISES_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERTISES_DIR))

# Seimei / I-Ching は固有名スクリプト方式（コピー元と完全一致を保つため __init__.py を追加しない）
ROOT = Path(__file__).parent
for subdir in ["Seimei", "I-Ching"]:
    path = ROOT / subdir
    if path.exists() and str(path) not in sys.path:
        sys.path.insert(0, str(path))
