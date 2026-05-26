from __future__ import annotations

import pytest

from domain.feed_policy import FeedPolicy


class TestFeedPolicy:
    def test_has_passthrough_and_weave_compact(self):
        assert FeedPolicy.PASSTHROUGH.value == "passthrough"
        assert FeedPolicy.WEAVE_COMPACT.value == "weave_compact"

    def test_from_string_passthrough(self):
        assert FeedPolicy.from_string("passthrough") is FeedPolicy.PASSTHROUGH

    def test_from_string_weave_compact(self):
        assert FeedPolicy.from_string("weave_compact") is FeedPolicy.WEAVE_COMPACT

    def test_from_string_unknown_raises(self):
        with pytest.raises(ValueError):
            FeedPolicy.from_string("unknown_policy")

    def test_only_two_members(self):
        assert {m.value for m in FeedPolicy} == {"passthrough", "weave_compact"}
