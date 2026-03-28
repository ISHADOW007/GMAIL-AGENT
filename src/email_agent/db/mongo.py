from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

try:
    from pymongo import MongoClient
except ImportError:  # pragma: no cover
    MongoClient = None

from email_agent.models import (
    ClassificationResult,
    ContactMemory,
    DraftReply,
    MemoryBundle,
    NormalizedEmail,
    ThreadMemory,
)


@dataclass(slots=True)
class MongoMemoryStore:
    uri: str | None
    database_name: str
    enabled: bool = field(init=False, default=False)
    _client: Any = field(init=False, default=None, repr=False)
    _db: Any = field(init=False, default=None, repr=False)

    def __post_init__(self) -> None:
        self.enabled = bool(self.uri and MongoClient)
        if self.enabled:
            self._client = MongoClient(self.uri)
            self._db = self._client[self.database_name]

    @classmethod
    def from_settings(cls, settings: Any) -> "MongoMemoryStore":
        return cls(
            uri=getattr(settings, "mongodb_uri", None),
            database_name=getattr(settings, "mongodb_database", "email_agent"),
        )

    def load_memory_bundle(self, normalized_email: NormalizedEmail) -> MemoryBundle:
        if not self.enabled:
            return MemoryBundle()

        contact_doc = self._db.contacts.find_one({"email": normalized_email.sender})
        thread_doc = self._db.threads.find_one({"thread_id": normalized_email.thread_id})
        similar_cursor = self._db.drafts.find(
            {"sender": normalized_email.sender, "status": "approved"},
            {"body": 1},
        ).limit(3)
        memory_doc = self._db.memories.find_one({"scope": "global"}) or {}

        contact = ContactMemory.model_validate(contact_doc) if contact_doc else None
        thread = ThreadMemory.model_validate(thread_doc) if thread_doc else None
        similar_replies = [doc.get("body", "") for doc in similar_cursor]
        business_facts = memory_doc.get("business_facts", [])

        return MemoryBundle(
            contact=contact,
            thread=thread,
            similar_replies=similar_replies,
            business_facts=business_facts,
        )

    def create_review_task(
        self,
        normalized_email: NormalizedEmail,
        classification: ClassificationResult,
        draft: DraftReply | None,
    ) -> None:
        if not self.enabled:
            return

        self._db.reviews.insert_one(
            {
                "email_id": normalized_email.email_id,
                "thread_id": normalized_email.thread_id,
                "sender": normalized_email.sender,
                "subject": normalized_email.subject,
                "classification": classification.model_dump(mode="json"),
                "draft": draft.model_dump(mode="json") if draft else None,
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    def update_review_task(
        self,
        *,
        email_id: str,
        decision: str,
        comments: str | None,
        reviewer: str | None,
        reviewed_at: str,
    ) -> None:
        if not self.enabled:
            return

        self._db.reviews.update_many(
            {"email_id": email_id, "status": "pending"},
            {
                "$set": {
                    "status": decision,
                    "decision": decision,
                    "comments": comments,
                    "reviewer": reviewer,
                    "reviewed_at": reviewed_at,
                }
            },
        )

    def update_after_run(self, state: dict[str, Any]) -> None:
        if not self.enabled:
            return

        normalized_email = state.get("normalized_email", {})
        classification = state.get("classification")
        draft = state.get("draft")
        final_action = state.get("final_action")
        delivery_status = state.get("delivery_status")

        if normalized_email:
            self._db.threads.update_one(
                {"thread_id": normalized_email["thread_id"]},
                {
                    "$set": {
                        "thread_id": normalized_email["thread_id"],
                        "summary": normalized_email.get("summary"),
                        "last_outcome": delivery_status,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                },
                upsert=True,
            )
            self._db.contacts.update_one(
                {"email": normalized_email["sender"]},
                {
                    "$setOnInsert": {
                        "email": normalized_email["sender"],
                        "importance": "normal",
                        "preferences": [],
                        "notes": [],
                    }
                },
                upsert=True,
            )

        if draft:
            self._db.drafts.insert_one(
                {
                    "email_id": state.get("email_id"),
                    "thread_id": state.get("thread_id"),
                    "sender": normalized_email.get("sender"),
                    "status": delivery_status,
                    "final_action": final_action,
                    "classification": classification,
                    **draft,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
