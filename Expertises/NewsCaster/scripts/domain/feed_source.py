from __future__ import annotations

from dataclasses import dataclass

from domain.exceptions import ValidationError
from domain.feed_policy import FeedPolicy


@dataclass(frozen=True)
class FeedSource:
    name: str
    url: str
    policy: FeedPolicy

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValidationError("FeedSource.name is required")
        if not self.url or not self.url.strip():
            raise ValidationError("FeedSource.url is required")
        if not isinstance(self.policy, FeedPolicy):
            raise ValidationError(
                f"FeedSource.policy must be FeedPolicy, got {type(self.policy).__name__}"
            )
