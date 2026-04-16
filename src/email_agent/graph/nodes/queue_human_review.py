"""Node that creates or refreshes the dashboard review item before a pause."""
from __future__ import annotations

from datetime import datetime, timezone

from email_agent.db.mongo import MongoMemoryStore
from email_agent.graph.state import EmailAgentState
from email_agent.mailbox import MailboxClient
from email_agent.models import (
    ClassificationResult,
    DraftReply,
    EmailMessage,
    NormalizedEmail,
)
from email_agent.services.review_service import find_latest_review_item, update_review_item


def make_queue_human_review_node(
    mailbox: MailboxClient,
    memory_store: MongoMemoryStore,
):
    def queue_human_review(state: EmailAgentState) -> EmailAgentState:
        email = EmailMessage.model_validate(state["email"])
        normalized_email = NormalizedEmail.model_validate(state["normalized_email"])
        classification = ClassificationResult.model_validate(state["classification"])
        draft = DraftReply.model_validate(state["draft"]) if state.get("draft") else None

        checkpoint_thread_id = state.get("run_id") or state.get("email_id") or email.id
        review_item = None
        if state.get("review_id"):
            review_item = find_latest_review_item(review_id=state["review_id"])
        if review_item is None:
            review_item = find_latest_review_item(
                checkpoint_thread_id=checkpoint_thread_id,
                email_id=email.id,
                status="pending",
            )

        updates = {
            "email_id": email.id,
            "thread_id": email.thread_id,
            "from_address": email.from_address,
            "subject": email.subject,
            "reason": classification.reason,
            "status": "pending",
            "decision": "pending",
            "draft": draft.model_dump(mode="json") if draft else None,
            "classification": classification.model_dump(mode="json"),
            "normalized_email": normalized_email.model_dump(mode="json"),
            "checkpoint_thread_id": checkpoint_thread_id,
            "last_queued_at": datetime.now(timezone.utc).isoformat(),
        }

        if review_item is None:
            review_item = mailbox.flag_for_human_review(
                original_email=email,
                reason=classification.reason,
                metadata=updates,
            )
            memory_store.create_review_task(
                normalized_email=normalized_email,
                classification=classification,
                draft=draft,
                review_id=review_item.get("review_id"),
            )
        else:
            review_item = update_review_item(
                review_item["review_id"],
                updates=updates,
                memory_store=memory_store,
            )

        return {
            "review_id": review_item["review_id"],
            "delivery_status": "pending_human_review",
            "status": "pending_human",
            "final_action": "human_review",
        }

    return queue_human_review
