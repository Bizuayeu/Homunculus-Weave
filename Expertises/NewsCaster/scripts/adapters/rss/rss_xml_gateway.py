from __future__ import annotations

import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from typing import Callable

from domain.exceptions import RssFetchError, ValidationError
from domain.models import NewsItem

DEFAULT_TIMEOUT_SEC = 30


class RssXmlGateway:
    def __init__(
        self,
        *,
        rss_url: str,
        user_agent: str,
        timeout: int = DEFAULT_TIMEOUT_SEC,
        time_provider: Callable[[], float] | None = None,
    ) -> None:
        self._rss_url = rss_url
        self._user_agent = user_agent
        self._timeout = timeout
        self._time_provider = time_provider or time.time

    def fetch_all(self) -> list[NewsItem]:
        xml_bytes = self._fetch_xml()
        return self._parse(xml_bytes)

    def _build_cache_busted_url(self) -> str:
        epoch_seconds = int(self._time_provider())
        separator = "&" if "?" in self._rss_url else "?"
        return f"{self._rss_url}{separator}_={epoch_seconds}"

    def _build_request_headers(self) -> dict[str, str]:
        return {
            "User-Agent": self._user_agent,
            "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
            "Cache-Control": "no-cache, no-store, max-age=0",
            "Pragma": "no-cache",
        }

    def _fetch_xml(self) -> bytes:
        url = self._build_cache_busted_url()
        req = urllib.request.Request(url, headers=self._build_request_headers())
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            raise RssFetchError(
                f"HTTP error fetching {self._rss_url}: {e.code}",
                status_code=e.code,
                final_url=url,
            ) from e
        except urllib.error.URLError as e:
            raise RssFetchError(
                f"URL error fetching {self._rss_url}: {e.reason}",
                status_code=None,
                final_url=url,
            ) from e

    def _parse(self, xml_bytes: bytes) -> list[NewsItem]:
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as e:
            raise RssFetchError(f"malformed RSS XML: {e}") from e

        channel = root.find("channel")
        if channel is None:
            raise RssFetchError("RSS missing <channel> element")

        items: list[NewsItem] = []
        for item_el in channel.findall("item"):
            d = {
                "title": _text(item_el, "title"),
                "link": _text(item_el, "link"),
                "guid": _text(item_el, "guid"),
                "pubDate": _text(item_el, "pubDate"),
                "description": _text(item_el, "description"),
                "category": _text(item_el, "category"),
            }
            try:
                items.append(NewsItem.from_rss_dict(d))
            except ValidationError:
                # 個別 item の不正は黙ってスキップ（フィード全体は維持）
                continue
        return items


def _text(parent: ET.Element, tag: str) -> str:
    el = parent.find(tag)
    if el is None or el.text is None:
        return ""
    return el.text
