"""TripleDivinationUseCase — 三占術結果を DivinationTriplet に統合する。

姓名判断 (dict)・周易 (dict)・タロット (TarotReading) の三結果を受け取り、
鑑定書ドメインで扱える単一の DivinationTriplet に正規化する。
"""
from __future__ import annotations

from typing import Any

from PrecognitiveViewer.Report.domain import (
    DivinationTriplet,
    TarotReading,
)


class TripleDivinationUseCase:
    """三占術統合 UseCase。各結果を DivinationTriplet にロスなく格納する。"""

    def synthesize(
        self,
        seimei_summary: dict,
        iching_summary: dict,
        tarot_reading: TarotReading,
    ) -> DivinationTriplet:
        """三占術結果を統合する。

        tarot_reading は TarotReading 型なので、DivinationTriplet 形式に合わせて
        dict 化する（drawn_cards はカード情報の dict リストへ展開）。
        """
        tarot_summary = self._tarot_to_dict(tarot_reading)
        return DivinationTriplet(
            seimei_summary=seimei_summary,
            iching_summary=iching_summary,
            tarot_summary=tarot_summary,
        )

    @staticmethod
    def _tarot_to_dict(reading: TarotReading) -> dict[str, Any]:
        return {
            "spread_name": reading.spread.name,
            "spread_focus": reading.spread.focus,
            "positions": list(reading.spread.positions),
            "question": reading.question,
            "context": reading.context,
            "timestamp": reading.timestamp.isoformat(),
            "drawn_cards": [
                {
                    "position": d.position,
                    "position_name": reading.spread.positions[d.position],
                    "id": d.card.id,
                    "name": d.card.name,
                    "arcana": d.card.arcana,
                    "suit": d.card.suit,
                    "number": d.card.number,
                    "is_reversed": d.is_reversed,
                    "keywords": list(d.card.keywords),
                    "meaning": d.card.reversed_meaning if d.is_reversed else d.card.upright_meaning,
                }
                for d in reading.drawn_cards
            ],
        }
