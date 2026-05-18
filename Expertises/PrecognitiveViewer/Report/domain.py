"""PrecognitiveViewer Domain — タロット値オブジェクト + 三占術統合 + 鑑定書ドメイン。

Clean Architecture の最内層。標準ライブラリのみに依存し、frozen dataclass で不変性を確保する。
日本語フィールド値は dataclass 標準の __repr__ で UTF-8 のまま可読に保持される。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional

ArcanaType = Literal["major", "minor"]
SuitType = Literal["wands", "cups", "swords", "pentacles"]


@dataclass(frozen=True)
class TarotCard:
    """タロットカードの値オブジェクト。

    大アルカナ（22 枚、番号 0-21、スートなし）と小アルカナ（56 枚、4 スート × 番号 1-14）
    の双方を統一表現する。`__post_init__` で arcana/number/suit の整合性を assert する。
    """

    id: str
    name: str
    arcana: ArcanaType
    number: int
    keywords: tuple[str, ...]
    upright_meaning: str
    reversed_meaning: str
    suit: Optional[SuitType] = None
    element: Optional[str] = None
    astrology: Optional[str] = None

    def __post_init__(self) -> None:
        if self.arcana == "major":
            if not 0 <= self.number <= 21:
                raise ValueError(
                    f"大アルカナの番号は 0-21 の範囲、got {self.number}"
                )
            if self.suit is not None:
                raise ValueError("大アルカナにスート指定は不要")
        elif self.arcana == "minor":
            if not 1 <= self.number <= 14:
                raise ValueError(
                    f"小アルカナの番号は 1-14 の範囲、got {self.number}"
                )
            if self.suit is None:
                raise ValueError("小アルカナにはスート指定が必須")


@dataclass(frozen=True)
class SpreadDefinition:
    """スプレッド定義。positions の各要素が「過去/現在/未来」等の意味を表す。"""

    name: str
    positions: tuple[str, ...]
    focus: str

    @property
    def card_count(self) -> int:
        return len(self.positions)


@dataclass(frozen=True)
class DrawnCard:
    """引かれたカード。スプレッド内での位置（インデックス）と正逆を保持する。"""

    card: TarotCard
    is_reversed: bool
    position: int


@dataclass(frozen=True)
class TarotReading:
    """一回のタロット・リーディング結果。

    `TarotReadingUseCase.read()` の出力。スプレッドと引かれたカード群、
    占機・占的・状況を保持する（再現性検証可能）。
    """

    spread: SpreadDefinition
    drawn_cards: tuple[DrawnCard, ...]
    question: str
    context: str
    timestamp: datetime


@dataclass(frozen=True)
class DivinationTriplet:
    """三占術（姓名・易・タロット）の統合結果。

    各 summary は占術固有の構造を持つため dict として保持する。
    フォーマル鑑定書を構築する `ReadingReportComposerUseCase` の入力となる。
    """

    seimei_summary: dict
    iching_summary: dict
    tarot_summary: dict


@dataclass(frozen=True)
class Recipient:
    """被鑑定者情報。鑑定書の宛先となる。"""

    full_name: str
    reading: str
    context: Optional[str] = None


@dataclass(frozen=True)
class ReadingReport:
    """三位占術フォーマル鑑定書のドメイン表現。

    各 section は LLM 解釈レイヤーによって埋められた Markdown 本文を保持する。
    Presenter がこれを最終的なファイル（ReadingReport_yyyymmdd_hhmmss.md）に整形する。
    """

    recipient: Recipient
    timestamp: datetime
    seimei_section: str
    iching_section: str
    tarot_section: str
    integrated_insight: str
    closing_message: str
