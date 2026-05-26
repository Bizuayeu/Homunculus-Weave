from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from domain.exceptions import LeaseConflictError
from domain.lease import SessionLease
from domain.models import OutboundMessage
from domain.offset import UpdateOffset
from usecases.send_reply import SendReply

from tests.usecases.fakes import FakeLeaseStore, FakeMessageSink, FakeOffsetStore


def _t(seconds: int = 0) -> datetime:
    base = datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc)
    return base + timedelta(seconds=seconds)


def test_successful_send_advances_offset_and_renews_lease():
    sink = FakeMessageSink()
    offset_store = FakeOffsetStore(initial=UpdateOffset(value=10))
    lease = SessionLease(owner="me", heartbeat=_t(0), ttl_seconds=120)
    lease_store = FakeLeaseStore(initial=lease)

    uc = SendReply(sink, offset_store, lease_store)
    renewed = uc.execute(
        message=OutboundMessage(chat_id=100, text="hi"),
        update_id=15,
        lease=lease,
        now=_t(30),
    )

    assert len(sink.sent) == 1
    assert sink.sent[0].text == "hi"
    assert offset_store.offset.value == 16  # max(10, 15+1)
    assert renewed.heartbeat == _t(30)
    assert lease_store.lease == renewed


def test_send_failure_does_not_advance_offset_or_renew_lease():
    sink = FakeMessageSink(fail=True)
    offset_store = FakeOffsetStore(initial=UpdateOffset(value=10))
    lease = SessionLease(owner="me", heartbeat=_t(0), ttl_seconds=120)
    lease_store = FakeLeaseStore(initial=lease)

    uc = SendReply(sink, offset_store, lease_store)
    with pytest.raises(RuntimeError):
        uc.execute(
            message=OutboundMessage(chat_id=100, text="hi"),
            update_id=15,
            lease=lease,
            now=_t(30),
        )

    # 送信失敗時は永続化が走らない（offset 据え置き / lease 据え置き）
    assert offset_store.offset.value == 10
    assert offset_store.save_calls == []
    assert lease_store.lease == lease
    assert lease_store.save_calls == []


def test_offset_advance_is_idempotent_with_smaller_update_id():
    # 既に進んでいる場合は巻き戻らない（再処理時の冪等性）
    sink = FakeMessageSink()
    offset_store = FakeOffsetStore(initial=UpdateOffset(value=20))
    lease = SessionLease(owner="me", heartbeat=_t(0), ttl_seconds=120)
    lease_store = FakeLeaseStore(initial=lease)

    uc = SendReply(sink, offset_store, lease_store)
    uc.execute(
        message=OutboundMessage(chat_id=100, text="hi"),
        update_id=5,
        lease=lease,
        now=_t(10),
    )
    assert offset_store.offset.value == 20  # max(20, 5+1) = 20


def test_send_raises_when_lease_was_stolen():
    # store には他人の lease（=奪取後の状態）
    stolen = SessionLease(owner="other", heartbeat=_t(30), ttl_seconds=120)
    lease_store = FakeLeaseStore(initial=stolen)

    # 我々が握っている古い lease snapshot
    my_lease = SessionLease(owner="me", heartbeat=_t(0), ttl_seconds=120)

    sink = FakeMessageSink()
    offset_store = FakeOffsetStore(initial=UpdateOffset(value=10))
    uc = SendReply(sink, offset_store, lease_store)
    with pytest.raises(LeaseConflictError):
        uc.execute(
            message=OutboundMessage(chat_id=100, text="hi"),
            update_id=15,
            lease=my_lease,
            now=_t(40),
        )
    # 何も書き換わらない（送信せず、offset 据え置き、他人 lease は触らない）
    assert sink.sent == []
    assert offset_store.save_calls == []
    assert lease_store.save_calls == []
    assert lease_store.lease == stolen


def test_send_raises_when_lease_was_released():
    # lease が release されて消えている状態
    lease_store = FakeLeaseStore(initial=None)
    my_lease = SessionLease(owner="me", heartbeat=_t(0), ttl_seconds=120)

    sink = FakeMessageSink()
    offset_store = FakeOffsetStore(initial=UpdateOffset(value=10))
    uc = SendReply(sink, offset_store, lease_store)
    with pytest.raises(LeaseConflictError):
        uc.execute(
            message=OutboundMessage(chat_id=100, text="hi"),
            update_id=15,
            lease=my_lease,
            now=_t(40),
        )
    assert sink.sent == []
    assert offset_store.save_calls == []
