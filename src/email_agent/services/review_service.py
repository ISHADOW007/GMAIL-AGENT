"""Helpers for reading, normalizing, and updating review queue items."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from email_agent.db.mongo import MongoMemoryStore


REVIEW_QUEUE_PATH = Path("data/review_queue.json")


def _read_json_file(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_file(path: Path, payload: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _review_id_for(item: dict[str, Any]) -> str:
    review_id = item.get("review_id")
    if review_id:
        return str(review_id)
    return f"{item.get('email_id', 'review')}:{item.get('created_at', '')}"


def normalize_review_item(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    normalized["review_id"] = _review_id_for(item)
    normalized["status"] = item.get("status", "pending")
    normalized["decision"] = item.get("decision", normalized["status"])
    normalized["comments"] = item.get("comments")
    normalized["reviewer"] = item.get("reviewer")
    normalized["reviewed_at"] = item.get("reviewed_at")
    normalized["resumable"] = bool(
        item.get("checkpoint_thread_id") or item.get("state_snapshot")
    )
    normalized["legacy"] = not normalized["resumable"]
    normalized["has_draft"] = bool(item.get("draft"))
    normalized["can_revise"] = normalized["resumable"] and normalized["has_draft"]
    normalized["kind"] = "review"
    normalized["summary"] = item.get("reason")
    return normalized


def list_review_items(
    *,
    status: str | None = None,
    limit: int | None = None,
    path: Path = REVIEW_QUEUE_PATH,
) -> list[dict[str, Any]]:
    items = [normalize_review_item(item) for item in _read_json_file(path)]
    if status:
        items = [item for item in items if item["status"] == status]
    items.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    if limit is not None:
        items = items[:limit]
    return items


def get_review_item(
    review_id: str,
    *,
    path: Path = REVIEW_QUEUE_PATH,
) -> dict[str, Any]:
    rows = _read_json_file(path)
    for row in rows:
        normalized = normalize_review_item(row)
        if normalized["review_id"] == review_id:
            return normalized
    raise KeyError(review_id)


def find_latest_review_item(
    *,
    review_id: str | None = None,
    checkpoint_thread_id: str | None = None,
    email_id: str | None = None,
    status: str | None = None,
    path: Path = REVIEW_QUEUE_PATH,
) -> dict[str, Any] | None:
    items = [normalize_review_item(item) for item in _read_json_file(path)]

    if review_id:
        items = [item for item in items if item["review_id"] == review_id]
    if checkpoint_thread_id:
        items = [
            item
            for item in items
            if item.get("checkpoint_thread_id") == checkpoint_thread_id
        ]
    if email_id:
        items = [item for item in items if item.get("email_id") == email_id]
    if status:
        items = [item for item in items if item.get("status") == status]

    if not items:
        return None

    items.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return items[0]


def update_review_item(
    review_id: str,
    *,
    updates: dict[str, Any],
    path: Path = REVIEW_QUEUE_PATH,
    memory_store: MongoMemoryStore | None = None,
) -> dict[str, Any]:
    rows = _read_json_file(path)
    updated_item: dict[str, Any] | None = None

    for index, row in enumerate(rows):
        normalized = normalize_review_item(row)
        if normalized["review_id"] != review_id:
            continue

        updated_item = {
            **normalized,
            **updates,
        }
        rows[index] = updated_item
        break

    if updated_item is None:
        raise KeyError(review_id)

    _write_json_file(path, rows)

    if memory_store and memory_store.enabled and "status" in updates:
        memory_store.update_review_task(
            email_id=updated_item["email_id"],
            decision=updated_item["status"],
            comments=updated_item.get("comments"),
            reviewer=updated_item.get("reviewer"),
            reviewed_at=updated_item.get("reviewed_at")
            or datetime.now(timezone.utc).isoformat(),
            review_id=updated_item.get("review_id"),
        )

    return updated_item


def apply_review_decision(
    review_id: str,
    *,
    decision: str,
    comments: str | None = None,
    reviewer: str | None = None,
    path: Path = REVIEW_QUEUE_PATH,
    memory_store: MongoMemoryStore | None = None,
    extra_updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return update_review_item(
        review_id,
        updates={
            "status": decision,
            "decision": decision,
            "comments": comments,
            "reviewer": reviewer or "dashboard",
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            **(extra_updates or {}),
        },
        path=path,
        memory_store=memory_store,
    )

