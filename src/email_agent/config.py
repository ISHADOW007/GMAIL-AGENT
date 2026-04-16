"""Environment-backed settings loader for the Gmail-only agent runtime."""
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
    openai_embedding_model: str
    openai_embedding_dimensions: int
    email_backend: str
    auto_send: bool
    max_emails: int
    gmail_user_id: str
    gmail_credentials_path: Path
    gmail_token_path: Path
    gmail_open_browser: bool
    gmail_label_prefix: str
    default_from_address: str | None
    mongodb_uri: str | None
    mongodb_database: str
    mongodb_store_collection: str
    mongodb_memory_namespace: str


def load_settings() -> Settings:
    load_dotenv()

    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY is required.")

    configured_backend = os.getenv("EMAIL_BACKEND", "gmail").strip().lower()
    if configured_backend not in {"", "gmail"}:
        raise ValueError("This codebase is now Gmail-only. Set EMAIL_BACKEND=gmail or remove it.")

    return Settings(
        openai_api_key=openai_api_key,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        openai_embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        openai_embedding_dimensions=int(os.getenv("OPENAI_EMBEDDING_DIMENSIONS", "1536")),
        email_backend="gmail",
        auto_send=_as_bool(os.getenv("AUTO_SEND"), default=False),
        max_emails=int(os.getenv("MAX_EMAILS", "5")),
        gmail_user_id=os.getenv("GMAIL_USER_ID", "me"),
        gmail_credentials_path=Path(
            os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json")
        ),
        gmail_token_path=Path(os.getenv("GMAIL_TOKEN_PATH", "data/gmail_token.json")),
        gmail_open_browser=_as_bool(os.getenv("GMAIL_OPEN_BROWSER"), default=False),
        gmail_label_prefix=os.getenv("GMAIL_LABEL_PREFIX", "AI").strip() or "AI",
        default_from_address=os.getenv("DEFAULT_FROM_ADDRESS"),
        mongodb_uri=os.getenv("MONGODB_URI"),
        mongodb_database=os.getenv("MONGODB_DATABASE", "email_agent"),
        mongodb_store_collection=os.getenv("MONGODB_STORE_COLLECTION", "long_term_memory"),
        mongodb_memory_namespace=os.getenv("MONGODB_MEMORY_NAMESPACE", "email_agent"),
    )
