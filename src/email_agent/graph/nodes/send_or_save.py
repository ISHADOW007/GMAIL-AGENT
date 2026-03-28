from __future__ import annotations

from email_agent.config import Settings
from email_agent.graph.state import EmailAgentState
from email_agent.mailbox import MailboxClient
from email_agent.models import ClassificationResult, DraftReply, EmailMessage, SafetyResult


def make_send_or_save_node(mailbox: MailboxClient, settings: Settings):
    def send_or_save(state: EmailAgentState) -> EmailAgentState:
        if state.get("final_action") == "ignore":
            return {
                "delivery_status": "ignored",
                "status": "ignored",
                "final_action": "ignore",
            }

        if "classification" in state:
            classification = ClassificationResult.model_validate(state["classification"])
            if classification.action == "ignore":
                return {
                    "delivery_status": "ignored",
                    "status": "ignored",
                    "final_action": "ignore",
                }

        email = EmailMessage.model_validate(state["email"])
        draft = DraftReply.model_validate(state["draft"])
        safety = SafetyResult.model_validate(state["safety_result"])

        if settings.auto_send and safety.safe_to_send:
            mailbox.send_email(email, draft)
            return {
                "delivery_status": "sent",
                "status": "sent",
                "final_action": "sent",
            }

        mailbox.save_draft(email, draft)
        return {
            "delivery_status": "draft_saved",
            "status": "draft_saved",
            "final_action": "draft_saved",
        }

    return send_or_save
