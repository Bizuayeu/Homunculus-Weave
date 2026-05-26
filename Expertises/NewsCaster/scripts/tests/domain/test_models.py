from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from domain.exceptions import ValidationError
from domain.models import NewsItem

JST = ZoneInfo("Asia/Tokyo")


def _rss_dict(**overrides) -> dict:
    base = {
        "title": "グーグル、AIを悪用した大規模ハッキング未遂を初検知",
        "link": "https://news.nullevi.app/google-ai-abuse-hacking-foiled-2026-05-12",
        "guid": "https://news.nullevi.app/google-ai-abuse-hacking-foiled-2026-05-12",
        "pubDate": "Tue, 12 May 2026 08:00:00 GMT",
        "description": "Alphabet傘下のグーグルが2026-05-11発表の報告書で...",
        "category": "Google, AI悪用, サイバーセキュリティ, 脆弱性",
    }
    base.update(overrides)
    return base


DEFAULT_SOURCE_NAME = "ナルエビちゃんニュース"


class TestNewsItemFromRssDict:
    def test_happy_path_creates_aware_jst_datetime(self):
        item = NewsItem.from_rss_dict(_rss_dict(), source_name=DEFAULT_SOURCE_NAME)

        assert item.title.startswith("グーグル")
        assert item.link.startswith("https://")
        assert item.guid == item.link
        # GMT 08:00 → JST 17:00 (+09:00)
        assert item.pub_date_jst == datetime(2026, 5, 12, 17, 0, 0, tzinfo=JST)
        assert item.pub_date_jst.tzinfo is not None
        assert item.description.startswith("Alphabet")
        assert item.categories == ("Google", "AI悪用", "サイバーセキュリティ", "脆弱性")
        assert item.source_name == DEFAULT_SOURCE_NAME

    def test_carries_source_name(self):
        item = NewsItem.from_rss_dict(_rss_dict(), source_name="Wireless Wire News")
        assert item.source_name == "Wireless Wire News"

    def test_rejects_empty_source_name(self):
        with pytest.raises(ValidationError):
            NewsItem.from_rss_dict(_rss_dict(), source_name="")

    def test_rejects_whitespace_source_name(self):
        with pytest.raises(ValidationError):
            NewsItem.from_rss_dict(_rss_dict(), source_name="   ")

    def test_rejects_invalid_pubdate(self):
        with pytest.raises(ValidationError):
            NewsItem.from_rss_dict(
                _rss_dict(pubDate="invalid string"),
                source_name=DEFAULT_SOURCE_NAME,
            )

    def test_rejects_empty_title(self):
        with pytest.raises(ValidationError):
            NewsItem.from_rss_dict(_rss_dict(title=""), source_name=DEFAULT_SOURCE_NAME)

    def test_rejects_empty_link(self):
        with pytest.raises(ValidationError):
            NewsItem.from_rss_dict(_rss_dict(link=""), source_name=DEFAULT_SOURCE_NAME)

    def test_handles_empty_categories(self):
        item = NewsItem.from_rss_dict(
            _rss_dict(category=""), source_name=DEFAULT_SOURCE_NAME
        )
        assert item.categories == ()

    def test_strips_category_whitespace(self):
        item = NewsItem.from_rss_dict(
            _rss_dict(category="  A ,  B,C  "), source_name=DEFAULT_SOURCE_NAME
        )
        assert item.categories == ("A", "B", "C")

    def test_missing_optional_description_defaults_empty(self):
        d = _rss_dict()
        d.pop("description")
        item = NewsItem.from_rss_dict(d, source_name=DEFAULT_SOURCE_NAME)
        assert item.description == ""

    def test_frozen_dataclass_immutable(self):
        item = NewsItem.from_rss_dict(_rss_dict(), source_name=DEFAULT_SOURCE_NAME)
        with pytest.raises(Exception):
            item.title = "mutated"  # type: ignore[misc]


class TestNewsItemDirectConstruction:
    def test_direct_construction_requires_aware_datetime(self):
        with pytest.raises(ValidationError):
            NewsItem(
                title="t",
                link="https://x.example/",
                guid="g",
                pub_date_jst=datetime(2026, 5, 11, 12, 0, 0),  # naive
                description="",
                categories=(),
                source_name=DEFAULT_SOURCE_NAME,
            )

    def test_direct_construction_with_utc_datetime_rejected(self):
        # JST 以外の aware datetime も拒否（pub_date_jst フィールドの意味的純度）
        with pytest.raises(ValidationError):
            NewsItem(
                title="t",
                link="https://x.example/",
                guid="g",
                pub_date_jst=datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc),
                description="",
                categories=(),
                source_name=DEFAULT_SOURCE_NAME,
            )

    def test_direct_construction_rejects_empty_source_name(self):
        with pytest.raises(ValidationError):
            NewsItem(
                title="t",
                link="https://x.example/",
                guid="g",
                pub_date_jst=datetime(2026, 5, 11, 12, 0, 0, tzinfo=JST),
                description="",
                categories=(),
                source_name="",
            )
