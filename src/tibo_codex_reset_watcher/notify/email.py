from __future__ import annotations

import smtplib
from email.message import EmailMessage

from tibo_codex_reset_watcher.models import ResetEvent
from tibo_codex_reset_watcher.notify.text import render_plain_text


class EmailNotifier:
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_addr: str,
        to_addr: str,
        use_tls: bool = True,
        use_ssl: bool = False,
        timezone: str = "Asia/Shanghai",
    ) -> None:
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.to_addr = to_addr
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.timezone = timezone

    def notify(self, event: ResetEvent) -> None:
        message = EmailMessage()
        message["From"] = self.from_addr
        message["To"] = self.to_addr
        message["Subject"] = f"Codex {event.event_type.value}: {event.severity.value}"
        message.set_content(render_plain_text(event, self.timezone))

        if self.use_ssl:
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=30) as smtp:
                smtp.login(self.username, self.password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as smtp:
                if self.use_tls:
                    smtp.starttls()
                smtp.login(self.username, self.password)
                smtp.send_message(message)
