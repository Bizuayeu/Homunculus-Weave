"""Stage 3 Tests — 三占術 UseCase + TripleDivinationUseCase の検証。

計画書 Stage 3 Success Criteria より:
- test_seimei_usecase_returns_summary_with_personnel_type
- test_iching_usecase_returns_hexagram_and_yao
- test_tarot_celtic_cross_returns_10_cards
- test_triple_divination_synthesis_preserves_all_three
"""
from __future__ import annotations

from datetime import datetime

import pytest

from PrecognitiveViewer.Report.domain import (
    DivinationTriplet,
    DrawnCard,
    SpreadDefinition,
    TarotCard,
    TarotReading,
)
from PrecognitiveViewer.Report.seimei_usecase import (
    SeimeiAssessmentUseCase,
)
from PrecognitiveViewer.Report.iching_usecase import (
    IChingDivinationUseCase,
)
from PrecognitiveViewer.Report.tarot_usecase import (
    TarotReadingUseCase,
)
from PrecognitiveViewer.Report.triple_divination import (
    TripleDivinationUseCase,
)


# ----------------------------------------------------------------------------
# Seimei UseCase
# ----------------------------------------------------------------------------


def test_seimei_usecase_returns_summary_with_personnel_type() -> None:
    """SeimeiAssessmentUseCase が人材4類型と七格を含む結果を返す"""
    usecase = SeimeiAssessmentUseCase()
    summary = usecase.assess(
        surname="山田",
        given_name="太郎",
        surname_strokes=[3, 5],
        given_strokes=[4, 9],
    )
    assert "七格" in summary
    assert "人材4類型" in summary
    # 人材4類型の度数合計は 18（既存ロジック）
    total = sum(summary["人材4類型"].values())
    assert total == 18


# ----------------------------------------------------------------------------
# IChing UseCase
# ----------------------------------------------------------------------------


def test_iching_usecase_returns_hexagram_and_yao() -> None:
    """IChingDivinationUseCase が卦と爻を含む結果を返す"""
    usecase = IChingDivinationUseCase()
    summary = usecase.divine(
        question="今年の事業展望を観たい",
        context="建設業の新規事業を立ち上げ検討中",
    )
    assert "得卦" in summary
    assert "得爻" in summary
    assert "番号" in summary["得卦"]
    assert 1 <= summary["得卦"]["番号"] <= 64


def test_iching_usecase_determinism_with_fixed_timestamp() -> None:
    """timestamp を固定すると、同一入力で同じ結果"""
    usecase = IChingDivinationUseCase()
    ts = 1747573000.0
    r1 = usecase.divine("問A", "状況X", timestamp=ts)
    r2 = usecase.divine("問A", "状況X", timestamp=ts)
    assert r1["得卦"]["番号"] == r2["得卦"]["番号"]
    assert r1["得爻"]["番号"] == r2["得爻"]["番号"]


# ----------------------------------------------------------------------------
# Tarot UseCase
# ----------------------------------------------------------------------------


def test_tarot_celtic_cross_returns_10_cards() -> None:
    """ケルト十字スプレッドで 10 枚の DrawnCard が返る"""
    usecase = TarotReadingUseCase()
    reading = usecase.read(
        question="今年の事業展望",
        context="建設業の新規事業",
        spread_name="celtic_cross",
    )
    assert isinstance(reading, TarotReading)
    assert len(reading.drawn_cards) == 10
    # 各 DrawnCard の position が 0-9
    positions = sorted(d.position for d in reading.drawn_cards)
    assert positions == list(range(10))


def test_tarot_single_card_returns_1_card() -> None:
    """一枚引きスプレッドで 1 枚返る"""
    usecase = TarotReadingUseCase()
    reading = usecase.read(
        question="今日の指針",
        context="朝の一枚",
        spread_name="single_card",
    )
    assert len(reading.drawn_cards) == 1


def test_tarot_person_reading_returns_3_cards() -> None:
    """人物リーディングスプレッドで 3 枚返る（第三者代理引き専用）"""
    usecase = TarotReadingUseCase()
    reading = usecase.read(
        question="",  # 占的なしでも引ける（第三者代理）
        context="対話相手のプロファイリング",
        spread_name="person_reading",
    )
    assert len(reading.drawn_cards) == 3


def test_tarot_reading_determinism() -> None:
    """同じ占機・占的で 2 回引いた結果が一致する"""
    usecase = TarotReadingUseCase()
    ts = datetime(2026, 5, 18, 14, 30, 15)
    r1 = usecase.read("問A", "状況X", "past_present_future", timestamp=ts)
    r2 = usecase.read("問A", "状況X", "past_present_future", timestamp=ts)
    ids1 = [d.card.id for d in r1.drawn_cards]
    ids2 = [d.card.id for d in r2.drawn_cards]
    assert ids1 == ids2


def test_tarot_unknown_spread_raises() -> None:
    """未知のスプレッド名で ValueError"""
    usecase = TarotReadingUseCase()
    with pytest.raises(ValueError, match="スプレッド"):
        usecase.read("test", "ctx", "nonexistent_spread")


# ----------------------------------------------------------------------------
# Triple Divination
# ----------------------------------------------------------------------------


def test_triple_divination_synthesis_preserves_all_three() -> None:
    """DivinationTriplet が三 Summary をロスなく保持する"""
    seimei = {"七格": {"人格": {"数": 10}}, "人材4類型": {"軍人": 5, "天才": 4, "秀才": 5, "凡人": 4}}
    iching = {"得卦": {"番号": 1, "名前": "乾為天"}, "得爻": {"番号": 5}}
    tarot_reading = TarotReading(
        spread=SpreadDefinition(name="single_card", positions=("核心",), focus="一枚で観る"),
        drawn_cards=(
            DrawnCard(
                card=TarotCard(
                    id="major-00",
                    name="愚者",
                    arcana="major",
                    number=0,
                    keywords=("始まり",),
                    upright_meaning="新たな旅立ち",
                    reversed_meaning="軽率さ",
                ),
                is_reversed=False,
                position=0,
            ),
        ),
        question="今日の指針",
        context="朝の一枚",
        timestamp=datetime(2026, 5, 18, 9, 0, 0),
    )

    usecase = TripleDivinationUseCase()
    triplet = usecase.synthesize(seimei, iching, tarot_reading)

    assert isinstance(triplet, DivinationTriplet)
    assert triplet.seimei_summary["七格"]["人格"]["数"] == 10
    assert triplet.iching_summary["得卦"]["番号"] == 1
    # tarot_summary には引かれたカードの情報が保持される
    assert "drawn_cards" in triplet.tarot_summary
    assert len(triplet.tarot_summary["drawn_cards"]) == 1
    assert triplet.tarot_summary["drawn_cards"][0]["name"] == "愚者"
