"""Telegram Bot API への HTTP クライアント。getUpdates / sendMessage を提供。"""
from __future__ import annotations

from typing import Any, List, Optional

import httpx

from domain.exceptions import AuthFailureError, TelegramSecretaryError
from domain.models import OutboundMessage, TelegramUpdate
from domain.offset import UpdateOffset


class TelegramApiGateway:
    """Telegram Bot API の getUpdates / sendMessage を呼ぶ実装。

    - 5xx は retry_count 回まで自動再試行
    - 401 は AuthFailureError（exit 3 系の決定打）
    - その他 4xx は TelegramSecretaryError
    - ネットワークエラーは retry 後に TelegramSecretaryError
    """

    DEFAULT_BASE_URL = "https://api.telegram.org"
    DEFAULT_USER_AGENT = "TelegramSecretary/0.1 (+Weave)"

    def __init__(
        self,
        bot_token: str,
        base_url: str = DEFAULT_BASE_URL,
        client: Optional[httpx.Client] = None,
        retry_count: int = 2,
        request_timeout: float = 40.0,
    ) -> None:
        self._bot_token = bot_token
        self._base_url = base_url.rstrip("/")
        self._retry_count = retry_count
        self._request_timeout = request_timeout
        if client is None:
            client = httpx.Client(
                timeout=request_timeout,
                headers={"User-Agent": self.DEFAULT_USER_AGENT},
            )
        self._client = client

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "TelegramApiGateway":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    def fetch(self, offset: UpdateOffset, timeout_seconds: int = 30) -> List[TelegramUpdate]:
        url = f"{self._base_url}/bot{self._bot_token}/getUpdates"
        params = {"offset": offset.value, "timeout": timeout_seconds}
        response = self._request_with_retry("GET", url, params=params)
        data = response.json()
        if not data.get("ok"):
            raise TelegramSecretaryError(f"getUpdates failed: {data}")
        return [TelegramUpdate.from_api(u) for u in data.get("result", [])]

    def send(self, message: OutboundMessage) -> None:
        url = f"{self._base_url}/bot{self._bot_token}/sendMessage"
        payload: dict[str, Any] = {"chat_id": message.chat_id, "text": message.text}
        if message.reply_to_message_id is not None:
            payload["reply_to_message_id"] = message.reply_to_message_id
        response = self._request_with_retry("POST", url, json=payload)
        data = response.json()
        if not data.get("ok"):
            raise TelegramSecretaryError(f"sendMessage failed: {data}")

    def _request_with_retry(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        last_exc: Optional[Exception] = None
        for attempt in range(self._retry_count + 1):
            try:
                response = self._client.request(method, url, **kwargs)
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt < self._retry_count:
                    continue
                raise TelegramSecretaryError(f"network error after retries: {exc}") from exc

            if response.status_code == 401:
                raise AuthFailureError(f"401 Unauthorized: {response.text[:200]}")
            if response.status_code >= 500:
                last_exc = httpx.HTTPStatusError(
                    f"{response.status_code}", request=response.request, response=response
                )
                if attempt < self._retry_count:
                    continue
                raise TelegramSecretaryError(
                    f"server error after retries: {response.status_code}"
                )
            if response.status_code >= 400:
                raise TelegramSecretaryError(
                    f"client error: {response.status_code} {response.text[:200]}"
                )
            return response

        raise TelegramSecretaryError(f"unreachable, last_exc={last_exc}")
