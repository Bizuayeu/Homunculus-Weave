from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

DEFAULT_RSS_URL = "https://news.nullevi.app/rss"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_STATE_DIR = Path(__file__).resolve().parents[2] / "state"


@dataclass(frozen=True)
class DigestConfig:
    sender: str
    recipient: str
    oauth_token_path: Path | None
    oauth_token_json: str | None
    oauth_client_secret_path: Path | None
    rss_url: str
    user_agent: str
    state_dir: Path
    retry_count: int

    _instance: ClassVar["DigestConfig | None"] = None

    @classmethod
    def load(cls, env_file: Path | None = None) -> "DigestConfig":
        if cls._instance is not None:
            return cls._instance

        if env_file is None:
            env_file = Path.cwd() / ".env"
        if env_file.exists():
            cls._load_env_file(env_file)

        retry_raw = os.environ.get("NEWSCASTER_MAIL_RETRY_COUNT", "3")
        try:
            retry_count = int(retry_raw)
        except ValueError:
            retry_count = 3

        token_raw = os.environ.get("NEWSCASTER_OAUTH_TOKEN_PATH", "").strip()
        token_json_raw = os.environ.get("NEWSCASTER_OAUTH_TOKEN_JSON", "").strip()
        client_secret_raw = os.environ.get(
            "NEWSCASTER_OAUTH_CLIENT_SECRET_PATH", ""
        ).strip()
        state_dir_raw = os.environ.get("NEWSCASTER_STATE_DIR", "").strip()

        cls._instance = cls(
            sender=os.environ.get("NEWSCASTER_SENDER_EMAIL", ""),
            recipient=os.environ.get("NEWSCASTER_RECIPIENT_EMAIL", ""),
            oauth_token_path=Path(token_raw) if token_raw else None,
            oauth_token_json=token_json_raw or None,
            oauth_client_secret_path=Path(client_secret_raw)
            if client_secret_raw
            else None,
            rss_url=os.environ.get("NEWSCASTER_RSS_URL", "").strip() or DEFAULT_RSS_URL,
            user_agent=os.environ.get("NEWSCASTER_USER_AGENT", "").strip()
            or DEFAULT_USER_AGENT,
            state_dir=Path(state_dir_raw) if state_dir_raw else DEFAULT_STATE_DIR,
            retry_count=retry_count,
        )
        return cls._instance

    @staticmethod
    def _load_env_file(path: Path) -> None:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.sender:
            errors.append("NEWSCASTER_SENDER_EMAIL is required")
        if not self.recipient:
            errors.append("NEWSCASTER_RECIPIENT_EMAIL is required")
        if self.oauth_token_path is None and self.oauth_token_json is None:
            errors.append(
                "NEWSCASTER_OAUTH_TOKEN_PATH or NEWSCASTER_OAUTH_TOKEN_JSON is required"
            )
        return errors

    @classmethod
    def reset(cls) -> None:
        cls._instance = None
