"""UseCase テスト用の fake adapter 群。"""
from __future__ import annotations

from typing import List, Optional

from domain.lease import SessionLease
from domain.models import OutboundMessage, TelegramUpdate
from domain.offset import UpdateOffset


class FakeUpdateSource:
    """fetch をスクリプト化された応答列で駆動する fake。"""

    def __init__(self, batches: Optional[List[List[TelegramUpdate]]] = None) -> None:
        self.batches = list(batches or [])
        self.fetch_calls: List[tuple[UpdateOffset, int]] = []

    def fetch(self, offset: UpdateOffset, timeout_seconds: int = 30) -> List[TelegramUpdate]:
        self.fetch_calls.append((offset, timeout_seconds))
        if not self.batches:
            return []
        return self.batches.pop(0)


class FakeMessageSink:
    """send を記録、`fail` フラグで例外を投げる fake。"""

    def __init__(self, fail: bool = False) -> None:
        self.sent: List[OutboundMessage] = []
        self.fail = fail

    def send(self, message: OutboundMessage) -> None:
        if self.fail:
            raise RuntimeError("simulated send failure")
        self.sent.append(message)


class FakeOffsetStore:
    """in-memory な offset store。"""

    def __init__(self, initial: Optional[UpdateOffset] = None) -> None:
        self.offset = initial or UpdateOffset.initial()
        self.save_calls: List[UpdateOffset] = []

    def load(self) -> UpdateOffset:
        return self.offset

    def save(self, offset: UpdateOffset) -> None:
        self.offset = offset
        self.save_calls.append(offset)


class FakeLeaseStore:
    """in-memory な lease store。"""

    def __init__(self, initial: Optional[SessionLease] = None) -> None:
        self.lease: Optional[SessionLease] = initial
        self.save_calls: List[SessionLease] = []
        self.clear_calls: int = 0

    def load(self) -> Optional[SessionLease]:
        return self.lease

    def save(self, lease: SessionLease) -> None:
        self.lease = lease
        self.save_calls.append(lease)

    def clear(self) -> None:
        self.lease = None
        self.clear_calls += 1
