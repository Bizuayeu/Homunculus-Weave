from __future__ import annotations

from domain.date_range import DateRangeJST
from domain.models import NewsItem
from usecases.ports import RssGatewayPort


class FetchAndFilterUseCase:
    def __init__(self, rss_gateway: RssGatewayPort) -> None:
        self._rss = rss_gateway

    def execute(self, *, date_range: DateRangeJST) -> list[NewsItem]:
        all_items = self._rss.fetch_all()
        filtered = [item for item in all_items if date_range.contains(item.pub_date_jst)]
        filtered.sort(key=lambda i: i.pub_date_jst, reverse=True)
        return filtered
