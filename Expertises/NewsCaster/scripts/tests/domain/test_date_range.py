from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from domain.date_range import DateRangeJST
from domain.exceptions import ValidationError

JST = ZoneInfo("Asia/Tokyo")


class TestFromYesterday:
    def test_at_010_jst_returns_previous_day_00_to_2359(self):
        now = datetime(2026, 5, 12, 0, 10, 0, tzinfo=JST)
        r = DateRangeJST.from_yesterday(now)
        assert r.start_jst == datetime(2026, 5, 11, 0, 0, 0, tzinfo=JST)
        assert r.end_jst == datetime(
            2026, 5, 11, 23, 59, 59, 999999, tzinfo=JST
        )

    def test_at_noon_returns_previous_day_too(self):
        now = datetime(2026, 5, 12, 12, 0, 0, tzinfo=JST)
        r = DateRangeJST.from_yesterday(now)
        assert r.start_jst.date().isoformat() == "2026-05-11"
        assert r.end_jst.date().isoformat() == "2026-05-11"

    def test_month_boundary_handled(self):
        now = datetime(2026, 6, 1, 0, 10, 0, tzinfo=JST)
        r = DateRangeJST.from_yesterday(now)
        assert r.start_jst.date().isoformat() == "2026-05-31"

    def test_naive_datetime_rejected(self):
        with pytest.raises(ValidationError):
            DateRangeJST.from_yesterday(datetime(2026, 5, 12, 0, 10, 0))

    def test_utc_datetime_converted_to_jst_first(self):
        # 2026-05-11 15:10 UTC = 2026-05-12 00:10 JST → 前日は 5/11 JST
        now_utc = datetime(2026, 5, 11, 15, 10, 0, tzinfo=timezone.utc)
        r = DateRangeJST.from_yesterday(now_utc)
        assert r.start_jst.date().isoformat() == "2026-05-11"


class TestContains:
    def test_pubdate_gmt_2330_belongs_to_following_jst_day(self):
        # GMT 2026-05-11 23:30 = JST 2026-05-12 08:30
        # → 5/11 を対象にする range には含まれない
        # → 5/12 を対象にする range には含まれる
        pub = datetime(2026, 5, 11, 23, 30, 0, tzinfo=timezone.utc)

        range_5_11 = DateRangeJST.from_yesterday(
            datetime(2026, 5, 12, 0, 10, 0, tzinfo=JST)
        )
        range_5_12 = DateRangeJST.from_yesterday(
            datetime(2026, 5, 13, 0, 10, 0, tzinfo=JST)
        )

        assert range_5_11.contains(pub) is False
        assert range_5_12.contains(pub) is True

    def test_pubdate_gmt_at_jst_midnight_inclusive(self):
        # 2026-05-10 15:00 UTC = 2026-05-11 00:00 JST → 5/11 range の境界inclusive
        pub = datetime(2026, 5, 10, 15, 0, 0, tzinfo=timezone.utc)
        r = DateRangeJST.from_yesterday(
            datetime(2026, 5, 12, 0, 10, 0, tzinfo=JST)
        )
        assert r.contains(pub) is True

    def test_pubdate_just_before_jst_midnight_excluded(self):
        # 2026-05-10 14:59:59 UTC = 2026-05-10 23:59:59 JST → 5/11 range の外
        pub = datetime(2026, 5, 10, 14, 59, 59, tzinfo=timezone.utc)
        r = DateRangeJST.from_yesterday(
            datetime(2026, 5, 12, 0, 10, 0, tzinfo=JST)
        )
        assert r.contains(pub) is False

    def test_naive_datetime_in_contains_rejected(self):
        r = DateRangeJST.from_yesterday(
            datetime(2026, 5, 12, 0, 10, 0, tzinfo=JST)
        )
        with pytest.raises(ValidationError):
            r.contains(datetime(2026, 5, 11, 12, 0, 0))


class TestProperties:
    def test_target_date_isoformat(self):
        r = DateRangeJST.from_yesterday(
            datetime(2026, 5, 12, 0, 10, 0, tzinfo=JST)
        )
        assert r.target_date_iso() == "2026-05-11"
