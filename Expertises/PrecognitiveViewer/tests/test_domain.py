"""Stage 1 Red Tests — Report/domain.py の値オブジェクトを検証する。

代表ケース 3 件（計画書 Stage 1 の Success Criteria より）:
- test_tarot_card_immutability
- test_drawn_card_position_in_spread
- test_reading_report_required_fields

加えて、`__post_init__` の不変条件・日本語 repr の可読性も補強的に検証する。
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from PrecognitiveViewer.Report.domain import (
    DivinationTriplet,
    DrawnCard,
    ReadingReport,
    Recipient,
    SpreadDefinition,
    TarotCard,
)


# ----------------------------------------------------------------------------
# 計画書 Success Criteria 3 件
# ----------------------------------------------------------------------------


def test_tarot_card_immutability() -> None:
    """TarotCard は frozen で、属性書換時に FrozenInstanceError が発生する"""
    card = TarotCard(
        id="major-00",
        name="愚者",
        arcana="major",
        number=0,
        keywords=("始まり", "純粋", "無垢"),
        upright_meaning="新たな旅立ち、可能性、自由",
        reversed_meaning="軽率さ、無謀、向こう見ず",
    )
    with pytest.raises(FrozenInstanceError):
        card.name = "魔術師"  # type: ignore[misc]


def test_drawn_card_position_in_spread() -> None:
    """DrawnCard.position が SpreadDefinition.positions のインデックスと整合する"""
    spread = SpreadDefinition(
        name="三枚引き",
        positions=("過去", "現在", "未来"),
        focus="時間軸の流れを観る",
    )
    card = TarotCard(
        id="major-00",
        name="愚者",
        arcana="major",
        number=0,
        keywords=("始まり",),
        upright_meaning="新たな旅立ち",
        reversed_meaning="軽率さ",
    )
    drawn = DrawnCard(card=card, is_reversed=True, position=0)
    assert spread.positions[drawn.position] == "過去"


def test_reading_report_required_fields() -> None:
    """ReadingReport の必須フィールドが未指定だと TypeError が発生する"""
    recipient = Recipient(full_name="山田太郎", reading="やまだたろう")
    # seimei_section 以降を欠いて生成 → TypeError
    with pytest.raises(TypeError):
        ReadingReport(recipient=recipient, timestamp=datetime.now())  # type: ignore[call-arg]


# ----------------------------------------------------------------------------
# 補強テスト：不変条件と日本語可読性
# ----------------------------------------------------------------------------


def test_major_arcana_number_range_rejects_22() -> None:
    """大アルカナの番号は 0-21、22 で ValueError"""
    with pytest.raises(ValueError, match="大アルカナ"):
        TarotCard(
            id="major-22",
            name="不正",
            arcana="major",
            number=22,
            keywords=(),
            upright_meaning="",
            reversed_meaning="",
        )


def test_major_arcana_rejects_suit() -> None:
    """大アルカナにスート指定があると ValueError"""
    with pytest.raises(ValueError, match="大アルカナ"):
        TarotCard(
            id="major-00",
            name="愚者",
            arcana="major",
            number=0,
            keywords=(),
            upright_meaning="",
            reversed_meaning="",
            suit="cups",
        )


def test_minor_arcana_requires_suit() -> None:
    """小アルカナはスート必須、なしで ValueError"""
    with pytest.raises(ValueError, match="小アルカナ"):
        TarotCard(
            id="minor-cups-01",
            name="カップのエース",
            arcana="minor",
            number=1,
            keywords=(),
            upright_meaning="",
            reversed_meaning="",
            suit=None,
        )


def test_minor_arcana_number_range_rejects_15() -> None:
    """小アルカナの番号は 1-14、15 で ValueError"""
    with pytest.raises(ValueError, match="小アルカナ"):
        TarotCard(
            id="minor-cups-15",
            name="不正",
            arcana="minor",
            number=15,
            keywords=(),
            upright_meaning="",
            reversed_meaning="",
            suit="cups",
        )


def test_tarot_card_repr_contains_japanese() -> None:
    """TarotCard の repr が日本語フィールド値を可読に保持する"""
    card = TarotCard(
        id="major-00",
        name="愚者",
        arcana="major",
        number=0,
        keywords=("始まり",),
        upright_meaning="新たな旅立ち",
        reversed_meaning="軽率さ",
    )
    rep = repr(card)
    assert "愚者" in rep
    assert "始まり" in rep


def test_spread_definition_card_count() -> None:
    """SpreadDefinition.card_count は positions の長さと一致"""
    spread = SpreadDefinition(
        name="ケルト十字",
        positions=tuple(f"位置{i+1}" for i in range(10)),
        focus="包括的分析",
    )
    assert spread.card_count == 10


def test_divination_triplet_holds_three_summaries() -> None:
    """DivinationTriplet が三占術の summary を保持する"""
    triplet = DivinationTriplet(
        seimei_summary={"主導星": "月", "人材4類型": "秀才"},
        iching_summary={"卦": "乾為天", "爻": "九五"},
        tarot_summary={"主要札": "愚者"},
    )
    assert triplet.seimei_summary["主導星"] == "月"
    assert triplet.iching_summary["卦"] == "乾為天"
    assert triplet.tarot_summary["主要札"] == "愚者"


def test_reading_report_full_construction() -> None:
    """ReadingReport の全フィールド指定で生成成功"""
    recipient = Recipient(
        full_name="山田太郎",
        reading="やまだたろう",
        context="今年の事業展望を観たい",
    )
    report = ReadingReport(
        recipient=recipient,
        timestamp=datetime(2026, 5, 18, 14, 30, 15),
        seimei_section="第一章テキスト",
        iching_section="第二章テキスト",
        tarot_section="第三章テキスト",
        integrated_insight="第四章テキスト",
        closing_message="結びの言葉",
    )
    assert report.recipient.full_name == "山田太郎"
    assert report.timestamp.year == 2026
