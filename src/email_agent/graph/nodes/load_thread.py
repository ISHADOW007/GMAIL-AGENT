"""Node that fetches prior thread messages from the active mailbox backend."""
from __future__ import annotations

from email_agent.graph.state import EmailAgentState
from email_agent.mailbox import MailboxClient
from email_agent.models import EmailMessage
from email_agent.services.thread_service import (
    serialize_thread_messages,
    summarize_thread_messages,
)


def make_load_thread_node(mailbox: MailboxClient):
    def load_thread(state: EmailAgentState) -> EmailAgentState:
        email = EmailMessage.model_validate(state["email"])
        thread_messages = mailbox.fetch_thread_messages(email.thread_id, email.id)
        return {
            "thread_messages": serialize_thread_messages(thread_messages),
            "thread_summary": summarize_thread_messages(thread_messages),
        }

    return load_thread

