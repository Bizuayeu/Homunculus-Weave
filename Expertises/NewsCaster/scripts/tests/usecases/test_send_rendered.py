from __future__ import annotations

from usecases.send_rendered import SendRenderedResult, SendRenderedUseCase


class FakeMailGateway:
    def __init__(self):
        self.sent: list[dict] = []

    def send(self, *, sender: str, to: str, subject: str, body: str) -> None:
        self.sent.append(
            {"sender": sender, "to": to, "subject": subject, "body": body}
        )


class FakeStateStore:
    def __init__(self, already_sent: set[str] | None = None):
        self.sent_dates: set[str] = set(already_sent or [])
        self.mark_called: list[str] = []

    def is_sent(self, target_date: str) -> bool:
        return target_date in self.sent_dates

    def mark_sent(self, target_date: str) -> None:
        self.sent_dates.add(target_date)
        self.mark_called.append(target_date)


def _build_uc(*, already_sent=None):
    mail = FakeMailGateway()
    state = FakeStateStore(already_sent=already_sent)
    uc = SendRenderedUseCase(
        mail_gateway=mail,
        state_store=state,
        sender="from@example.com",
        recipient="to@example.com",
    )
    return uc, mail, state


def test_sends_rendered_body_and_marks_state():
    uc, mail, state = _build_uc()
    result = uc.execute(
        target_date="2026-05-11",
        subject="件名",
        body="本文",
    )
    assert result is SendRenderedResult.SENT
    assert len(mail.sent) == 1
    assert mail.sent[0]["subject"] == "件名"
    assert mail.sent[0]["body"] == "本文"
    assert state.is_sent("2026-05-11") is True


def test_skips_when_already_sent():
    uc, mail, state = _build_uc(already_sent={"2026-05-11"})
    result = uc.execute(
        target_date="2026-05-11",
        subject="件名",
        body="本文",
    )
    assert result is SendRenderedResult.ALREADY_SENT
    assert mail.sent == []
    assert state.mark_called == []


def test_does_not_mark_when_send_fails():
    class FailingMail:
        def send(self, **_):
            raise RuntimeError("smtp down")

    state = FakeStateStore()
    uc = SendRenderedUseCase(
        mail_gateway=FailingMail(),
        state_store=state,
        sender="from@example.com",
        recipient="to@example.com",
    )
    try:
        uc.execute(target_date="2026-05-11", subject="件名", body="本文")
    except RuntimeError:
        pass
    assert state.mark_called == []


def test_refuses_unfilled_placeholder():
    """親プロセス Weave が書き換え忘れた WEAVE_COMPACT プレースホルダ残存時は送信を拒否する。"""
    uc, mail, state = _build_uc()
    result = uc.execute(
        target_date="2026-05-11",
        subject="件名",
        body="本文\n{{WEAVE_COMPACT:abc-123}}\n他の本文",
    )
    assert result is SendRenderedResult.PLACEHOLDER_REMAINS
    assert mail.sent == []
    assert state.mark_called == []
