from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from domain.digest import DailyDigest
from domain.models import NewsItem
from usecases.send_digest_email import SendDigestEmailUseCase

JST = ZoneInfo("Asia/Tokyo")


class FakeMailGateway:
    def __init__(self):
        self.sent: list[tuple[str, str, str, str]] = []

    def send(self, *, sender: str, to: str, subject: str, body: str) -> None:
        self.sent.append((sender, to, subject, body))


class FakeStateStore:
    def __init__(self, already_sent: set[str] | None = None):
        self.sent_dates: set[str] = set(already_sent or [])
        self.mark_called: list[str] = []

    def is_sent(self, target_date: str) -> bool:
        return target_date in self.sent_dates

    def mark_sent(self, target_date: str) -> None:
        self.sent_dates.add(target_date)
        self.mark_called.append(target_date)


def _digest(target_date: str = "2026-05-11", with_item: bool = True) -> DailyDigest:
    items = (
        (
            NewsItem(
                title="t",
                link="https://x.example/",
                guid="g",
                pub_date_jst=datetime(2026, 5, 11, 12, 0, 0, tzinfo=JST),
                description="b",
                categories=(),
                source_name="ナルエビちゃんニュース",
            ),
        )
        if with_item
        else ()
    )
    return DailyDigest(
        target_date=target_date,
        items=items,
        formatted_subject="件名",
        formatted_body="本文",
    )


def test_sends_email_when_not_sent_yet():
    mail = FakeMailGateway()
    state = FakeStateStore()
    uc = SendDigestEmailUseCase(
        mail_gateway=mail,
        state_store=state,
        sender="from@example.com",
        recipient="to@example.com",
    )

    sent = uc.execute(digest=_digest())

    assert sent is True
    assert len(mail.sent) == 1
    sender, to, subject, body = mail.sent[0]
    assert sender == "from@example.com"
    assert to == "to@example.com"
    assert subject == "件名"
    assert body == "本文"
    assert state.is_sent("2026-05-11") is True


def test_skips_when_already_sent_today():
    mail = FakeMailGateway()
    state = FakeStateStore(already_sent={"2026-05-11"})
    uc = SendDigestEmailUseCase(
        mail_gateway=mail,
        state_store=state,
        sender="from@example.com",
        recipient="to@example.com",
    )

    sent = uc.execute(digest=_digest())

    assert sent is False
    assert mail.sent == []
    assert state.mark_called == []


def test_marks_sent_after_successful_send():
    mail = FakeMailGateway()
    state = FakeStateStore()
    uc = SendDigestEmailUseCase(
        mail_gateway=mail,
        state_store=state,
        sender="from@example.com",
        recipient="to@example.com",
    )
    uc.execute(digest=_digest())
    assert state.mark_called == ["2026-05-11"]


def test_does_not_mark_sent_when_mail_fails():
    class FailingMail:
        def send(self, **_):
            raise RuntimeError("smtp down")

    state = FakeStateStore()
    uc = SendDigestEmailUseCase(
        mail_gateway=FailingMail(),
        state_store=state,
        sender="from@example.com",
        recipient="to@example.com",
    )

    try:
        uc.execute(digest=_digest())
    except RuntimeError:
        pass

    assert state.mark_called == []
