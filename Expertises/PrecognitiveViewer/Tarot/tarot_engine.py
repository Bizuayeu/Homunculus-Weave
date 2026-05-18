"""Tarot Repository + Deterministic Shuffler。

I-Ching と同じく BASE64+SHA256 シードによる Fisher-Yates シャッフルで再現性を確保する。
データは tarot_cards.json / tarot_spreads.json から読み込む。
出典は tarot-mcp (MIT License、abdul-hamid-achik/tarot-mcp)。詳細は LICENSE.md 参照。
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Optional

# 同じディレクトリの domain（Report/domain.py）を参照する
# conftest.py で PrecognitiveViewer package を sys.path に通している
from PrecognitiveViewer.Report.domain import (
    SpreadDefinition,
    TarotCard,
)

DATA_DIR = Path(__file__).parent


class TarotCardRepository:
    """tarot_cards.json から 78 枚の TarotCard をロードする"""

    def __init__(self, json_path: Optional[Path] = None) -> None:
        self._json_path = json_path or (DATA_DIR / "tarot_cards.json")
        with self._json_path.open("r", encoding="utf-8") as f:
            self._raw = json.load(f)

    def load_all(self) -> list[TarotCard]:
        return [self._to_card(c) for c in self._raw["cards"]]

    @staticmethod
    def _to_card(d: dict) -> TarotCard:
        return TarotCard(
            id=d["id"],
            name=d["name"],
            arcana=d["arcana"],
            number=d["number"],
            keywords=tuple(d["keywords"]),
            upright_meaning=d["upright_meaning"],
            reversed_meaning=d["reversed_meaning"],
            suit=d.get("suit"),
            element=d.get("element"),
            astrology=d.get("astrology"),
        )


class SpreadRepository:
    """tarot_spreads.json からスプレッド定義をロードする"""

    def __init__(self, json_path: Optional[Path] = None) -> None:
        self._json_path = json_path or (DATA_DIR / "tarot_spreads.json")
        with self._json_path.open("r", encoding="utf-8") as f:
            self._raw = json.load(f)

    def load_all(self) -> list[SpreadDefinition]:
        return [self._to_spread(s) for s in self._raw["spreads"]]

    @staticmethod
    def _to_spread(d: dict) -> SpreadDefinition:
        return SpreadDefinition(
            name=d["name"],
            positions=tuple(d["positions"]),
            focus=d["focus"],
        )


class DeterministicShuffler:
    """占的 + 状況 + 占機（timestamp）から決定論的に 0-77 の順列を生成する。

    I-Ching と同じ思想：天地人三才（占的・状況・時刻）を BASE64+SHA256 で混和し、
    再現可能な乱数列を得る。同じ入力には必ず同じ結果を返す（占機の真正性確保）。
    """

    DECK_SIZE = 78

    def shuffle(
        self,
        question: str,
        context: str,
        timestamp: float,
        n: int,
    ) -> list[int]:
        """n 枚分の引き札のインデックス（0-77、重複なし）を返す"""
        if not 1 <= n <= self.DECK_SIZE:
            raise ValueError(f"引き枚数は 1-{self.DECK_SIZE}、got {n}")

        seed_bytes = self._make_seed(question, context, timestamp)
        return self._fisher_yates(seed_bytes, n)

    @staticmethod
    def _make_seed(question: str, context: str, timestamp: float) -> bytes:
        """占的・状況・占機を BASE64+SHA256 で混和したシードを生成"""
        ts_str = f"{timestamp:.6f}"
        payload = "|".join([
            base64.b64encode(question.encode("utf-8")).decode("ascii"),
            base64.b64encode(context.encode("utf-8")).decode("ascii"),
            base64.b64encode(ts_str.encode("utf-8")).decode("ascii"),
        ])
        return hashlib.sha256(payload.encode("ascii")).digest()

    def _fisher_yates(self, seed: bytes, n: int) -> list[int]:
        """シードから決定論的に Fisher-Yates シャッフルし、先頭 n 個を返す"""
        deck = list(range(self.DECK_SIZE))
        # シードを再ハッシュしてバイト列を拡張（必要なバイト数を確保）
        stream = bytearray()
        block = seed
        while len(stream) < self.DECK_SIZE * 4:
            stream.extend(block)
            block = hashlib.sha256(block).digest()

        # Fisher-Yates：末尾から、ストリームから 4 バイト読んで index 決定
        for i in range(self.DECK_SIZE - 1, 0, -1):
            offset = (self.DECK_SIZE - 1 - i) * 4
            r = int.from_bytes(stream[offset:offset + 4], "big")
            j = r % (i + 1)
            deck[i], deck[j] = deck[j], deck[i]

        return deck[:n]
