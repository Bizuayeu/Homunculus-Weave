from __future__ import annotations

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate


def build_mime(*, sender: str, to: str, subject: str, body: str) -> MIMEMultipart:
    mime = MIMEMultipart("mixed")
    mime["From"] = sender
    mime["To"] = to
    mime["Subject"] = subject
    mime["Date"] = formatdate(localtime=True)
    mime.attach(MIMEText(body, "plain", "utf-8"))
    return mime
