"""UseCase 層が依存する Port（抽象インターフェース）群。

Port は Protocol で定義し、実装は adapters/ 配下に置く。テストは fake 実装で駆動する。
"""
from __future__ import annotations

from typing import List, Optional, Protocol

from domain.lease import SessionLease
from domain.models import OutboundMessage, TelegramUpdate
from domain.offset import UpdateOffset


class UpdateSource(Protocol):
    """Telegram getUpdates を抽象化する Port。"""

    def fetch(self, offset: UpdateOffset, timeout_seconds: int = 30) -> List[TelegramUpdate]:
        ...


class MessageSink(Protocol):
    """sendMessage を抽象化する Port。"""

    def send(self, message: OutboundMessage) -> None:
        ...


class OffsetStore(Protocol):
    """update offset の永続化。in-memory + 定期 flush を許容。"""

    def load(self) -> UpdateOffset:
        ...

    def save(self, offset: UpdateOffset) -> None:
        ...


class LeaseStore(Protocol):
    """セッションリースの永続化。"""

    def load(self) -> Optional[SessionLease]:
        ...

    def save(self, lease: SessionLease) -> None:
        ...

    def clear(self) -> None:
        ...
