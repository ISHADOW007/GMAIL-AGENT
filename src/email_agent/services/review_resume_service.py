from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from langchain_openai import ChatOpenAI

from email_agent.config import load_settings
from email_agent.db.mongo import MongoMemoryStore
from email_agent.graph.nodes.mark_processed import make_mark_processed_node
from email_agent.graph.nodes.revise_reply import make_revise_reply_node
from email_agent.graph.nodes.send_or_save import make_send_or_save_node
from email_agent.graph.nodes.update_memory import make_update_memory_node
from email_agent.mailbox import build_mailbox_client
from email_agent.models import HumanDecision
from email_agent.services.review_service import (
    apply_review_decision,
    get_review_item,
    update_review_item,
)


def _build_runtime():
    settings = load_settings()
    mailbox = build_mailbox_client(settings)
    memory_store = MongoMemoryStore.from_settings(settings)
    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0,
    )
    return settings, mailbox, memory_store, llm


def _restore_review_state(review_item: dict[str, Any]) -> dict[str, Any] | None:
    snapshot = review_item.get("state_snapshot")
    if not snapshot:
        return None

    state = dict(snapshot)
    if review_item.get("draft"):
        state["draft"] = review_item["draft"]
    state["review_id"] = review_item["review_id"]
    return state


def _human_decision_payload(decision: str, comments: str | None, reviewer: str | None) -> dict[str, Any]:
    return HumanDecision(
        decision=decision,
        comments=comments,
        reviewer=reviewer or "dashboard",
        reviewed_at=datetime.now(timezone.utc),
    ).model_dump(mode="json")


def _finalize_review_state(state: dict[str, Any], mailbox: Any, settings: Any, memory_store: MongoMemoryStore) -> dict[str, Any]:
    if "draft" in state and state.get("final_action") != "ignore":
        send_or_save = make_send_or_save_node(mailbox, settings)
        state.update(send_or_save(state))

    update_memory = make_update_memory_node(memory_store)
    state.update(update_memory(state))

    mark_processed = make_mark_processed_node(mailbox)
    state.update(mark_processed(state))
    return state


def approve_review(
    review_id: str,
    *,
    comments: str | None = None,
    reviewer: str | None = None,
) -> dict[str, Any]:
    review_item = get_review_item(review_id)
    state = _restore_review_state(review_item)
    settings, mailbox, memory_store, _ = _build_runtime()

    if state is None:
        return apply_review_decision(
            review_id,
            decision="approve",
            comments=comments,
            reviewer=reviewer,
            memory_store=memory_store,
            extra_updates={
                "resumed": False,
                "resume_note": "Legacy review item had no saved graph state to resume.",
                "review_history": [
                    *review_item.get("review_history", []),
                    {
                        "decision": "approve",
                        "comments": comments,
                        "reviewer": reviewer or "dashboard",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    },
                ],
            },
        )

    state["human_decision"] = _human_decision_payload("approve", comments, reviewer)
    if "draft" not in state:
        state.update(
            {
                "delivery_status": "approved_without_delivery",
                "status": "approved",
                "final_action": "approved",
            }
        )

    _finalize_review_state(state, mailbox, settings, memory_store)
    return apply_review_decision(
        review_id,
        decision="approve",
        comments=comments,
        reviewer=reviewer,
        memory_store=memory_store,
        extra_updates={
            "resumed": True,
            "delivery_status": state.get("delivery_status"),
            "final_action": state.get("final_action"),
            "draft": state.get("draft"),
            "state_snapshot": state,
            "review_history": [
                *review_item.get("review_history", []),
                {
                    "decision": "approve",
                    "comments": comments,
                    "reviewer": reviewer or "dashboard",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "delivery_status": state.get("delivery_status"),
                },
            ],
        },
    )


def reject_review(
    review_id: str,
    *,
    comments: str | None = None,
    reviewer: str | None = None,
) -> dict[str, Any]:
    review_item = get_review_item(review_id)
    state = _restore_review_state(review_item)
    settings, mailbox, memory_store, _ = _build_runtime()

    if state is None:
        return apply_review_decision(
            review_id,
            decision="reject",
            comments=comments,
            reviewer=reviewer,
            memory_store=memory_store,
            extra_updates={
                "resumed": False,
                "resume_note": "Legacy review item had no saved graph state to resume.",
                "review_history": [
                    *review_item.get("review_history", []),
                    {
                        "decision": "reject",
                        "comments": comments,
                        "reviewer": reviewer or "dashboard",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    },
                ],
            },
        )

    state["human_decision"] = _human_decision_payload("reject", comments, reviewer)
    state.update(
        {
            "delivery_status": "rejected_after_review",
            "status": "rejected",
            "final_action": "reject",
        }
    )
    _finalize_review_state(state, mailbox, settings, memory_store)
    return apply_review_decision(
        review_id,
        decision="reject",
        comments=comments,
        reviewer=reviewer,
        memory_store=memory_store,
        extra_updates={
            "resumed": True,
            "delivery_status": state.get("delivery_status"),
            "final_action": state.get("final_action"),
            "draft": state.get("draft"),
            "state_snapshot": state,
            "review_history": [
                *review_item.get("review_history", []),
                {
                    "decision": "reject",
                    "comments": comments,
                    "reviewer": reviewer or "dashboard",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "delivery_status": state.get("delivery_status"),
                },
            ],
        },
    )


def revise_review(
    review_id: str,
    *,
    comments: str | None = None,
    reviewer: str | None = None,
) -> dict[str, Any]:
    review_item = get_review_item(review_id)
    state = _restore_review_state(review_item)
    _, _, memory_store, llm = _build_runtime()

    if state is None or "draft" not in state:
        raise ValueError("This review item has no saved draft to revise.")

    state["human_decision"] = _human_decision_payload("revise", comments, reviewer)
    revise_reply = make_revise_reply_node(llm)
    state.update(revise_reply(state))

    reviewed_at = datetime.now(timezone.utc).isoformat()
    previous_draft = review_item.get("draft")
    return update_review_item(
        review_id,
        updates={
            "status": "pending",
            "decision": "pending",
            "comments": comments,
            "reviewer": reviewer or "dashboard",
            "reviewed_at": reviewed_at,
            "last_revision_requested_at": reviewed_at,
            "draft": state.get("draft"),
            "state_snapshot": {
                **state,
                "draft": state.get("draft"),
            },
            "review_history": [
                *review_item.get("review_history", []),
                {
                    "decision": "revise",
                    "comments": comments,
                    "reviewer": reviewer or "dashboard",
                    "created_at": reviewed_at,
                    "previous_draft": previous_draft,
                    "updated_draft": state.get("draft"),
                },
            ],
        },
        memory_store=memory_store,
    )
