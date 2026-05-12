from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any
from zoneinfo import ZoneInfo

from domain.exceptions import ValidationError

JST = ZoneInfo("Asia/Tokyo")


@dataclass(frozen=True)
class NewsItem:
    title: str
    link: str
    guid: str
    pub_date_jst: datetime
    description: str
    categories: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.title or not self.title.strip():
            raise ValidationError("title is required")
        if not self.link or not self.link.strip():
            raise ValidationError("link is required")
        if not self.guid or not self.guid.strip():
            raise ValidationError("guid is required")
        if not isinstance(self.pub_date_jst, datetime):
            raise ValidationError("pub_date_jst must be datetime")
        if self.pub_date_jst.tzinfo is None:
            raise ValidationError("pub_date_jst must be timezone-aware")
        offset = self.pub_date_jst.utcoffset()
        if offset is None or offset.total_seconds() != 9 * 3600:
            raise ValidationError("pub_date_jst must be in JST (+09:00)")

    @classmethod
    def from_rss_dict(cls, d: dict[str, Any]) -> "NewsItem":
        title = (d.get("title") or "").strip()
        link = (d.get("link") or "").strip()
        guid = (d.get("guid") or link).strip()
        pub_date_raw = d.get("pubDate") or ""
        description = (d.get("description") or "").strip()
        category_raw = (d.get("category") or "").strip()

        try:
            pub_aware = parsedate_to_datetime(pub_date_raw)
        except (TypeError, ValueError) as e:
            raise ValidationError(f"invalid pubDate: {pub_date_raw!r}") from e
        if pub_aware is None or not isinstance(pub_aware, datetime):
            raise ValidationError(f"invalid pubDate: {pub_date_raw!r}")
        if pub_aware.tzinfo is None:
            raise ValidationError(f"pubDate missing timezone: {pub_date_raw!r}")
        pub_jst = pub_aware.astimezone(JST)

        if category_raw:
            categories = tuple(
                part.strip() for part in category_raw.split(",") if part.strip()
            )
        else:
            categories = ()

        return cls(
            title=title,
            link=link,
            guid=guid,
            pub_date_jst=pub_jst,
            description=description,
            categories=categories,
        )
