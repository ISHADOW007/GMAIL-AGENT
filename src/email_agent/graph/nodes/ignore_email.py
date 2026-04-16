"""Node for emails that should be ignored rather than answered."""
from __future__ import annotations

from email_agent.graph.state import EmailAgentState


def make_ignore_email_node():
    def ignore_email(_: EmailAgentState) -> EmailAgentState:
        return {
            "delivery_status": "ignored",
            "final_action": "ignore",
            "status": "ignored",
        }

    return ignore_email

