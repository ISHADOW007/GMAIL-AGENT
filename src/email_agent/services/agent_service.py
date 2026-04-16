"""Shared runtime orchestration used by both the CLI and FastAPI backend."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain_openai import ChatOpenAI

from email_agent.config import load_settings
from email_agent.db.mongo import MongoMemoryStore, MongoShortTermCheckpointer
from email_agent.graph.builder import build_email_graph
from email_agent.mailbox import build_mailbox_client
from email_agent.models import ClassificationResult, DraftReply, HumanDecision
from email_agent.services.review_service import list_review_items


LAST_RUN_PATH = Path("data/last_run.json")
PROGRESS_PATH = Path("data/run_progress.json")
NODE_EXECUTION_ORDER = [
    "normalize_email",
    "load_thread",
    "load_memory",
    "classify_email",
    "ignore_email",
    "retrieve_context",
    "draft_reply",
    "safety_check",
    "queue_human_review",
    "human_review",
    "revise_reply",
    "send_or_save",
    "update_memory",
    "mark_processed",
]


def _read_json_file(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _write_last_run(payload: dict[str, Any]) -> None:
    LAST_RUN_PATH.parent.mkdir(parents=True, exist_ok=True)
    LAST_RUN_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_progress(payload: dict[str, Any]) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _build_runtime(progress_callback=None):
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
        progress_callback=progress_callback,
    )
    return settings, mailbox, graph, short_term_memory


def _serialize_unread_preview(mailbox: Any, limit: int) -> list[dict[str, Any]]:
    emails = mailbox.fetch_unread(limit=limit)
    return [
        {
            "id": email.id,
            "thread_id": email.thread_id,
            "from_address": email.from_address,
            "subject": email.subject,
            "body": email.body,
            "summary": " ".join(email.body.split())[:240],
            "received_at": email.received_at.isoformat(),
            "is_unread": email.is_unread,
            "kind": "unread",
        }
        for email in emails
    ]


def collect_progress_snapshot() -> dict[str, Any]:
    if not PROGRESS_PATH.exists():
        return {
            "status": "idle",
            "backend": None,
            "total_emails": 0,
            "processed_count": 0,
            "percent_complete": 0,
            "current_email": None,
            "recent_results": [],
            "started_at": None,
            "updated_at": None,
            "error_message": None,
            "email_runs": [],
        }

    snapshot = json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
    return {
        "status": snapshot.get("status", "idle"),
        "backend": snapshot.get("backend"),
        "total_emails": snapshot.get("total_emails", 0),
        "processed_count": snapshot.get("processed_count", 0),
        "percent_complete": snapshot.get("percent_complete", 0),
        "current_email": snapshot.get("current_email"),
        "recent_results": snapshot.get("recent_results", []),
        "started_at": snapshot.get("started_at"),
        "updated_at": snapshot.get("updated_at"),
        "error_message": snapshot.get("error_message"),
        "email_runs": snapshot.get("email_runs", []),
    }


def _fresh_node_executions() -> list[dict[str, Any]]:
    return [
        {
            "node_name": node_name,
            "status": "pending",
            "summary": "Waiting to run.",
            "result_preview": "",
            "started_at": None,
            "completed_at": None,
            "duration_ms": None,
        }
        for node_name in NODE_EXECUTION_ORDER
    ]


def _truncate_preview(payload: Any, *, limit: int = 1200) -> str:
    rendered = json.dumps(payload, indent=2, default=str)
    if len(rendered) <= limit:
        return rendered
    return f"{rendered[:limit]}..."


def _summarize_node_output(node_name: str, payload: dict[str, Any]) -> str:
    if node_name == "classify_email" and payload.get("classification"):
        classification = payload["classification"]
        return (
            f"Intent: {classification.get('intent', 'unknown')} | "
            f"Action: {classification.get('action', 'unknown')} | "
            f"Risk: {classification.get('risk', 'unknown')}"
        )
    if node_name == "draft_reply" and payload.get("draft"):
        draft = payload["draft"]
        return f"Drafted reply: {draft.get('subject', 'Untitled draft')}"
    if node_name == "send_or_save":
        return f"Delivery status: {payload.get('delivery_status', 'unknown')}"
    if node_name == "queue_human_review":
        return f"Prepared review item: {payload.get('review_id', 'pending')}"
    if node_name == "human_review":
        return "Paused for a human decision."
    if node_name == "mark_processed":
        return "Marked email as processed in the mailbox."
    if node_name == "ignore_email":
        return "Email routed to ignore path."
    if node_name == "load_thread":
        return f"Loaded {len(payload.get('thread_messages', []))} historical thread messages."
    if node_name == "load_memory":
        memory = payload.get("memory", {})
        return f"Loaded memory keys: {', '.join(memory.keys()) or 'none'}."
    if node_name == "retrieve_context":
        context = payload.get("retrieved_context", {})
        return f"Prepared context keys: {', '.join(context.keys()) or 'none'}."
    if node_name == "safety_check" and payload.get("safety_result"):
        safety = payload["safety_result"]
        return (
            f"Safe to send: {safety.get('safe_to_send')} | "
            f"Needs human: {safety.get('needs_human')}"
        )
    if node_name == "update_memory":
        return "Persisted the run outcome into memory stores."
    if node_name == "normalize_email":
        normalized = payload.get("normalized_email", {})
        return f"Normalized sender: {normalized.get('sender', 'unknown')}."
    if node_name == "revise_reply" and payload.get("draft"):
        draft = payload["draft"]
        return f"Revised draft: {draft.get('subject', 'Updated draft')}"
    return f"Updated keys: {', '.join(payload.keys()) or 'none'}."


def _update_node_execution(
    email_run: dict[str, Any],
    *,
    phase: str,
    node_name: str,
    payload: dict[str, Any],
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    node_execution = next(
        (item for item in email_run["node_executions"] if item["node_name"] == node_name),
        None,
    )
    if node_execution is None:
        return

    if phase == "start":
        node_execution["status"] = "running"
        node_execution["summary"] = f"Executing {node_name}..."
        node_execution["started_at"] = now
        return

    if phase == "error":
        node_execution["status"] = "error"
        node_execution["summary"] = payload.get("error", "Node execution failed.")
        node_execution["completed_at"] = now
        node_execution["result_preview"] = _truncate_preview(payload)
        return

    if phase == "interrupt":
        node_execution["status"] = "paused"
        node_execution["summary"] = "Paused and waiting for a human decision."
        node_execution["completed_at"] = now
        if node_execution.get("started_at"):
            started_at = datetime.fromisoformat(node_execution["started_at"])
            completed_at = datetime.fromisoformat(now)
            node_execution["duration_ms"] = int((completed_at - started_at).total_seconds() * 1000)
        node_execution["result_preview"] = _truncate_preview(payload)
        return

    node_execution["status"] = "completed"
    node_execution["completed_at"] = now
    if node_execution.get("started_at"):
        started_at = datetime.fromisoformat(node_execution["started_at"])
        completed_at = datetime.fromisoformat(now)
        node_execution["duration_ms"] = int((completed_at - started_at).total_seconds() * 1000)
    node_execution["summary"] = _summarize_node_output(node_name, payload)
    node_execution["result_preview"] = _truncate_preview(payload)


def _finalize_node_executions(email_run: dict[str, Any]) -> None:
    for node_execution in email_run["node_executions"]:
        if node_execution["status"] == "pending":
            node_execution["status"] = "skipped"
            node_execution["summary"] = "Skipped because this branch was not taken."
        if node_execution["status"] == "running":
            node_execution["status"] = "completed"
            node_execution["summary"] = "Completed."


def run_agent(limit: int | None = None, include_draft_body: bool = False) -> dict[str, Any]:
    settings = load_settings()
    effective_limit = limit or settings.max_emails
    started_at = datetime.now(timezone.utc).isoformat()
    email_runs: list[dict[str, Any]] = []
    current_email_run: dict[str, Any] | None = None

    def build_progress_payload(
        *,
        status: str,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        processed_count = len(run_summary["results"])
        total_emails = len(emails)
        percent_complete = 100 if status == "completed" else (
            int((processed_count / total_emails) * 100) if total_emails else 0
        )
        return {
            "status": status,
            "backend": settings.email_backend,
            "total_emails": total_emails,
            "processed_count": processed_count,
            "percent_complete": percent_complete,
            "current_email": current_email_run,
            "recent_results": run_summary["results"][-5:],
            "started_at": started_at,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "error_message": error_message,
            "email_runs": email_runs[-6:],
        }

    def handle_node_event(phase: str, node_name: str, payload: dict[str, Any]) -> None:
        if current_email_run is None:
            return
        _update_node_execution(
            current_email_run,
            phase=phase,
            node_name=node_name,
            payload=payload,
        )
        if phase == "complete":
            current_email_run["active_node"] = None
        elif phase == "start":
            current_email_run["active_node"] = node_name
        elif phase == "interrupt":
            current_email_run["active_node"] = None
            current_email_run["status"] = "paused"
        elif phase == "error":
            current_email_run["active_node"] = node_name
            current_email_run["status"] = "error"
        _write_progress(build_progress_payload(status="running"))

    settings, mailbox, graph, short_term_memory = _build_runtime(progress_callback=handle_node_event)
    emails = mailbox.fetch_unread(limit=effective_limit)

    run_summary: dict[str, Any] = {
        "backend": settings.email_backend,
        "processed_count": len(emails),
        "limit": effective_limit,
        "ran_at": started_at,
        "results": [],
    }
    _write_progress(build_progress_payload(status="running"))

    try:
        for email in emails:
            # Emails are fetched in a batch, but each one still gets a separate
            # graph invocation and its own progress timeline.
            current_email_run = {
                "id": email.id,
                "subject": email.subject,
                "from_address": email.from_address,
                "received_at": email.received_at.isoformat(),
                "status": "running",
                "active_node": None,
                "node_executions": _fresh_node_executions(),
            }
            email_runs.append(current_email_run)
            _write_progress(build_progress_payload(status="running"))

            result = graph.invoke(
                {
                    "run_id": email.id,
                    "email": email.model_dump(mode="json"),
                },
                config=short_term_memory.build_config(email.id),
            )
            interrupted = "__interrupt__" in result
            classification = ClassificationResult.model_validate(result["classification"])

            item = {
                "id": email.id,
                "subject": email.subject,
                "from_address": email.from_address,
                "body": email.body,
                "received_at": email.received_at.isoformat(),
                "intent": classification.intent,
                "urgency": classification.urgency,
                "risk": classification.risk,
                "action": classification.action,
                "reason": classification.reason,
                "delivery_status": result["delivery_status"],
                "kind": "activity",
            }

            if "draft" in result:
                draft = DraftReply.model_validate(result["draft"])
                item["draft"] = {
                    "subject": draft.subject,
                    "body": draft.body if include_draft_body else None,
                }

            if "human_decision" in result:
                human_decision = HumanDecision.model_validate(result["human_decision"])
                item["human_decision"] = human_decision.decision

            run_summary["results"].append(item)
            current_email_run["delivery_status"] = item["delivery_status"]
            current_email_run["final_action"] = item["action"]
            current_email_run["status"] = "paused" if interrupted else "completed"
            _finalize_node_executions(current_email_run)
            _write_progress(build_progress_payload(status="running"))
    except Exception as error:
        if current_email_run is not None:
            current_email_run["status"] = "error"
            _finalize_node_executions(current_email_run)
        _write_progress(
            build_progress_payload(
                status="error",
                error_message=str(error),
            )
        )
        raise

    _write_last_run(run_summary)
    _write_progress(build_progress_payload(status="completed"))
    return run_summary


def collect_dashboard_snapshot(limit: int = 5) -> dict[str, Any]:
    settings = load_settings()
    mailbox = build_mailbox_client(settings)
    unread_preview = _serialize_unread_preview(mailbox, limit)

    review_items = list_review_items(status="pending", limit=8)
    last_run = {}
    if LAST_RUN_PATH.exists():
        last_run = json.loads(LAST_RUN_PATH.read_text(encoding="utf-8"))

    return {
        "backend": settings.email_backend,
        "auto_send": settings.auto_send,
        "max_emails": settings.max_emails,
        "mongodb_enabled": bool(settings.mongodb_uri),
        "stats": {
            "unread_count": len(unread_preview),
            "review_count": len(list_review_items(status="pending")),
            "last_run_processed": last_run.get("processed_count", 0),
        },
        "unread_emails": unread_preview,
        "review_items": review_items,
        "last_run": last_run,
    }

