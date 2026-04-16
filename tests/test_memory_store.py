from __future__ import annotations

import unittest

from email_agent.db.mongo import MongoMemoryStore
from email_agent.models import ClassificationResult, DraftReply, NormalizedEmail


class _StructuredExtractorStub:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def invoke(self, _messages):
        return type("MemoryExtractionResult", (), self.payload)()


class _LLMStub:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def with_structured_output(self, _schema):
        return _StructuredExtractorStub(self.payload)


class MemoryStoreTests(unittest.TestCase):
    def test_long_term_memory_round_trips_compact_contact_thread_and_reply_examples(self) -> None:
        store = MongoMemoryStore(
            uri=None,
            database_name="email_agent",
            namespace_root="custom_agent",
        )
        normalized_email = NormalizedEmail(
            email_id="email-123",
            thread_id="thread-123",
            sender="sender@example.com",
            subject="Need help",
            clean_body="Can you help?",
            summary="Need help with setup.",
            has_attachments=False,
            detected_language="en",
        )

        store.update_after_run(
            {
                "email_id": "email-123",
                "thread_id": "thread-123",
                "normalized_email": normalized_email.model_dump(mode="json"),
                "thread_summary": "Customer asked for setup help.",
                "thread_messages": [
                    {
                        "sender": "support@example.com",
                        "subject": "Previous troubleshooting step",
                    }
                ],
                "draft": {
                    "subject": "Re: Need help",
                    "body": "Sure, here are the steps.",
                    "version": 1,
                },
                "delivery_status": "draft_saved",
                "final_action": "draft_saved",
                "classification": {
                    "intent": "support",
                    "urgency": "low",
                    "risk": "low",
                    "action": "draft",
                    "reason": "Support request",
                    "confidence": 0.95,
                },
            }
        )

        bundle = store.load_memory_bundle(normalized_email)
        contact_item = store.store.get(("custom_agent", "contacts"), "sender@example.com")
        thread_item = store.store.get(("custom_agent", "threads"), "thread-123")
        reply_item = store.store.get(
            ("custom_agent", "reply_examples"),
            "sender@example.com:support",
        )
        draft_history = store.store.search(("custom_agent", "draft_history"))

        self.assertIsNotNone(bundle.contact)
        self.assertEqual(bundle.contact.email, "sender@example.com")
        self.assertEqual(bundle.contact.interaction_count, 1)
        self.assertIsNotNone(bundle.thread)
        self.assertEqual(bundle.thread.thread_id, "thread-123")
        self.assertEqual(bundle.thread.summary, "Customer asked for setup help.")
        self.assertEqual(bundle.thread.recent_messages, ["support@example.com: Previous troubleshooting step"])
        self.assertEqual(bundle.similar_replies, ["Sure, here are the steps."])
        self.assertIsNotNone(contact_item)
        self.assertIsNotNone(thread_item)
        self.assertIsNotNone(reply_item)
        self.assertEqual(len(draft_history), 1)
        assert reply_item is not None
        self.assertEqual(reply_item.value["examples"][0]["body"], "Sure, here are the steps.")

    def test_review_history_is_stored_separately_from_reusable_memory(self) -> None:
        store = MongoMemoryStore(
            uri=None,
            database_name="email_agent",
            namespace_root="custom_agent",
        )
        normalized_email = NormalizedEmail(
            email_id="email-123",
            thread_id="thread-123",
            sender="sender@example.com",
            subject="Need help",
            clean_body="Can you help?",
            summary="Need help with setup.",
            has_attachments=False,
            detected_language="en",
        )
        classification = ClassificationResult(
            intent="support",
            urgency="low",
            risk="high",
            action="human_review",
            reason="Needs approval",
            confidence=0.91,
        )
        draft = DraftReply(
            subject="Re: Need help",
            body="Draft body",
            version=1,
        )

        store.create_review_task(
            normalized_email,
            classification,
            draft,
            review_id="review-123",
        )
        store.update_review_task(
            email_id="email-123",
            decision="approve",
            comments="Looks good",
            reviewer="satya",
            reviewed_at="2026-04-13T10:00:00+00:00",
            review_id="review-123",
        )

        saved = store.store.get(("custom_agent", "review_history"), "review-123")
        bundle = store.load_memory_bundle(normalized_email)

        self.assertIsNotNone(saved)
        assert saved is not None
        self.assertEqual(saved.value["status"], "approve")
        self.assertEqual(saved.value["decision"], "approve")
        self.assertEqual(saved.value["reviewer"], "satya")
        self.assertEqual(bundle.similar_replies, [])

    def test_collection_and_namespace_are_configurable(self) -> None:
        store = MongoMemoryStore(
            uri=None,
            database_name="email_agent",
            collection_name="team_memory",
            namespace_root="gmail_agent",
        )

        self.assertEqual(store.collection_name, "team_memory")
        self.assertEqual(store._contact_namespace(), ("gmail_agent", "contacts"))
        self.assertEqual(store._thread_namespace(), ("gmail_agent", "threads"))
        self.assertEqual(store._reply_examples_namespace(), ("gmail_agent", "reply_examples"))
        self.assertEqual(store._review_history_namespace(), ("gmail_agent", "review_history"))
        self.assertEqual(store._draft_history_namespace(), ("gmail_agent", "draft_history"))

    def test_llm_memory_extraction_merges_preferences_notes_and_business_facts(self) -> None:
        store = MongoMemoryStore(
            uri=None,
            database_name="email_agent",
            namespace_root="custom_agent",
        )
        normalized_email = NormalizedEmail(
            email_id="email-123",
            thread_id="thread-123",
            sender="sender@example.com",
            subject="Need help",
            clean_body="Can you help?",
            summary="Need help with setup.",
            has_attachments=False,
            detected_language="en",
        )
        llm = _LLMStub(
            {
                "importance": "high",
                "preferences": ["prefers concise replies"],
                "notes": ["Often asks setup questions"],
                "thread_summary": "Customer needs setup assistance",
                "business_facts": ["Setup support is available on weekdays"],
            }
        )

        store.update_after_run(
            {
                "email_id": "email-123",
                "thread_id": "thread-123",
                "normalized_email": normalized_email.model_dump(mode="json"),
                "thread_summary": "Fallback summary",
                "draft": {
                    "subject": "Re: Need help",
                    "body": "Sure, here are the steps.",
                    "version": 1,
                },
                "delivery_status": "sent",
                "final_action": "sent",
                "classification": {
                    "intent": "support",
                    "urgency": "low",
                    "risk": "low",
                    "action": "draft",
                    "reason": "Support request",
                    "confidence": 0.95,
                },
            },
            llm=llm,
        )

        contact_item = store.store.get(("custom_agent", "contacts"), "sender@example.com")
        thread_item = store.store.get(("custom_agent", "threads"), "thread-123")
        business_item = store.store.get(("custom_agent", "business_facts"), "global")

        self.assertIsNotNone(contact_item)
        self.assertIsNotNone(thread_item)
        self.assertIsNotNone(business_item)
        assert contact_item is not None
        assert thread_item is not None
        assert business_item is not None
        self.assertEqual(contact_item.value["importance"], "high")
        self.assertEqual(contact_item.value["preferences"], ["prefers concise replies"])
        self.assertEqual(contact_item.value["notes"], ["Often asks setup questions"])
        self.assertEqual(thread_item.value["summary"], "Customer needs setup assistance")
        self.assertEqual(
            business_item.value["facts"],
            ["Setup support is available on weekdays"],
        )


if __name__ == "__main__":
    unittest.main()
