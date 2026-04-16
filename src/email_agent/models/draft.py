"""Pydantic models for generated email draft payloads and outbox records."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DraftReply(BaseModel):
    subject: str
    body: str
    version: int = 1


class OutboxMessage(BaseModel):
    email_id: str
    action: str
    to_address: str
    subject: str
    body: str
    created_at: datetime

