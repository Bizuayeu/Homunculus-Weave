"""IChingDivinationUseCase — 周易占断（デジタル心易）の UseCase 層。

コピーされた `I-Ching/iching_divination.py` の `IChingDivination`
クラスを内部使用し、結果 dict を返す。テスト容易性のため依存性注入可能。
"""
from __future__ import annotations

from typing import Optional

# conftest.py で sys.path に I-Ching/ が追加されている
from iching_divination import IChingDivination


class IChingDivinationUseCase:
    """周易占断 UseCase。既存エンジンをラップし、UseCase 層 API を提供する。"""

    def __init__(self, divination: Optional[IChingDivination] = None) -> None:
        self._divination = divination or IChingDivination()

    def divine(
        self,
        question: str,
        context: str,
        timestamp: Optional[float] = None,
    ) -> dict:
        """易占断を実行し、結果 dict を返す。

        Args:
            question: 占的（明確化された問い）
            context: 状況整理（背景情報）
            timestamp: 占機（時刻 Unix epoch）。None の場合は現在時刻。

        Returns:
            既存 `IChingDivination.divine()` の出力 dict。
            主要キー: 占機、占的、状況整理、得卦、得爻
        """
        return self._divination.divine(question, context, timestamp)
