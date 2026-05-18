"""TarotReadingUseCase — タロット・リーディングの UseCase 層。

`Tarot/tarot_engine.py` の Repository + Shuffler を組み合わせて TarotReading を生成する。
占的なしでも引ける運用（人物リーディング等）を前提に、第三者代理引きに対応する。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from PrecognitiveViewer.Report.domain import (
    DrawnCard,
    SpreadDefinition,
    TarotCard,
    TarotReading,
)
from PrecognitiveViewer.Tarot.tarot_engine import (
    DeterministicShuffler,
    SpreadRepository,
    TarotCardRepository,
)


class TarotReadingUseCase:
    """タロット・リーディング UseCase。スプレッドを引いて TarotReading を返す。"""

    def __init__(
        self,
        card_repo: Optional[TarotCardRepository] = None,
        spread_repo: Optional[SpreadRepository] = None,
        shuffler: Optional[DeterministicShuffler] = None,
    ) -> None:
        self._card_repo = card_repo or TarotCardRepository()
        self._spread_repo = spread_repo or SpreadRepository()
        self._shuffler = shuffler or DeterministicShuffler()

    def read(
        self,
        question: str,
        context: str,
        spread_name: str,
        timestamp: Optional[datetime] = None,
    ) -> TarotReading:
        """指定のスプレッドでカードを引き、TarotReading を返す。

        Args:
            question: 占的（空文字列可、人物リーディング等の第三者代理引き対応）
            context: 状況・対象（被鑑定者情報など）
            spread_name: スプレッド名（single_card / past_present_future / celtic_cross / decision_making / person_reading）
            timestamp: 占機。None の場合は現在時刻。

        Raises:
            ValueError: 未知のスプレッド名
        """
        ts = timestamp or datetime.now()

        spread = self._find_spread(spread_name)
        cards = self._card_repo.load_all()
        indices = self._shuffler.shuffle(
            question=question,
            context=context,
            timestamp=ts.timestamp(),
            n=spread.card_count,
        )

        drawn = tuple(
            DrawnCard(
                card=cards[idx],
                is_reversed=self._is_reversed(idx, ts),
                position=pos,
            )
            for pos, idx in enumerate(indices)
        )

        return TarotReading(
            spread=spread,
            drawn_cards=drawn,
            question=question,
            context=context,
            timestamp=ts,
        )

    def _find_spread(self, name: str) -> SpreadDefinition:
        for s in self._spread_repo.load_all():
            if s.name == name:
                return s
        raise ValueError(f"未知のスプレッド名: {name}")

    @staticmethod
    def _is_reversed(card_idx: int, ts: datetime) -> bool:
        """正逆の決定論的判定。占機の秒数とカードインデックスから疑似的に決める。

        実カードのシャッフル時に裏返しが混入する物理過程を、決定論的に模倣する。
        """
        return ((card_idx + int(ts.timestamp())) % 2) == 1
