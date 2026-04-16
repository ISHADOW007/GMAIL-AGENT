"""Resume helpers for dashboard review actions."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from langchain_openai import ChatOpenAI
from langgraph.types import Command

from email_agent.config import load_settings
from email_agent.db.mongo import MongoMemoryStore, MongoShortTermCheckpointer
from email_agent.graph.builder import build_email_graph
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

logger = logging.getLogger(__name__)


def _build_runtime():
    settings = load_settings()
    mailbox = build_mailbox_client(settings)
    memory_store = MongoMemoryStore.from_settings(settings)
    short_term_memory = MongoShortTermCheckpointer.from_settings(settings)
    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0,
    )
    graph = build_email_graph(
        llm,
        mailbox,
        settings,
        memory_store=memory_store,
        checkpointer=short_term_memory.saver,
    )
    return settings, mailbox, memory_store, short_term_memory, graph, llm


def _checkpoint_config(
    short_term_memory: MongoShortTermCheckpointer,
    review_item: dict[str, Any],
) -> dict[str, Any] | None:
    thread_id = review_item.get("checkpoint_thread_id") or review_item.get("email_id")
    if not thread_id:
        return None
    return short_term_memory.build_config(thread_id, review_item.get("checkpoint_id"))


def _checkpoint_updates(config: dict[str, Any] | None) -> dict[str, Any]:
    if not config:
        return {}
    configurable = config.get("configurable", {})
    return {
        "checkpoint_thread_id": configurable.get("thread_id"),
        "checkpoint_id": configurable.get("checkpoint_id"),
    }


def _human_decision_payload(
    decision: str,
    comments: str | None,
    reviewer: str | None,
) -> dict[str, Any]:
    return HumanDecision(
        decision=decision,
        comments=comments,
        reviewer=reviewer or "dashboard",
        reviewed_at=datetime.now(timezone.utc),
    ).model_dump(mode="json")


def _append_review_history(
    review_item: dict[str, Any],
    entry: dict[str, Any],
) -> list[dict[str, Any]]:
    return [*review_item.get("review_history", []), entry]


def _resume_with_langgraph(
    review_item: dict[str, Any],
    *,
    decision: str,
    comments: str | None,
    reviewer: str | None,
) -> tuple[dict[str, Any], dict[str, Any], MongoMemoryStore] | None:
    _, _, memory_store, short_term_memory, graph, _ = _build_runtime()
    config = _checkpoint_config(short_term_memory, review_item)
    if config is None:
        return None

    try:
        checkpoint_state = graph.get_state(config)
    except Exception as error:  # pragma: no cover - defensive runtime fallback
        logger.warning("Failed to inspect LangGraph checkpoint: %s", error)
        return None

    if checkpoint_state is None or not getattr(checkpoint_state, "next", ()):
        return None

    try:
        result = graph.invoke(
            Command(resume=_human_decision_payload(decision, comments, reviewer)),
            config=config,
        )
    except Exception as error:  # pragma: no cover - defensive runtime fallback
        logger.warning("Failed to resume LangGraph review flow: %s", error)
        return None

    return result, config, memory_store


def _restore_review_state(
    graph: Any,
    short_term_memory: MongoShortTermCheckpointer,
    review_item: dict[str, Any],
) -> dict[str, Any] | None:
    config = _checkpoint_config(short_term_memory, review_item)
    if config is not None:
        try:
            checkpoint_state = graph.get_state(config)
            if checkpoint_state and checkpoint_state.values:
                state = dict(checkpoint_state.values)
            else:
                state = None
        except Exception as error:  # pragma: no cover - defensive runtime fallback
            logger.warning("Failed to restore short-term memory from checkpointer: %s", error)
            state = None
    else:
        state = None

    if state is None:
        snapshot = review_item.get("state_snapshot")
        if not snapshot:
            return None
        state = dict(snapshot)

    # Older review items may contain a draft key with a null value. Dropping it
    # here keeps downstream model validation from treating null as a real draft.
    if not state.get("draft"):
        state.pop("draft", None)
    if review_item.get("draft"):
        state["draft"] = review_item["draft"]
    state["review_id"] = review_item["review_id"]
    return state


def _persist_short_term_state(
    graph: Any,
    short_term_memory: MongoShortTermCheckpointer,
    review_item: dict[str, Any],
    state: dict[str, Any],
    *,
    as_node: str,
) -> dict[str, Any] | None:
    config = _checkpoint_config(short_term_memory, review_item)
    if config is None:
        return None
    try:
        return graph.update_state(config, state, as_node=as_node)
    except Exception as error:  # pragma: no cover - defensive runtime fallback
        logger.warning("Failed to persist short-term memory to checkpointer: %s", error)
        return None


def _finalize_review_state(
    state: dict[str, Any],
    mailbox: Any,
    settings: Any,
    memory_store: MongoMemoryStore,
    llm: ChatOpenAI | None,
) -> dict[str, Any]:
    if state.get("draft") and state.get("final_action") not in {"ignore", "reject"}:
        send_or_save = make_send_or_save_node(mailbox, settings)
        state.update(send_or_save(state))

    update_memory = make_update_memory_node(memory_store, llm)
    state.update(update_memory(state))

    mark_processed = make_mark_processed_node(mailbox)
    state.update(mark_processed(state))
    return state


def _approve_review_legacy(
    review_item: dict[str, Any],
    *,
    comments: str | None,
    reviewer: str | None,
) -> dict[str, Any]:
    settings, mailbox, memory_store, short_term_memory, graph, llm = _build_runtime()
    state = _restore_review_state(graph, short_term_memory, review_item)

    if state is None:
        return apply_review_decision(
            review_item["review_id"],
            decision="approve",
            comments=comments,
            reviewer=reviewer,
            memory_store=memory_store,
            extra_updates={
                "resumed": False,
                "resume_note": "Legacy review item had no saved graph state to resume.",
                "review_history": _append_review_history(
                    review_item,
                    {
                        "decision": "approve",
                        "comments": comments,
                        "reviewer": reviewer or "dashboard",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    },
                ),
            },
        )

    state["human_decision"] = _human_decision_payload("approve", comments, reviewer)
    if not state.get("draft"):
        state.update(
            {
                "delivery_status": "approved_without_delivery",
                "status": "approved",
                "final_action": "approved",
            }
        )

    _finalize_review_state(state, mailbox, settings, memory_store, llm)
    persisted_config = _persist_short_term_state(
        graph,
        short_term_memory,
        review_item,
        state,
        as_node="mark_processed",
    )
    return apply_review_decision(
        review_item["review_id"],
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
            **_checkpoint_updates(persisted_config),
            "review_history": _append_review_history(
                review_item,
                {
                    "decision": "approve",
                    "comments": comments,
                    "reviewer": reviewer or "dashboard",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "delivery_status": state.get("delivery_status"),
                },
            ),
        },
    )


def _reject_review_legacy(
    review_item: dict[str, Any],
    *,
    comments: str | None,
    reviewer: str | None,
) -> dict[str, Any]:
    settings, mailbox, memory_store, short_term_memory, graph, llm = _build_runtime()
    state = _restore_review_state(graph, short_term_memory, review_item)

    if state is None:
        return apply_review_decision(
            review_item["review_id"],
            decision="reject",
            comments=comments,
            reviewer=reviewer,
            memory_store=memory_store,
            extra_updates={
                "resumed": False,
                "resume_note": "Legacy review item had no saved graph state to resume.",
                "review_history": _append_review_history(
                    review_item,
                    {
                        "decision": "reject",
                        "comments": comments,
                        "reviewer": reviewer or "dashboard",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    },
                ),
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
    _finalize_review_state(state, mailbox, settings, memory_store, llm)
    persisted_config = _persist_short_term_state(
        graph,
        short_term_memory,
        review_item,
        state,
        as_node="mark_processed",
    )
    return apply_review_decision(
        review_item["review_id"],
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
            **_checkpoint_updates(persisted_config),
            "review_history": _append_review_history(
                review_item,
                {
                    "decision": "reject",
                    "comments": comments,
                    "reviewer": reviewer or "dashboard",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "delivery_status": state.get("delivery_status"),
                },
            ),
        },
    )


def _revise_review_legacy(
    review_item: dict[str, Any],
    *,
    comments: str | None,
    reviewer: str | None,
) -> dict[str, Any]:
    _, _, memory_store, short_term_memory, graph, llm = _build_runtime()
    state = _restore_review_state(graph, short_term_memory, review_item)

    if state is None or not state.get("draft"):
        raise ValueError("This review item has no saved draft to revise.")

    state["human_decision"] = _human_decision_payload("revise", comments, reviewer)
    revise_reply = make_revise_reply_node(llm)
    state.update(revise_reply(state))

    persisted_config = _persist_short_term_state(
        graph,
        short_term_memory,
        review_item,
        state,
        as_node="revise_reply",
    )
    reviewed_at = datetime.now(timezone.utc).isoformat()
    previous_draft = review_item.get("draft")
    return update_review_item(
        review_item["review_id"],
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
            **_checkpoint_updates(persisted_config),
            "review_history": _append_review_history(
                review_item,
                {
                    "decision": "revise",
                    "comments": comments,
                    "reviewer": reviewer or "dashboard",
                    "created_at": reviewed_at,
                    "previous_draft": previous_draft,
                    "updated_draft": state.get("draft"),
                },
            ),
        },
        memory_store=memory_store,
    )


def approve_review(
    review_id: str,
    *,
    comments: str | None = None,
    reviewer: str | None = None,
) -> dict[str, Any]:
    review_item = get_review_item(review_id)
    resumed = _resume_with_langgraph(
        review_item,
        decision="approve",
        comments=comments,
        reviewer=reviewer,
    )
    if resumed is None:
        return _approve_review_legacy(
            review_item,
            comments=comments,
            reviewer=reviewer,
        )

    result, config, memory_store = resumed
    return apply_review_decision(
        review_id,
        decision="approve",
        comments=comments,
        reviewer=reviewer,
        memory_store=memory_store,
        extra_updates={
            "resumed": True,
            "delivery_status": result.get("delivery_status"),
            "final_action": result.get("final_action"),
            "draft": result.get("draft"),
            **_checkpoint_updates(config),
            "review_history": _append_review_history(
                review_item,
                {
                    "decision": "approve",
                    "comments": comments,
                    "reviewer": reviewer or "dashboard",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "delivery_status": result.get("delivery_status"),
                },
            ),
        },
    )


def reject_review(
    review_id: str,
    *,
    comments: str | None = None,
    reviewer: str | None = None,
) -> dict[str, Any]:
    review_item = get_review_item(review_id)
    resumed = _resume_with_langgraph(
        review_item,
        decision="reject",
        comments=comments,
        reviewer=reviewer,
    )
    if resumed is None:
        return _reject_review_legacy(
            review_item,
            comments=comments,
            reviewer=reviewer,
        )

    result, config, memory_store = resumed
    return apply_review_decision(
        review_id,
        decision="reject",
        comments=comments,
        reviewer=reviewer,
        memory_store=memory_store,
        extra_updates={
            "resumed": True,
            "delivery_status": result.get("delivery_status"),
            "final_action": result.get("final_action"),
            "draft": result.get("draft"),
            **_checkpoint_updates(config),
            "review_history": _append_review_history(
                review_item,
                {
                    "decision": "reject",
                    "comments": comments,
                    "reviewer": reviewer or "dashboard",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "delivery_status": result.get("delivery_status"),
                },
            ),
        },
    )


def revise_review(
    review_id: str,
    *,
    comments: str | None = None,
    reviewer: str | None = None,
) -> dict[str, Any]:
    review_item = get_review_item(review_id)
    if not review_item.get("draft"):
        raise ValueError("This review item has no saved draft to revise.")

    resumed = _resume_with_langgraph(
        review_item,
        decision="revise",
        comments=comments,
        reviewer=reviewer,
    )
    if resumed is None:
        return _revise_review_legacy(
            review_item,
            comments=comments,
            reviewer=reviewer,
        )

    result, config, memory_store = resumed
    latest_review_item = get_review_item(review_id)
    reviewed_at = datetime.now(timezone.utc).isoformat()
    return update_review_item(
        review_id,
        updates={
            "status": "pending",
            "decision": "pending",
            "comments": comments,
            "reviewer": reviewer or "dashboard",
            "reviewed_at": reviewed_at,
            "last_revision_requested_at": reviewed_at,
            "draft": result.get("draft", latest_review_item.get("draft")),
            "delivery_status": result.get("delivery_status", "pending_human_review"),
            "final_action": result.get("final_action", "human_review"),
            **_checkpoint_updates(config),
            "review_history": _append_review_history(
                latest_review_item,
                {
                    "decision": "revise",
                    "comments": comments,
                    "reviewer": reviewer or "dashboard",
                    "created_at": reviewed_at,
                    "previous_draft": review_item.get("draft"),
                    "updated_draft": result.get("draft", latest_review_item.get("draft")),
                },
            ),
        },
        memory_store=memory_store,
    )
