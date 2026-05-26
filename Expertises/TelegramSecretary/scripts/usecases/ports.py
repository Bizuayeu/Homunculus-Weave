"""UseCase 層が依存する Port（抽象インターフェース）群。

Port は Protocol で定義し、実装は adapters/ 配下に置く。テストは fake 実装で駆動する。
"""
from __future__ import annotations

from pathlib import Path
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


class MediaDownloader(Protocol):
    """Telegram の file_id から実ファイルを download する Port（Stage 6.2）。

    実装は adapters/telegram/media_downloader.py（Stage 6.3）。
    target_dir は state_dir/media/ を想定（呼び出し側が用意）。
    戻り値は保存先の絶対 Path。
    """

    def download(self, file_id: str, target_dir: Path) -> Path:
        ...
