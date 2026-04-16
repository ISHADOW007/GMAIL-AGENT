"""Node that converts the raw inbound email into a cleaner normalized representation."""
from __future__ import annotations

from email_agent.graph.state import EmailAgentState
from email_agent.models import EmailMessage, NormalizedEmail


def _thread_id_for(email: EmailMessage) -> str:
    return email.thread_id or email.id


def _summarize(body: str, limit: int = 180) -> str:
    compact = " ".join(body.split())
    return compact[:limit]


def make_normalize_email_node():
    def normalize_email(state: EmailAgentState) -> EmailAgentState:
        email = EmailMessage.model_validate(state["email"])
        normalized = NormalizedEmail(
            email_id=email.id,
            thread_id=_thread_id_for(email),
            sender=email.from_address,
            subject=email.subject.strip() or "(No subject)",
            clean_body=email.body.strip(),
            summary=_summarize(email.body),
            has_attachments=False,
            detected_language="en",
        )
        return {
            "email_id": email.id,
            "thread_id": normalized.thread_id,
            "normalized_email": normalized.model_dump(),
            "status": "new",
        }

    return normalize_email

