from __future__ import annotations

from typing import Literal, TypedDict


class EmailAgentState(TypedDict, total=False):
    run_id: str
    review_id: str
    email_id: str
    thread_id: str
    email: dict
    normalized_email: dict
    thread_messages: list[dict]
    thread_summary: str | None
    memory: dict
    retrieved_context: dict
    classification: dict
    draft: dict
    safety_result: dict
    human_decision: dict
    final_action: str
    delivery_status: str
    status: Literal[
        "new",
        "classified",
        "drafted",
        "pending_human",
        "approved",
        "rejected",
        "sent",
        "draft_saved",
        "ignored",
        "completed",
        "error",
    ]
