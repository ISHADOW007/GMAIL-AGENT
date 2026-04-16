"""LangGraph-backed Mongo persistence for checkpoints and long-term memory."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.base import BaseStore, Item
from langgraph.store.memory import InMemoryStore

try:
    from langgraph.checkpoint.mongodb import MongoDBSaver
except ImportError:  # pragma: no cover - optional extra dependency
    MongoDBSaver = None

try:
    from langgraph.store.mongodb import MongoDBStore, create_vector_index_config
except ImportError:  # pragma: no cover - optional extra dependency
    MongoDBStore = None
    create_vector_index_config = None

from email_agent.llm.prompts import MEMORY_EXTRACTION_SYSTEM_PROMPT
from email_agent.models import (
    ClassificationResult,
    ContactMemory,
    DraftReply,
    MemoryBundle,
    MemoryExtraction,
    NormalizedEmail,
    ThreadMemory,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class MongoShortTermCheckpointer:
    uri: str | None
    database_name: str
    enabled: bool = field(init=False, default=False)
    persistent: bool = field(init=False, default=False)
    saver: Any = field(init=False, default=None, repr=False)
    _context: Any = field(init=False, default=None, repr=False)

    def __post_init__(self) -> None:
        if self.uri and MongoDBSaver:
            try:
                candidate = MongoDBSaver.from_conn_string(self.uri, self.database_name)
                if hasattr(candidate, "__enter__"):
                    self._context = candidate
                    self.saver = candidate.__enter__()
                else:
                    self.saver = candidate
                if hasattr(self.saver, "setup"):
                    self.saver.setup()
                self.enabled = True
                self.persistent = True
                return
            except Exception as error:  # pragma: no cover - defensive runtime fallback
                logger.warning(
                    "MongoDB checkpointer unavailable. Falling back to in-memory checkpoints: %s",
                    error,
                )

        if self.uri and not MongoDBSaver:
            logger.warning(
                "langgraph-checkpoint-mongodb is not installed. Falling back to in-memory checkpoints."
            )

        self.saver = InMemorySaver()
        self.enabled = True
        self.persistent = False

    @classmethod
    def from_settings(cls, settings: Any) -> "MongoShortTermCheckpointer":
        return cls(
            uri=getattr(settings, "mongodb_uri", None),
            database_name=getattr(settings, "mongodb_database", "email_agent"),
        )

    def build_config(self, thread_id: str, checkpoint_id: str | None = None) -> dict[str, Any]:
        config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
        if checkpoint_id:
            config["configurable"]["checkpoint_id"] = checkpoint_id
        return config


@dataclass(slots=True)
class MongoMemoryStore:
    uri: str | None
    database_name: str
    collection_name: str = "long_term_memory"
    namespace_root: str = "email_agent"
    openai_api_key: str | None = None
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    enabled: bool = field(init=False, default=False)
    persistent: bool = field(init=False, default=False)
    semantic_search_enabled: bool = field(init=False, default=False)
    store: BaseStore = field(init=False, repr=False)
    _context: Any = field(init=False, default=None, repr=False)
    _embeddings: OpenAIEmbeddings | None = field(init=False, default=None, repr=False)

    def __post_init__(self) -> None:
        self._embeddings = self._build_embeddings()
        if self.uri and MongoDBStore:
            try:
                candidate = MongoDBStore.from_conn_string(
                    conn_string=self.uri,
                    db_name=self.database_name,
                    collection_name=self.collection_name,
                    index_config=self._build_vector_index_config(),
                )
                if hasattr(candidate, "__enter__"):
                    self._context = candidate
                    self.store = candidate.__enter__()
                else:
                    self.store = candidate
                if hasattr(self.store, "setup"):
                    self.store.setup()
                self.enabled = True
                self.persistent = True
                self.semantic_search_enabled = self._embeddings is not None
                return
            except TypeError:
                candidate = MongoDBStore.from_conn_string(
                    conn_string=self.uri,
                    db_name=self.database_name,
                    collection_name=self.collection_name,
                )
                if hasattr(candidate, "__enter__"):
                    self._context = candidate
                    self.store = candidate.__enter__()
                else:
                    self.store = candidate
                if hasattr(self.store, "setup"):
                    self.store.setup()
                self.enabled = True
                self.persistent = True
                self.semantic_search_enabled = False
                return
            except Exception as error:  # pragma: no cover - defensive runtime fallback
                logger.warning(
                    "LangGraph MongoDB store unavailable. Falling back to in-memory store: %s",
                    error,
                )

        if self.uri and not MongoDBStore:
            logger.warning(
                "langgraph-store-mongodb is not installed. Falling back to in-memory long-term store."
            )

        self.store = InMemoryStore(index=self._build_inmemory_index_config())
        self.enabled = True
        self.persistent = False
        self.semantic_search_enabled = self._embeddings is not None

    @classmethod
    def from_settings(cls, settings: Any) -> "MongoMemoryStore":
        return cls(
            uri=getattr(settings, "mongodb_uri", None),
            database_name=getattr(settings, "mongodb_database", "email_agent"),
            collection_name=getattr(
                settings,
                "mongodb_store_collection",
                "long_term_memory",
            ),
            namespace_root=getattr(
                settings,
                "mongodb_memory_namespace",
                "email_agent",
            ),
            openai_api_key=getattr(settings, "openai_api_key", None),
            embedding_model=getattr(
                settings,
                "openai_embedding_model",
                "text-embedding-3-small",
            ),
            embedding_dimensions=getattr(
                settings,
                "openai_embedding_dimensions",
                1536,
            ),
        )

    def _build_embeddings(self) -> OpenAIEmbeddings | None:
        if not self.openai_api_key:
            return None
        return OpenAIEmbeddings(
            api_key=self.openai_api_key,
            model=self.embedding_model,
        )

    def _build_inmemory_index_config(self) -> dict[str, Any] | None:
        if self._embeddings is None:
            return None
        return {
            "dims": self.embedding_dimensions,
            "embed": self._embeddings,
            "fields": ["summary", "examples[*].body", "facts[*]"],
        }

    def _build_vector_index_config(self) -> Any | None:
        if self._embeddings is None or create_vector_index_config is None:
            return None
        return create_vector_index_config(
            embed=self._embeddings,
            dims=self.embedding_dimensions,
            fields=["summary", "examples[*].body", "facts[*]"],
            filters=["sender", "intent"],
        )

    def _disable_on_error(self, error: Exception) -> None:
        logger.warning(
            "LangGraph store operation failed. Falling back to in-memory long-term store: %s",
            error,
        )
        self.store = InMemoryStore(index=self._build_inmemory_index_config())
        self.enabled = True
        self.persistent = False
        self.semantic_search_enabled = self._embeddings is not None

    def _contact_namespace(self) -> tuple[str, ...]:
        return (self.namespace_root, "contacts")

    def _thread_namespace(self) -> tuple[str, ...]:
        return (self.namespace_root, "threads")

    def _reply_examples_namespace(self) -> tuple[str, ...]:
        return (self.namespace_root, "reply_examples")

    def _business_facts_namespace(self) -> tuple[str, ...]:
        return (self.namespace_root, "business_facts")

    def _review_history_namespace(self) -> tuple[str, ...]:
        return (self.namespace_root, "review_history")

    def _draft_history_namespace(self) -> tuple[str, ...]:
        return (self.namespace_root, "draft_history")

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _get_item(self, namespace: tuple[str, ...], key: str) -> Item | None:
        return self.store.get(namespace, key)

    def _put_item(
        self,
        namespace: tuple[str, ...],
        key: str,
        value: dict[str, Any],
        *,
        index: list[str] | bool | None = None,
    ) -> None:
        self.store.put(namespace, key, value, index=index)

    @staticmethod
    def _recent_message_summaries(state: dict[str, Any], *, limit: int = 3) -> list[str]:
        messages = state.get("thread_messages", []) or []
        recent_messages = []
        for item in messages[-limit:]:
            sender = item.get("sender") or item.get("from_address") or "unknown"
            subject = item.get("subject") or "(no subject)"
            recent_messages.append(f"{sender}: {subject}")
        return recent_messages

    @staticmethod
    def _reply_examples_key(sender: str, intent: str | None) -> str:
        cleaned_intent = (intent or "general").strip().lower() or "general"
        return f"{sender}:{cleaned_intent}"

    @staticmethod
    def _review_history_key(review_id: str | None, email_id: str) -> str:
        return review_id or email_id

    @staticmethod
    def _draft_history_key(email_id: str | None) -> str:
        base = email_id or "draft"
        timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
        return f"{base}:{timestamp}"

    @staticmethod
    def _dedupe_strings(values: list[str], *, limit: int = 5) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = str(value).strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            deduped.append(cleaned)
            if len(deduped) >= limit:
                break
        return deduped

    @staticmethod
    def _dedupe_reply_examples(examples: list[dict[str, Any]], *, limit: int = 3) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen_bodies: set[str] = set()
        sorted_examples = sorted(
            examples,
            key=lambda example: example.get("created_at", ""),
            reverse=True,
        )
        for example in sorted_examples:
            body = str(example.get("body", "")).strip()
            if not body or body in seen_bodies:
                continue
            seen_bodies.add(body)
            deduped.append(example)
            if len(deduped) >= limit:
                break
        return deduped

    @staticmethod
    def _memory_query_text(normalized_email: NormalizedEmail) -> str:
        return "\n".join(
            part
            for part in [
                normalized_email.subject,
                normalized_email.summary,
                normalized_email.clean_body[:1200],
            ]
            if part
        )

    def _search_items(
        self,
        namespace: tuple[str, ...],
        *,
        filter: dict[str, Any] | None = None,
        query: str | None = None,
        limit: int = 5,
    ) -> list[Any]:
        search_query = query if self.semantic_search_enabled else None
        return self.store.search(namespace, filter=filter, query=search_query, limit=limit)

    def load_memory_bundle(self, normalized_email: NormalizedEmail) -> MemoryBundle:
        if not self.enabled:
            return MemoryBundle()

        query_text = self._memory_query_text(normalized_email)
        try:
            contact_item = self._get_item(
                self._contact_namespace(),
                normalized_email.sender,
            )
            thread_item = (
                self._get_item(
                    self._thread_namespace(),
                    normalized_email.thread_id,
                )
                if normalized_email.thread_id
                else None
            )
            reply_example_items = self._search_items(
                self._reply_examples_namespace(),
                filter={"sender": normalized_email.sender},
                query=query_text,
                limit=3,
            )
            business_fact_items = self._search_items(
                self._business_facts_namespace(),
                query=query_text,
                limit=3,
            )
        except Exception as error:
            self._disable_on_error(error)
            return MemoryBundle()

        contact = (
            ContactMemory.model_validate(contact_item.value)
            if contact_item and contact_item.value
            else None
        )
        thread = (
            ThreadMemory.model_validate(thread_item.value)
            if thread_item and thread_item.value
            else None
        )

        flattened_examples: list[dict[str, Any]] = []
        for item in reply_example_items:
            flattened_examples.extend(item.value.get("examples", []))
        similar_replies = [
            example.get("body", "")
            for example in self._dedupe_reply_examples(flattened_examples)
            if example.get("body")
        ]

        flattened_facts: list[str] = []
        for item in business_fact_items:
            flattened_facts.extend(item.value.get("facts", []))
        business_facts = self._dedupe_strings(flattened_facts, limit=5)

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
        *,
        review_id: str | None = None,
    ) -> None:
        if not self.enabled:
            return

        try:
            key = self._review_history_key(review_id, normalized_email.email_id)
            self._put_item(
                self._review_history_namespace(),
                key,
                {
                    "review_id": review_id,
                    "email_id": normalized_email.email_id,
                    "thread_id": normalized_email.thread_id,
                    "sender": normalized_email.sender,
                    "subject": normalized_email.subject,
                    "classification": classification.model_dump(mode="json"),
                    "draft": draft.model_dump(mode="json") if draft else None,
                    "status": "pending",
                    "created_at": self._now().isoformat(),
                },
            )
        except Exception as error:
            self._disable_on_error(error)

    def update_review_task(
        self,
        *,
        email_id: str,
        decision: str,
        comments: str | None,
        reviewer: str | None,
        reviewed_at: str,
        review_id: str | None = None,
    ) -> None:
        if not self.enabled:
            return

        try:
            key = self._review_history_key(review_id, email_id)
            current_item = self._get_item(self._review_history_namespace(), key)
            current_value = current_item.value if current_item else {"email_id": email_id}
            self._put_item(
                self._review_history_namespace(),
                key,
                {
                    **current_value,
                    "review_id": review_id or current_value.get("review_id"),
                    "email_id": email_id,
                    "status": decision,
                    "decision": decision,
                    "comments": comments,
                    "reviewer": reviewer,
                    "reviewed_at": reviewed_at,
                },
            )
        except Exception as error:
            self._disable_on_error(error)

    def _extract_memory_with_llm(
        self,
        llm: ChatOpenAI | None,
        state: dict[str, Any],
        *,
        existing_contact: dict[str, Any],
        existing_thread: dict[str, Any],
    ) -> MemoryExtraction:
        fallback = MemoryExtraction(
            thread_summary=state.get("thread_summary")
            or state.get("normalized_email", {}).get("summary"),
        )
        if llm is None:
            return fallback

        try:
            extractor = llm.with_structured_output(MemoryExtraction)
            prompt = (
                "Create a compact long-term memory update from this completed email workflow.\n\n"
                f"Existing contact memory: {existing_contact}\n"
                f"Existing thread memory: {existing_thread}\n"
                f"Normalized email: {state.get('normalized_email', {})}\n"
                f"Thread summary: {state.get('thread_summary')}\n"
                f"Thread messages: {state.get('thread_messages', [])[-5:]}\n"
                f"Classification: {state.get('classification', {})}\n"
                f"Draft: {state.get('draft', {})}\n"
                f"Human decision: {state.get('human_decision', {})}\n"
                f"Final action: {state.get('final_action')}\n"
                f"Delivery status: {state.get('delivery_status')}\n"
            )
            extracted = extractor.invoke(
                [
                    SystemMessage(content=MEMORY_EXTRACTION_SYSTEM_PROMPT),
                    HumanMessage(content=prompt),
                ]
            )
            return extracted
        except Exception as error:  # pragma: no cover - defensive runtime fallback
            logger.warning("LLM memory extraction failed. Using fallback memory update: %s", error)
            return fallback

    def update_after_run(self, state: dict[str, Any], *, llm: ChatOpenAI | None = None) -> None:
        if not self.enabled:
            return

        normalized_email = state.get("normalized_email", {}) or {}
        if not normalized_email:
            return

        classification = state.get("classification") or {}
        draft = state.get("draft")
        final_action = state.get("final_action")
        delivery_status = state.get("delivery_status")
        sender = normalized_email.get("sender")
        thread_id = normalized_email.get("thread_id")
        now = self._now()

        try:
            existing_contact_item = (
                self._get_item(self._contact_namespace(), sender) if sender else None
            )
            existing_contact_value = (
                existing_contact_item.value if existing_contact_item else {}
            )
            existing_thread_item = (
                self._get_item(self._thread_namespace(), thread_id) if thread_id else None
            )
            existing_thread_value = existing_thread_item.value if existing_thread_item else {}
            extracted = self._extract_memory_with_llm(
                llm,
                state,
                existing_contact=existing_contact_value,
                existing_thread=existing_thread_value,
            )

            if sender:
                self._put_item(
                    self._contact_namespace(),
                    sender,
                    {
                        "email": sender,
                        "name": existing_contact_value.get("name"),
                        "importance": extracted.importance
                        or existing_contact_value.get("importance", "normal"),
                        "preferences": self._dedupe_strings(
                            [
                                *existing_contact_value.get("preferences", []),
                                *extracted.preferences,
                            ],
                            limit=5,
                        ),
                        "notes": self._dedupe_strings(
                            [
                                *existing_contact_value.get("notes", []),
                                *extracted.notes,
                            ],
                            limit=5,
                        ),
                        "interaction_count": int(
                            existing_contact_value.get("interaction_count", 0)
                        )
                        + 1,
                        "last_seen_at": now.isoformat(),
                    },
                )

            if thread_id:
                self._put_item(
                    self._thread_namespace(),
                    thread_id,
                    {
                        "thread_id": thread_id,
                        "summary": extracted.thread_summary
                        or state.get("thread_summary")
                        or normalized_email.get("summary")
                        or existing_thread_value.get("summary"),
                        "last_outcome": delivery_status or existing_thread_value.get("last_outcome"),
                        "recent_messages": self._recent_message_summaries(state)
                        or existing_thread_value.get("recent_messages", []),
                        "updated_at": now.isoformat(),
                    },
                    index=["summary"],
                )

            if extracted.business_facts:
                existing_facts_item = self._get_item(
                    self._business_facts_namespace(),
                    "global",
                )
                existing_facts_value = (
                    existing_facts_item.value if existing_facts_item else {}
                )
                merged_facts = self._dedupe_strings(
                    [
                        *existing_facts_value.get("facts", []),
                        *extracted.business_facts,
                    ],
                    limit=20,
                )
                self._put_item(
                    self._business_facts_namespace(),
                    "global",
                    {
                        "facts": merged_facts,
                        "updated_at": now.isoformat(),
                    },
                    index=["facts[*]"],
                )

            if draft:
                self._put_item(
                    self._draft_history_namespace(),
                    self._draft_history_key(state.get("email_id")),
                    {
                        "email_id": state.get("email_id"),
                        "thread_id": state.get("thread_id"),
                        "sender": sender,
                        "status": delivery_status,
                        "final_action": final_action,
                        "classification": classification,
                        **draft,
                        "created_at": now.isoformat(),
                    },
                )

            if draft and sender and delivery_status in {"sent", "draft_saved"}:
                reply_examples_key = self._reply_examples_key(
                    sender,
                    classification.get("intent"),
                )
                existing_examples_item = self._get_item(
                    self._reply_examples_namespace(),
                    reply_examples_key,
                )
                existing_examples_value = (
                    existing_examples_item.value if existing_examples_item else {}
                )
                merged_examples = self._dedupe_reply_examples(
                    [
                        *existing_examples_value.get("examples", []),
                        {
                            "subject": draft.get("subject"),
                            "body": draft.get("body"),
                            "quality": delivery_status,
                            "created_at": now.isoformat(),
                        },
                    ]
                )
                self._put_item(
                    self._reply_examples_namespace(),
                    reply_examples_key,
                    {
                        "sender": sender,
                        "intent": classification.get("intent", "general"),
                        "examples": merged_examples,
                        "updated_at": now.isoformat(),
                    },
                    index=["examples[*].body"],
                )
        except Exception as error:
            self._disable_on_error(error)
