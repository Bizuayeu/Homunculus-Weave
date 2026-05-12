from __future__ import annotations

from domain.digest import DailyDigest
from usecases.ports import MailGatewayPort, StateStorePort


class SendDigestEmailUseCase:
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

    def execute(self, *, digest: DailyDigest) -> bool:
        if self._state.is_sent(digest.target_date):
            return False
        self._mail.send(
            sender=self._sender,
            to=self._recipient,
            subject=digest.formatted_subject,
            body=digest.formatted_body,
        )
        self._state.mark_sent(digest.target_date)
        return True
