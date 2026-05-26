"""Telegram Bot API への HTTP クライアント。getUpdates / sendMessage を提供。"""
from __future__ import annotations

import time
from typing import Any, List, Optional

import httpx

from domain.exceptions import AuthFailureError, TelegramSecretaryError
from domain.models import OutboundMessage, TelegramUpdate
from domain.offset import UpdateOffset


class TelegramApiGateway:
    """Telegram Bot API の getUpdates / sendMessage を呼ぶ実装。

    - 5xx / 429 は retry_count 回まで自動再試行
    - 429 は `Retry-After` ヘッダを尊重して sleep（最大 `max_retry_after_seconds` 秒）
    - 401 は AuthFailureError（exit 3 系の決定打）
    - その他 4xx は TelegramSecretaryError
    - ネットワークエラーは retry 後に TelegramSecretaryError
    """

    DEFAULT_BASE_URL = "https://api.telegram.org"
    DEFAULT_USER_AGENT = "TelegramSecretary/0.1 (+Weave)"
    DEFAULT_MAX_RETRY_AFTER_SECONDS = 60

    def __init__(
        self,
        bot_token: str,
        base_url: str = DEFAULT_BASE_URL,
        client: Optional[httpx.Client] = None,
        retry_count: int = 2,
        request_timeout: float = 40.0,
        max_retry_after_seconds: int = DEFAULT_MAX_RETRY_AFTER_SECONDS,
    ) -> None:
        self._bot_token = bot_token
        self._base_url = base_url.rstrip("/")
        self._retry_count = retry_count
        self._request_timeout = request_timeout
        self._max_retry_after_seconds = max_retry_after_seconds
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

    def get_file(self, file_id: str) -> str:
        """Telegram /getFile で file_id から file_path を取得（Stage 6.3）。

        Bot API の File オブジェクトは `file_path` を含む（例: `photos/file_42.jpg`）。
        この相対パスを `/file/bot<TOKEN>/<file_path>` の組み立てに使う。
        """
        url = f"{self._base_url}/bot{self._bot_token}/getFile"
        params = {"file_id": file_id}
        response = self._request_with_retry("GET", url, params=params)
        data = response.json()
        if not data.get("ok"):
            raise TelegramSecretaryError(f"getFile failed: {data}")
        result = data.get("result") or {}
        file_path = result.get("file_path")
        if not file_path:
            raise TelegramSecretaryError(
                f"getFile response missing file_path: {data}"
            )
        return str(file_path)

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
            if response.status_code == 429:
                # Telegram のレート制限。Retry-After ヘッダを尊重して sleep してから再試行
                last_exc = httpx.HTTPStatusError(
                    "429 Too Many Requests",
                    request=response.request,
                    response=response,
                )
                if attempt < self._retry_count:
                    self._sleep_for_retry_after(response.headers.get("Retry-After"))
                    continue
                raise TelegramSecretaryError(
                    f"rate limited after retries (429), Retry-After={response.headers.get('Retry-After')!r}"
                )
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

    def _sleep_for_retry_after(self, header_value: Optional[str]) -> None:
        """`Retry-After` ヘッダの秒数だけ sleep（上限 `max_retry_after_seconds`）。

        - ヘッダ無しまたは parse 失敗時は sleep しない（即時 retry）
        - 上限を超える値は上限に丸める（DoS 自損防止）
        """
        if not header_value:
            return
        try:
            seconds = int(header_value)
        except (ValueError, TypeError):
            return
        if seconds <= 0:
            return
        time.sleep(min(seconds, self._max_retry_after_seconds))
