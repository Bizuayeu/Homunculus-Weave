from __future__ import annotations

from typing import Protocol, runtime_checkable

from domain.models import NewsItem


@runtime_checkable
class RssGatewayPort(Protocol):
    def fetch_all(self) -> list[NewsItem]:
        """RSSフィードを取得し全itemをパースして返す。

        ネットワーク・パース失敗時は RssFetchError を raise。
        """
        ...


@runtime_checkable
class MailGatewayPort(Protocol):
    def send(self, *, sender: str, to: str, subject: str, body: str) -> None:
        """メールを送信する。失敗時は MailSendError / AuthError を raise。"""
        ...


@runtime_checkable
class StateStorePort(Protocol):
    def is_sent(self, target_date: str) -> bool:
        """target_date (YYYY-MM-DD) が送信済みか判定する。"""
        ...

    def mark_sent(self, target_date: str) -> None:
        """target_date を送信済みとして永続化する。"""
        ...
