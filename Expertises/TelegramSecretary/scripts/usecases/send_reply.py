"""Weave 起草の返信を送信 → offset 永続化 → lease renew。"""
from __future__ import annotations

from datetime import datetime

from domain.lease import SessionLease
from domain.models import OutboundMessage
from usecases.ports import LeaseStore, MessageSink, OffsetStore


class SendReply:
    def __init__(
        self,
        sink: MessageSink,
        offset_store: OffsetStore,
        lease_store: LeaseStore,
    ) -> None:
        self._sink = sink
        self._offset_store = offset_store
        self._lease_store = lease_store

    def execute(
        self,
        message: OutboundMessage,
        update_id: int,
        lease: SessionLease,
        now: datetime,
    ) -> SessionLease:
        """送信成功時のみ offset を advance、lease を renew する。

        - 送信失敗（例外伝播）時は offset/lease を変更しない → 次回 cron で同 update_id を再処理
        - 同じ update_id の advance は単調増加なので冪等
        """
        # 1. 送信を先に試行（失敗したら以降の永続化は走らない）
        self._sink.send(message)

        # 2. offset advance
        offset = self._offset_store.load()
        new_offset = offset.advance(update_id)
        self._offset_store.save(new_offset)

        # 3. lease renew
        renewed = lease.renew(now)
        self._lease_store.save(renewed)
        return renewed
