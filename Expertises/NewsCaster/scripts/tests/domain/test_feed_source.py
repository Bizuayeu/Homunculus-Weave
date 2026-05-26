from __future__ import annotations

import pytest

from domain.exceptions import ValidationError
from domain.feed_policy import FeedPolicy
from domain.feed_source import FeedSource


class TestFeedSource:
    def test_constructs_with_name_url_policy(self):
        fs = FeedSource(
            name="ナルエビちゃんニュース",
            url="https://news.nullevi.app/rss",
            policy=FeedPolicy.PASSTHROUGH,
        )
        assert fs.name == "ナルエビちゃんニュース"
        assert fs.url == "https://news.nullevi.app/rss"
        assert fs.policy is FeedPolicy.PASSTHROUGH

    def test_rejects_empty_name(self):
        with pytest.raises(ValidationError):
            FeedSource(
                name="",
                url="https://news.nullevi.app/rss",
                policy=FeedPolicy.PASSTHROUGH,
            )

    def test_rejects_whitespace_only_name(self):
        with pytest.raises(ValidationError):
            FeedSource(
                name="   ",
                url="https://news.nullevi.app/rss",
                policy=FeedPolicy.PASSTHROUGH,
            )

    def test_rejects_empty_url(self):
        with pytest.raises(ValidationError):
            FeedSource(
                name="X",
                url="",
                policy=FeedPolicy.PASSTHROUGH,
            )

    def test_rejects_whitespace_only_url(self):
        with pytest.raises(ValidationError):
            FeedSource(
                name="X",
                url="   ",
                policy=FeedPolicy.PASSTHROUGH,
            )

    def test_frozen_immutable(self):
        fs = FeedSource(
            name="X",
            url="https://x.example/",
            policy=FeedPolicy.WEAVE_COMPACT,
        )
        with pytest.raises(Exception):
            fs.name = "mutated"  # type: ignore[misc]

    def test_equality_by_value(self):
        a = FeedSource("X", "https://x/", FeedPolicy.PASSTHROUGH)
        b = FeedSource("X", "https://x/", FeedPolicy.PASSTHROUGH)
        c = FeedSource("X", "https://x/", FeedPolicy.WEAVE_COMPACT)
        assert a == b
        assert a != c
