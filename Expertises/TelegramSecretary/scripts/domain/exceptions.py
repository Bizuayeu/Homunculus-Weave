"""TelegramSecretary domain exceptions."""


class TelegramSecretaryError(Exception):
    """Base exception."""


class InvalidOffsetError(TelegramSecretaryError):
    """update offset が不正値（負数など）。"""


class LeaseConflictError(TelegramSecretaryError):
    """他セッションが lease を保持しており取得不可。"""


class AuthFailureError(TelegramSecretaryError):
    """Telegram bot token 認証失敗（401）。"""
