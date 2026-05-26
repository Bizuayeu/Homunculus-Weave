from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from domain.feed_policy import FeedPolicy
from domain.feed_source import FeedSource
from domain.models import NewsItem
from usecases.format_digest import FormatDigestUseCase

JST = ZoneInfo("Asia/Tokyo")

NARUEBI = FeedSource(
    name="ナルエビちゃんニュース",
    url="https://news.nullevi.app/rss",
    policy=FeedPolicy.PASSTHROUGH,
)
WIRELESS = FeedSource(
    name="Wireless Wire News",
    url="https://wirelesswire.jp/feed/",
    policy=FeedPolicy.WEAVE_COMPACT,
)


def _item(
    hour: int,
    title: str,
    desc: str = "本文",
    cats: tuple = ("AI",),
    source_name: str = NARUEBI.name,
    guid: str | None = None,
) -> NewsItem:
    link = f"https://x.example/{source_name}/{hour}"
    return NewsItem(
        title=title,
        link=link,
        guid=guid or link,
        pub_date_jst=datetime(2026, 5, 11, hour, 0, 0, tzinfo=JST),
        description=desc,
        categories=cats,
        source_name=source_name,
    )


def test_subject_contains_date_and_count():
    uc = FormatDigestUseCase()
    digest = uc.execute(
        target_date="2026-05-11",
        items=[_item(10, "A"), _item(12, "B")],
        feed_sources=(NARUEBI,),
    )
    assert "2026-05-11" in digest.formatted_subject
    assert "2件" in digest.formatted_subject
    assert "1ソース" in digest.formatted_subject
    assert "NewsCaster" in digest.formatted_subject


def test_body_contains_each_item_title_and_link():
    uc = FormatDigestUseCase()
    digest = uc.execute(
        target_date="2026-05-11",
        items=[_item(10, "TitleAlpha", "Body alpha"), _item(12, "TitleBeta", "Body beta")],
        feed_sources=(NARUEBI,),
    )
    assert "TitleAlpha" in digest.formatted_body
    assert "TitleBeta" in digest.formatted_body
    assert "Body alpha" in digest.formatted_body
    assert "Body beta" in digest.formatted_body


def test_body_includes_jst_pubdate_and_categories():
    uc = FormatDigestUseCase()
    digest = uc.execute(
        target_date="2026-05-11",
        items=[_item(15, "T", cats=("Cat1", "Cat2", "Cat3"))],
        feed_sources=(NARUEBI,),
    )
    assert "15:00" in digest.formatted_body
    assert "Cat1" in digest.formatted_body
    assert "Cat2" in digest.formatted_body
    assert "Cat3" in digest.formatted_body


def test_zero_items_produces_silent_digest():
    uc = FormatDigestUseCase()
    digest = uc.execute(
        target_date="2026-05-11",
        items=[],
        feed_sources=(NARUEBI,),
    )
    assert digest.is_empty is True
    assert digest.target_date == "2026-05-11"
    assert digest.formatted_subject
    assert digest.formatted_body
    assert "0件" in digest.formatted_subject
    assert "0ソース" in digest.formatted_subject


def test_target_date_propagated():
    uc = FormatDigestUseCase()
    digest = uc.execute(
        target_date="2026-05-11",
        items=[_item(10, "A")],
        feed_sources=(NARUEBI,),
    )
    assert digest.target_date == "2026-05-11"


def test_items_tuple_preserved_order():
    uc = FormatDigestUseCase()
    a = _item(12, "first")
    b = _item(10, "second")
    digest = uc.execute(
        target_date="2026-05-11",
        items=[a, b],
        feed_sources=(NARUEBI,),
    )
    assert digest.items == (a, b)


# ----- Stage 5b: Multi-source sections -----


def test_groups_by_source():
    uc = FormatDigestUseCase()
    items = [
        _item(12, "NaruebiA", source_name=NARUEBI.name),
        _item(11, "WireA", desc="装飾エッセイ", source_name=WIRELESS.name),
        _item(10, "WireB", desc="別の装飾エッセイ", source_name=WIRELESS.name),
    ]
    digest = uc.execute(
        target_date="2026-05-11",
        items=items,
        feed_sources=(NARUEBI, WIRELESS),
    )
    body = digest.formatted_body

    # フィード見出しが両方含まれる
    assert NARUEBI.name in body
    assert WIRELESS.name in body
    # フィード順序が feed_sources の順に従う（ナルエビ先・WirelessWire後）
    naruebi_pos = body.index(NARUEBI.name)
    wireless_pos = body.index(WIRELESS.name)
    assert naruebi_pos < wireless_pos
    # subject の「Mソース」が2
    assert "2ソース" in digest.formatted_subject


def test_emits_placeholder_for_weave_compact_items():
    uc = FormatDigestUseCase()
    wire_item = _item(
        12,
        "装飾的なエッセイのタイトル",
        desc="長い装飾的な本文がここに入る。生のまま出すと長すぎる。",
        source_name=WIRELESS.name,
        guid="wire-guid-001",
    )
    digest = uc.execute(
        target_date="2026-05-11",
        items=[wire_item],
        feed_sources=(WIRELESS,),
    )
    body = digest.formatted_body

    # プレースホルダが含まれる
    assert "{{WEAVE_COMPACT:wire-guid-001}}" in body
    # 本文 description は出力されない
    assert "長い装飾的な本文" not in body
    # タイトル/リンク等のメタは出力される
    assert "装飾的なエッセイのタイトル" in body


def test_passthrough_keeps_description_verbatim():
    uc = FormatDigestUseCase()
    naruebi_item = _item(
        10,
        "ナルエビ要旨",
        desc="既に要約された1段落の description",
        source_name=NARUEBI.name,
    )
    digest = uc.execute(
        target_date="2026-05-11",
        items=[naruebi_item],
        feed_sources=(NARUEBI,),
    )
    body = digest.formatted_body

    assert "既に要約された1段落の description" in body
    assert "{{WEAVE_COMPACT" not in body


def test_empty_source_is_skipped_in_body():
    # WIRELESS は items を持たない → セクション見出しが出ない
    uc = FormatDigestUseCase()
    digest = uc.execute(
        target_date="2026-05-11",
        items=[_item(12, "OnlyNaruebi", source_name=NARUEBI.name)],
        feed_sources=(NARUEBI, WIRELESS),
    )
    body = digest.formatted_body

    assert NARUEBI.name in body
    assert WIRELESS.name not in body
    # subject の「Mソース」は1（items を持つフィードだけカウント）
    assert "1ソース" in digest.formatted_subject
