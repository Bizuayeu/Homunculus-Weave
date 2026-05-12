from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from domain.exceptions import ValidationError

JST = ZoneInfo("Asia/Tokyo")


@dataclass(frozen=True)
class DateRangeJST:
    start_jst: datetime
    end_jst: datetime

    def __post_init__(self) -> None:
        for name, val in (("start_jst", self.start_jst), ("end_jst", self.end_jst)):
            if not isinstance(val, datetime):
                raise ValidationError(f"{name} must be datetime")
            if val.tzinfo is None:
                raise ValidationError(f"{name} must be timezone-aware")
            off = val.utcoffset()
            if off is None or off.total_seconds() != 9 * 3600:
                raise ValidationError(f"{name} must be JST (+09:00)")
        if self.start_jst > self.end_jst:
            raise ValidationError("start_jst must be <= end_jst")

    @classmethod
    def from_yesterday(cls, now: datetime) -> "DateRangeJST":
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValidationError("now must be timezone-aware datetime")
        now_jst = now.astimezone(JST)
        yesterday = (now_jst - timedelta(days=1)).date()
        start = datetime(
            yesterday.year, yesterday.month, yesterday.day, 0, 0, 0, tzinfo=JST
        )
        end = datetime(
            yesterday.year,
            yesterday.month,
            yesterday.day,
            23,
            59,
            59,
            999999,
            tzinfo=JST,
        )
        return cls(start_jst=start, end_jst=end)

    def contains(self, dt: datetime) -> bool:
        if not isinstance(dt, datetime) or dt.tzinfo is None:
            raise ValidationError("dt must be timezone-aware datetime")
        dt_jst = dt.astimezone(JST)
        return self.start_jst <= dt_jst <= self.end_jst

    def target_date_iso(self) -> str:
        return self.start_jst.date().isoformat()
