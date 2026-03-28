from __future__ import annotations

from datetime import datetime, timezone

from email_agent.db.mongo import MongoMemoryStore
from email_agent.graph.state import EmailAgentState
from email_agent.mailbox import MailboxClient
from email_agent.models import (
    ClassificationResult,
    DraftReply,
    EmailMessage,
    HumanDecision,
    NormalizedEmail,
)


def make_human_review_node(mailbox: MailboxClient, memory_store: MongoMemoryStore):
    def human_review(state: EmailAgentState) -> EmailAgentState:
        email = EmailMessage.model_validate(state["email"])
        normalized_email = NormalizedEmail.model_validate(state["normalized_email"])
        classification = ClassificationResult.model_validate(state["classification"])
        draft = None
        if "draft" in state:
            draft = DraftReply.model_validate(state["draft"])

        review_item = mailbox.flag_for_human_review(
            original_email=email,
            reason=classification.reason,
            metadata={
                "draft": draft.model_dump(mode="json") if draft else None,
                "classification": classification.model_dump(mode="json"),
                "normalized_email": normalized_email.model_dump(mode="json"),
                "state_snapshot": {
                    "email": state["email"],
                    "email_id": state.get("email_id"),
                    "thread_id": state.get("thread_id"),
                    "normalized_email": state.get("normalized_email"),
                    "thread_messages": state.get("thread_messages", []),
                    "thread_summary": state.get("thread_summary"),
                    "memory": state.get("memory", {}),
                    "retrieved_context": state.get("retrieved_context", {}),
                    "classification": state.get("classification"),
                    "draft": state.get("draft"),
                    "safety_result": state.get("safety_result"),
                },
            },
        )
        memory_store.create_review_task(
            normalized_email=normalized_email,
            classification=classification,
            draft=draft,
        )
        decision = HumanDecision(
            decision="pending",
            comments="Queued for human review.",
            reviewed_at=datetime.now(timezone.utc),
        )
        return {
            "human_decision": decision.model_dump(mode="json"),
            "delivery_status": "pending_human_review",
            "status": "pending_human",
            "final_action": "human_review",
            "review_id": review_item.get("review_id"),
        }

    return human_review
