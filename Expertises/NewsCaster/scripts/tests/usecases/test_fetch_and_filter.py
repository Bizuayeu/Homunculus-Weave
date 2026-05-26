from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from domain.date_range import DateRangeJST
from domain.exceptions import RssFetchError
from domain.feed_policy import FeedPolicy
from domain.feed_source import FeedSource
from domain.models import NewsItem
from usecases.fetch_and_filter import FetchAndFilterUseCase

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


class FakeRssGateway:
    def __init__(self, items: list[NewsItem]):
        self._items = items
        self.fetch_called = 0

    def fetch_all(self) -> list[NewsItem]:
        self.fetch_called += 1
        return list(self._items)


class FailingRssGateway:
    def __init__(self, exc: RssFetchError):
        self._exc = exc

    def fetch_all(self) -> list[NewsItem]:
        raise self._exc


def _item(
    day: int,
    hour: int,
    title: str = "t",
    source_name: str = NARUEBI.name,
) -> NewsItem:
    return NewsItem(
        title=title,
        link=f"https://x.example/{source_name}/{day}-{hour}",
        guid=f"https://x.example/{source_name}/{day}-{hour}",
        pub_date_jst=datetime(2026, 5, day, hour, 0, 0, tzinfo=JST),
        description=f"body {day}-{hour}",
        categories=("AI",),
        source_name=source_name,
    )


def _range_for_5_11() -> DateRangeJST:
    return DateRangeJST.from_yesterday(datetime(2026, 5, 12, 0, 10, 0, tzinfo=JST))


def test_keeps_only_yesterday_items():
    items = [
        _item(10, 12, "Day before yesterday"),
        _item(11, 0, "Yesterday morning"),
        _item(11, 23, "Yesterday night"),
        _item(12, 0, "Today"),
        _item(12, 10, "After execution time"),
    ]
    gw = FakeRssGateway(items)
    uc = FetchAndFilterUseCase(gateways=[(NARUEBI, gw)])

    result = uc.execute(date_range=_range_for_5_11())

    titles = [i.title for i in result]
    assert titles == ["Yesterday night", "Yesterday morning"]  # 降順


def test_zero_items_when_no_match():
    gw = FakeRssGateway([_item(12, 12, "Today")])
    uc = FetchAndFilterUseCase(gateways=[(NARUEBI, gw)])
    assert uc.execute(date_range=_range_for_5_11()) == []


def test_calls_rss_gateway_once():
    gw = FakeRssGateway([])
    uc = FetchAndFilterUseCase(gateways=[(NARUEBI, gw)])
    uc.execute(date_range=_range_for_5_11())
    assert gw.fetch_called == 1


def test_sorts_descending_by_pub_date():
    items = [
        _item(11, 5, "early"),
        _item(11, 20, "late"),
        _item(11, 12, "noon"),
    ]
    gw = FakeRssGateway(items)
    uc = FetchAndFilterUseCase(gateways=[(NARUEBI, gw)])
    result = uc.execute(date_range=_range_for_5_11())
    assert [i.title for i in result] == ["late", "noon", "early"]


# ----- Stage 5b: Multi-feed support -----


def test_collects_from_multiple_feeds():
    naruebi_items = [_item(11, 10, "naruebi-AM", source_name=NARUEBI.name)]
    wireless_items = [
        _item(11, 22, "wire-PM", source_name=WIRELESS.name),
        _item(11, 8, "wire-AM", source_name=WIRELESS.name),
    ]
    uc = FetchAndFilterUseCase(
        gateways=[
            (NARUEBI, FakeRssGateway(naruebi_items)),
            (WIRELESS, FakeRssGateway(wireless_items)),
        ]
    )
    result = uc.execute(date_range=_range_for_5_11())

    titles = [i.title for i in result]
    # 時刻降順、出典横断
    assert titles == ["wire-PM", "naruebi-AM", "wire-AM"]


def test_skips_failing_feed_and_continues(capsys):
    naruebi_items = [_item(11, 12, "alive", source_name=NARUEBI.name)]
    uc = FetchAndFilterUseCase(
        gateways=[
            (NARUEBI, FakeRssGateway(naruebi_items)),
            (
                WIRELESS,
                FailingRssGateway(
                    RssFetchError("403 Forbidden", status_code=403)
                ),
            ),
        ]
    )

    result = uc.execute(date_range=_range_for_5_11())

    assert [i.title for i in result] == ["alive"]
    err = capsys.readouterr().err
    assert "Wireless Wire News" in err
    assert "403" in err


def test_raises_when_all_feeds_fail():
    err1 = RssFetchError("naruebi down", status_code=500)
    err2 = RssFetchError("wireless down", status_code=502)
    uc = FetchAndFilterUseCase(
        gateways=[
            (NARUEBI, FailingRssGateway(err1)),
            (WIRELESS, FailingRssGateway(err2)),
        ]
    )

    with pytest.raises(RssFetchError) as excinfo:
        uc.execute(date_range=_range_for_5_11())
    # 先頭のエラーが送出されること
    assert excinfo.value is err1


def test_rejects_empty_gateways():
    with pytest.raises(ValueError):
        FetchAndFilterUseCase(gateways=[])
