from __future__ import annotations

from email_agent.graph.state import EmailAgentState
from email_agent.mailbox import MailboxClient
from email_agent.models import EmailMessage


def make_mark_processed_node(mailbox: MailboxClient):
    def mark_processed(state: EmailAgentState) -> EmailAgentState:
        email = EmailMessage.model_validate(state["email"])
        mailbox.mark_processed(
            email.id,
            outcome=state.get("delivery_status") or state.get("final_action"),
        )
        if state.get("status") not in {"sent", "draft_saved", "ignored", "pending_human"}:
            return {"status": "completed"}
        return {}

    return mark_processed
