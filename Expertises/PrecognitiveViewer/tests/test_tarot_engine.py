"""Stage 2b Tests — Tarot Repository + Shuffler の動作を検証する。

計画書 Stage 2 の Success Criteria より:
- test_tarot_repository_loads_78_cards
- test_tarot_shuffler_determinism
- test_tarot_shuffler_uniqueness

加えてスート別カウント・スプレッド数・大小アルカナ数を補強的に検証する。
"""
from __future__ import annotations

from collections import Counter

import pytest

from PrecognitiveViewer.Tarot.tarot_engine import (
    DeterministicShuffler,
    SpreadRepository,
    TarotCardRepository,
)


# ----------------------------------------------------------------------------
# Repository
# ----------------------------------------------------------------------------


def test_tarot_repository_loads_78_cards() -> None:
    """78 枚のカード（Major 22 + Minor 56）が読み込まれる"""
    repo = TarotCardRepository()
    cards = repo.load_all()
    assert len(cards) == 78


def test_tarot_repository_major_count_22() -> None:
    """大アルカナが 22 枚"""
    repo = TarotCardRepository()
    major = [c for c in repo.load_all() if c.arcana == "major"]
    assert len(major) == 22
    # 番号 0-21 がすべて存在
    numbers = sorted(c.number for c in major)
    assert numbers == list(range(22))


def test_tarot_repository_minor_count_56_with_4_suits() -> None:
    """小アルカナが 56 枚、4 スート × 14 枚"""
    repo = TarotCardRepository()
    minor = [c for c in repo.load_all() if c.arcana == "minor"]
    assert len(minor) == 56
    suits = Counter(c.suit for c in minor)
    assert suits == {"wands": 14, "cups": 14, "swords": 14, "pentacles": 14}


def test_tarot_repository_all_cards_have_japanese_name() -> None:
    """全カードに日本語名が設定されている"""
    repo = TarotCardRepository()
    for card in repo.load_all():
        # 名前にひらがな・カタカナ・漢字のいずれかを含む
        assert any(
            "぀" <= ch <= "ヿ" or "一" <= ch <= "鿿"
            for ch in card.name
        ), f"日本語名が見当たらない: {card.id} / {card.name}"


# ----------------------------------------------------------------------------
# Spread Repository
# ----------------------------------------------------------------------------


def test_tarot_spread_repository_has_at_least_4_spreads() -> None:
    """最低 4 スプレッド（Single / 3-Card / Celtic Cross / Decision Making）が定義される"""
    repo = SpreadRepository()
    spreads = repo.load_all()
    assert len(spreads) >= 4
    names = {s.name for s in spreads}
    expected = {
        "single_card",
        "past_present_future",
        "celtic_cross",
        "decision_making",
    }
    assert expected.issubset(names)


def test_tarot_spread_celtic_cross_has_10_positions() -> None:
    """ケルト十字スプレッドは 10 ポジション"""
    repo = SpreadRepository()
    spreads = {s.name: s for s in repo.load_all()}
    assert spreads["celtic_cross"].card_count == 10


# ----------------------------------------------------------------------------
# Deterministic Shuffler
# ----------------------------------------------------------------------------


def test_tarot_shuffler_determinism() -> None:
    """同一入力で 2 回 shuffle した結果が一致する"""
    shuffler = DeterministicShuffler()
    seq1 = shuffler.shuffle(
        question="今年の事業展望",
        context="建設業の新規事業を立ち上げ検討中",
        timestamp=1747573000.0,
        n=10,
    )
    seq2 = shuffler.shuffle(
        question="今年の事業展望",
        context="建設業の新規事業を立ち上げ検討中",
        timestamp=1747573000.0,
        n=10,
    )
    assert seq1 == seq2


def test_tarot_shuffler_uniqueness() -> None:
    """引かれた 10 枚に重複なし"""
    shuffler = DeterministicShuffler()
    seq = shuffler.shuffle(
        question="人物リーディング",
        context="対話相手の存在を観る",
        timestamp=1747573000.0,
        n=10,
    )
    assert len(seq) == 10
    assert len(set(seq)) == 10


def test_tarot_shuffler_differs_by_input() -> None:
    """異なる占的では順列が異なる"""
    shuffler = DeterministicShuffler()
    seq1 = shuffler.shuffle("問A", "状況X", 1747573000.0, 5)
    seq2 = shuffler.shuffle("問B", "状況X", 1747573000.0, 5)
    assert seq1 != seq2


def test_tarot_shuffler_range() -> None:
    """shuffle 結果は 0-77 の範囲のインデックスを返す"""
    shuffler = DeterministicShuffler()
    seq = shuffler.shuffle("test", "ctx", 1747573000.0, 78)
    assert all(0 <= idx < 78 for idx in seq)
    assert len(set(seq)) == 78  # 全78枚を引いた場合、重複なし
