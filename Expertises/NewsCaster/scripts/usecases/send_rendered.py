from __future__ import annotations

import re
from enum import Enum

from usecases.ports import MailGatewayPort, StateStorePort


class SendRenderedResult(str, Enum):
    SENT = "sent"
    ALREADY_SENT = "already_sent"
    PLACEHOLDER_REMAINS = "placeholder_remains"


_PLACEHOLDER_PATTERN = re.compile(r"\{\{WEAVE_COMPACT:[^}]+\}\}")


class SendRenderedUseCase:
    """親プロセス Weave がベタ化済みの subject/body を直接送信する UseCase。

    プレースホルダ残存検出により Weave 書き換え失敗時の事故送信を防ぐ。
    target_date 単位の冪等性は SendDigestEmailUseCase と同じ規約。
    """

    def __init__(
        self,
        *,
        mail_gateway: MailGatewayPort,
        state_store: StateStorePort,
        sender: str,
        recipient: str,
    ) -> None:
        self._mail = mail_gateway
        self._state = state_store
        self._sender = sender
        self._recipient = recipient

    def execute(
        self, *, target_date: str, subject: str, body: str
    ) -> SendRenderedResult:
        if self._state.is_sent(target_date):
            return SendRenderedResult.ALREADY_SENT
        if _PLACEHOLDER_PATTERN.search(body):
            return SendRenderedResult.PLACEHOLDER_REMAINS

        self._mail.send(
            sender=self._sender,
            to=self._recipient,
            subject=subject,
            body=body,
        )
        self._state.mark_sent(target_date)
        return SendRenderedResult.SENT
