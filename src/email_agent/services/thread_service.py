"""Helpers that compact and summarize mailbox thread history for prompting."""
from __future__ import annotations

from email_agent.models import EmailMessage


def _compact_text(value: str, limit: int = 180) -> str:
    compact = " ".join(value.split())
    return compact[:limit]


def serialize_thread_messages(
    messages: list[EmailMessage],
    limit: int = 5,
) -> list[dict[str, str]]:
    recent_messages = messages[-limit:]
    return [
        {
            "email_id": message.id,
            "from_address": message.from_address,
            "subject": message.subject,
            "received_at": message.received_at.isoformat(),
            "summary": _compact_text(message.body),
        }
        for message in recent_messages
    ]


def summarize_thread_messages(
    messages: list[EmailMessage],
    limit: int = 3,
) -> str | None:
    serialized_messages = serialize_thread_messages(messages, limit=limit)
    if not serialized_messages:
        return None
    return "\n".join(
        f"{message['from_address']}: {message['summary']}"
        for message in serialized_messages
    )

