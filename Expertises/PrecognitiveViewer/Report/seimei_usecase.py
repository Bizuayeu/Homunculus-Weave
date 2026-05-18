"""SeimeiAssessmentUseCase — 姓名判断（七格剖象法）の UseCase 層。

コピーされた `Seimei/fortune_teller_assessment.py` の `FortuneTellerAssessment`
クラスを内部使用し、結果 dict を返す。テスト容易性のため依存性注入可能。
"""
from __future__ import annotations

from typing import Optional, Sequence

# conftest.py で sys.path に Seimei/ が追加されている
from fortune_teller_assessment import FortuneTellerAssessment


class SeimeiAssessmentUseCase:
    """姓名判断 UseCase。既存エンジンをラップし、UseCase 層 API を提供する。"""

    def __init__(self, assessor: Optional[FortuneTellerAssessment] = None) -> None:
        self._assessor = assessor or FortuneTellerAssessment()

    def assess(
        self,
        surname: str,
        given_name: str,
        surname_strokes: Sequence[int],
        given_strokes: Sequence[int],
    ) -> dict:
        """姓名判断を実行し、結果 dict を返す。

        Returns:
            既存 `FortuneTellerAssessment.assess()` の出力 dict。
            主要キー: 七格、星導分布、人材4類型、姓、名
        """
        return self._assessor.assess(
            surname,
            given_name,
            list(surname_strokes),
            list(given_strokes),
        )
