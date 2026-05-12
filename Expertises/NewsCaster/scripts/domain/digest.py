from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from domain.exceptions import ValidationError
from domain.models import NewsItem


@dataclass(frozen=True)
class DailyDigest:
    target_date: str
    items: tuple[NewsItem, ...]
    formatted_subject: str
    formatted_body: str

    def __post_init__(self) -> None:
        try:
            date.fromisoformat(self.target_date)
        except (TypeError, ValueError) as e:
            raise ValidationError(
                f"target_date must be ISO YYYY-MM-DD, got {self.target_date!r}"
            ) from e
        if not self.formatted_subject or not self.formatted_subject.strip():
            raise ValidationError("formatted_subject is required")
        if not self.formatted_body or not self.formatted_body.strip():
            raise ValidationError("formatted_body is required")

    @property
    def is_empty(self) -> bool:
        return len(self.items) == 0
