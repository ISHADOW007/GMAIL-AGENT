from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Settings:
    openai_api_key: str
    openai_model: str
    email_backend: str
    auto_send: bool
    max_emails: int
    local_inbox_path: Path
    local_outbox_path: Path
    gmail_user_id: str
    gmail_credentials_path: Path
    gmail_token_path: Path
    gmail_open_browser: bool
    gmail_label_prefix: str
    imap_host: str | None
    imap_port: int
    imap_username: str | None
    imap_password: str | None
    smtp_host: str | None
    smtp_port: int
    smtp_username: str | None
    smtp_password: str | None
    default_from_address: str | None
    mongodb_uri: str | None
    mongodb_database: str


def load_settings() -> Settings:
    load_dotenv()

    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY is required.")

    return Settings(
        openai_api_key=openai_api_key,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        email_backend=os.getenv("EMAIL_BACKEND", "local").strip().lower(),
        auto_send=_as_bool(os.getenv("AUTO_SEND"), default=False),
        max_emails=int(os.getenv("MAX_EMAILS", "5")),
        local_inbox_path=Path(os.getenv("LOCAL_INBOX_PATH", "data/sample_inbox.json")),
        local_outbox_path=Path(os.getenv("LOCAL_OUTBOX_PATH", "data/outbox.json")),
        gmail_user_id=os.getenv("GMAIL_USER_ID", "me"),
        gmail_credentials_path=Path(
            os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json")
        ),
        gmail_token_path=Path(os.getenv("GMAIL_TOKEN_PATH", "data/gmail_token.json")),
        gmail_open_browser=_as_bool(os.getenv("GMAIL_OPEN_BROWSER"), default=False),
        gmail_label_prefix=os.getenv("GMAIL_LABEL_PREFIX", "AI").strip() or "AI",
        imap_host=os.getenv("IMAP_HOST"),
        imap_port=int(os.getenv("IMAP_PORT", "993")),
        imap_username=os.getenv("IMAP_USERNAME"),
        imap_password=os.getenv("IMAP_PASSWORD"),
        smtp_host=os.getenv("SMTP_HOST"),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_username=os.getenv("SMTP_USERNAME"),
        smtp_password=os.getenv("SMTP_PASSWORD"),
        default_from_address=os.getenv("DEFAULT_FROM_ADDRESS"),
        mongodb_uri=os.getenv("MONGODB_URI"),
        mongodb_database=os.getenv("MONGODB_DATABASE", "email_agent"),
    )
a