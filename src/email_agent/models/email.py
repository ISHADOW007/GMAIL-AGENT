from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class EmailMessage(BaseModel):
    id: str
    from_address: str
    to_address: str
    subject: str
    body: str
    received_at: datetime
    is_unread: bool = True
    thread_id: str | None = None
    message_id: str | None = None


class NormalizedEmail(BaseModel):
    email_id: str
    thread_id: str
    sender: str
    subject: str
    clean_body: str
    summary: str | None = None
    has_attachments: bool = False
    detected_language: str = "en"
