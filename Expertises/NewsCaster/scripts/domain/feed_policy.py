from __future__ import annotations

from enum import Enum


class FeedPolicy(str, Enum):
    PASSTHROUGH = "passthrough"
    WEAVE_COMPACT = "weave_compact"

    @classmethod
    def from_string(cls, value: str) -> "FeedPolicy":
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"unknown FeedPolicy: {value!r}")
