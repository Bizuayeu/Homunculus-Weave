class NewsCasterError(Exception):
    pass


class ValidationError(NewsCasterError):
    pass


class AuthError(NewsCasterError):
    pass


class MailSendError(NewsCasterError):
    pass


class RssFetchError(NewsCasterError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        final_url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.final_url = final_url
