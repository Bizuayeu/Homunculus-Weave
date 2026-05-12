from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from domain.date_range import DateRangeJST
from domain.digest import DailyDigest
from usecases.fetch_and_filter import FetchAndFilterUseCase
from usecases.format_digest import FormatDigestUseCase
from usecases.ports import MailGatewayPort, RssGatewayPort, StateStorePort
from usecases.send_digest_email import SendDigestEmailUseCase


class RunResult(str, Enum):
    SENT = "sent"
    NO_ITEMS = "no_items"
    ALREADY_SENT = "already_sent"
    DRY_RUN = "dry_run"


@dataclass(frozen=True)
class RunOutcome:
    result: RunResult
    target_date: str
    digest: DailyDigest | None = None


class RunDailyDigestUseCase:
    def __init__(
        self,
        *,
        rss_gateway: RssGatewayPort,
        mail_gateway: MailGatewayPort,
        state_store: StateStorePort,
        sender: str,
        recipient: str,
    ) -> None:
        self._fetch_filter = FetchAndFilterUseCase(rss_gateway=rss_gateway)
        self._format = FormatDigestUseCase()
        self._send = SendDigestEmailUseCase(
            mail_gateway=mail_gateway,
            state_store=state_store,
            sender=sender,
            recipient=recipient,
        )
        self._state = state_store

    def execute(
        self, *, now: datetime, dry_run: bool = False
    ) -> RunOutcome:
        date_range = DateRangeJST.from_yesterday(now)
        target_date = date_range.target_date_iso()

        if self._state.is_sent(target_date) and not dry_run:
            return RunOutcome(RunResult.ALREADY_SENT, target_date)

        items = self._fetch_filter.execute(date_range=date_range)
        if not items:
            return RunOutcome(RunResult.NO_ITEMS, target_date)

        digest = self._format.execute(target_date=target_date, items=items)

        if dry_run:
            return RunOutcome(RunResult.DRY_RUN, target_date, digest=digest)

        sent = self._send.execute(digest=digest)
        result = RunResult.SENT if sent else RunResult.ALREADY_SENT
        return RunOutcome(result, target_date, digest=digest)
