from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from domain.digest import DailyDigest
from domain.exceptions import ValidationError
from domain.models import NewsItem

JST = ZoneInfo("Asia/Tokyo")


def _item(title: str = "title", hour: int = 12) -> NewsItem:
    return NewsItem(
        title=title,
        link="https://news.nullevi.app/x",
        guid="https://news.nullevi.app/x",
        pub_date_jst=datetime(2026, 5, 11, hour, 0, 0, tzinfo=JST),
        description="body",
        categories=("AI",),
        source_name="ナルエビちゃんニュース",
    )


class TestDailyDigest:
    def test_target_date_must_be_iso_string(self):
        DailyDigest(
            target_date="2026-05-11",
            items=(_item(),),
            formatted_subject="s",
            formatted_body="b",
        )

    def test_rejects_invalid_iso_date(self):
        with pytest.raises(ValidationError):
            DailyDigest(
                target_date="2026/05/11",
                items=(_item(),),
                formatted_subject="s",
                formatted_body="b",
            )

    def test_rejects_empty_subject(self):
        with pytest.raises(ValidationError):
            DailyDigest(
                target_date="2026-05-11",
                items=(_item(),),
                formatted_subject="",
                formatted_body="b",
            )

    def test_rejects_empty_body(self):
        with pytest.raises(ValidationError):
            DailyDigest(
                target_date="2026-05-11",
                items=(_item(),),
                formatted_subject="s",
                formatted_body="",
            )

    def test_zero_items_allowed(self):
        # 0件でも DailyDigest としては有効（送信スキップは UseCase 側で判断）
        d = DailyDigest(
            target_date="2026-05-11",
            items=(),
            formatted_subject="s",
            formatted_body="b",
        )
        assert d.is_empty is True

    def test_is_empty_false_when_items(self):
        d = DailyDigest(
            target_date="2026-05-11",
            items=(_item(),),
            formatted_subject="s",
            formatted_body="b",
        )
        assert d.is_empty is False

    def test_frozen(self):
        d = DailyDigest(
            target_date="2026-05-11",
            items=(_item(),),
            formatted_subject="s",
            formatted_body="b",
        )
        with pytest.raises(Exception):
            d.target_date = "x"  # type: ignore[misc]
