from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from domain.feed_policy import FeedPolicy
from domain.feed_source import FeedSource
from domain.models import NewsItem
from usecases.run_daily_digest import RunDailyDigestUseCase, RunResult

JST = ZoneInfo("Asia/Tokyo")

NARUEBI = FeedSource(
    name="ナルエビちゃんニュース",
    url="https://news.nullevi.app/rss",
    policy=FeedPolicy.PASSTHROUGH,
)


class FakeRssGateway:
    def __init__(self, items):
        self._items = items

    def fetch_all(self):
        return list(self._items)


class FakeMailGateway:
    def __init__(self):
        self.sent = []

    def send(self, **kwargs):
        self.sent.append(kwargs)


class FakeStateStore:
    def __init__(self, already_sent=None):
        self.sent_dates: set[str] = set(already_sent or [])
        self.mark_called: list[str] = []

    def is_sent(self, target_date: str) -> bool:
        return target_date in self.sent_dates

    def mark_sent(self, target_date: str) -> None:
        self.sent_dates.add(target_date)
        self.mark_called.append(target_date)


def _item(day: int, hour: int, title: str = "t") -> NewsItem:
    return NewsItem(
        title=title,
        link=f"https://news.nullevi.app/{day}-{hour}",
        guid=f"https://news.nullevi.app/{day}-{hour}",
        pub_date_jst=datetime(2026, 5, day, hour, 0, 0, tzinfo=JST),
        description="body",
        categories=("AI",),
        source_name="ナルエビちゃんニュース",
    )


def _build_uc(rss_items, *, already_sent=None):
    rss = FakeRssGateway(rss_items)
    mail = FakeMailGateway()
    state = FakeStateStore(already_sent=already_sent)
    uc = RunDailyDigestUseCase(
        gateways=[(NARUEBI, rss)],
        mail_gateway=mail,
        state_store=state,
        sender="from@example.com",
        recipient="to@example.com",
    )
    return uc, mail, state


def test_full_flow_sends_email_when_yesterday_has_items():
    uc, mail, state = _build_uc([_item(11, 12, "yesterday")])
    result = uc.execute(now=datetime(2026, 5, 12, 0, 10, 0, tzinfo=JST))
    assert result.result == RunResult.SENT
    assert len(mail.sent) == 1
    assert state.sent_dates == {"2026-05-11"}


def test_skips_email_when_zero_items_yesterday():
    uc, mail, state = _build_uc([_item(12, 12, "today")])
    result = uc.execute(now=datetime(2026, 5, 12, 0, 10, 0, tzinfo=JST))
    assert result.result == RunResult.NO_ITEMS
    assert mail.sent == []
    assert state.mark_called == []


def test_skips_when_already_sent_today():
    uc, mail, state = _build_uc(
        [_item(11, 12, "y")], already_sent={"2026-05-11"}
    )
    result = uc.execute(now=datetime(2026, 5, 12, 0, 10, 0, tzinfo=JST))
    assert result.result == RunResult.ALREADY_SENT
    assert mail.sent == []
    assert state.mark_called == []


def test_target_date_override_via_now():
    # 2026-05-13 0:10 で実行すると 5/12 が前日
    uc, mail, state = _build_uc([_item(12, 12, "in_range"), _item(11, 12, "out")])
    result = uc.execute(now=datetime(2026, 5, 13, 0, 10, 0, tzinfo=JST))
    assert result.result == RunResult.SENT
    assert state.sent_dates == {"2026-05-12"}


def test_dry_run_skips_send_and_state_mark():
    uc, mail, state = _build_uc([_item(11, 12, "y")])
    result = uc.execute(
        now=datetime(2026, 5, 12, 0, 10, 0, tzinfo=JST), dry_run=True
    )
    assert result.result == RunResult.DRY_RUN
    assert result.digest is not None
    assert mail.sent == []
    assert state.mark_called == []
