from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

STATE_FILENAME = "sent_dates.json"
RETENTION_DAYS = 90


class JsonStateStore:
    def __init__(self, *, state_dir: Path) -> None:
        self._state_file = state_dir / STATE_FILENAME

    def is_sent(self, target_date: str) -> bool:
        return target_date in self._load()

    def mark_sent(self, target_date: str) -> None:
        sent = self._load()
        sent.add(target_date)
        sent = self._prune(sent)
        self._write(sent)

    def _load(self) -> set[str]:
        if not self._state_file.exists():
            return set()
        try:
            raw = json.loads(self._state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return set()
        return set(raw.get("sent", []))

    def _write(self, sent: set[str]) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {"sent": sorted(sent)}
        self._state_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _prune(sent: set[str]) -> set[str]:
        threshold = date.today() - timedelta(days=RETENTION_DAYS)
        kept: set[str] = set()
        for d_str in sent:
            try:
                d = date.fromisoformat(d_str)
            except ValueError:
                continue
            if d >= threshold:
                kept.add(d_str)
        return kept
