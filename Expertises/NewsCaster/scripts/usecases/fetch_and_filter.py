from __future__ import annotations

import sys
from typing import Sequence

from domain.date_range import DateRangeJST
from domain.exceptions import RssFetchError
from domain.feed_source import FeedSource
from domain.models import NewsItem
from usecases.ports import RssGatewayPort


class FetchAndFilterUseCase:
    """複数の FeedSource を回して全件統合、前日範囲で絞り、時刻降順で返す。

    1フィードの失敗は stderr ログ後 skip。全フィード失敗時のみ最初のエラーを送出。
    """

    def __init__(
        self,
        gateways: Sequence[tuple[FeedSource, RssGatewayPort]],
    ) -> None:
        self._gateways: list[tuple[FeedSource, RssGatewayPort]] = list(gateways)
        if not self._gateways:
            raise ValueError("FetchAndFilterUseCase requires at least one gateway")

    def execute(self, *, date_range: DateRangeJST) -> list[NewsItem]:
        all_items: list[NewsItem] = []
        errors: list[RssFetchError] = []

        for fs, gw in self._gateways:
            try:
                fetched = gw.fetch_all()
            except RssFetchError as e:
                errors.append(e)
                print(
                    f"[warn] feed {fs.name!r} fetch failed: {e}",
                    file=sys.stderr,
                )
                continue
            all_items.extend(fetched)

        if errors and len(errors) == len(self._gateways):
            raise errors[0]

        filtered = [
            item for item in all_items if date_range.contains(item.pub_date_jst)
        ]
        filtered.sort(key=lambda i: i.pub_date_jst, reverse=True)
        return filtered
