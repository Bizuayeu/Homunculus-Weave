"""PrecognitiveViewer package — 三位占術によるフォーマル鑑定書スキル。

Bootstrap：package が import された時点で、Seimei/ と I-Ching/ ディレクトリを
sys.path に追加する。これにより、コピーされた既存スクリプト（固有名スクリプト方式）
`fortune_teller_assessment` `iching_divination` を、通常の Python 実行・pytest 実行
どちらの経路でも import 可能にする。

冪等：既に path に存在する場合は追加しない（多重 import 時の安全確保）。
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).parent

for _subdir in ["Seimei", "I-Ching"]:
    _path = _ROOT / _subdir
    if _path.exists():
        _path_str = str(_path)
        if _path_str not in sys.path:
            sys.path.insert(0, _path_str)
