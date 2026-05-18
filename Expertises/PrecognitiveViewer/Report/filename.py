"""ReportFilenameGenerator — フォーマル鑑定書のファイル名生成。

`ReadingReport_yyyymmdd_hhmmss.md` 形式。被鑑定者名はファイル名に含めず
タイムスタンプベースでユニーク性を確保（プライバシー配慮）。
"""
from __future__ import annotations

from datetime import datetime


class ReportFilenameGenerator:
    """鑑定書ファイル名の生成器"""

    @staticmethod
    def generate(timestamp: datetime) -> str:
        """ReadingReport_yyyymmdd_hhmmss.md 形式のファイル名を返す"""
        return f"ReadingReport_{timestamp.strftime('%Y%m%d_%H%M%S')}.md"
