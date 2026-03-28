from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from email_agent.services.review_resume_service import approve_review, revise_review


class _MailboxStub:
    def __init__(self) -> None:
        self.saved: list[tuple[str, str]] = []
        self.sent: list[tuple[str, str]] = []
        self.processed: list[str] = []

    def save_draft(self, original_email, draft) -> None:
        self.saved.append((original_email.id, draft.subject))

    def send_email(self, original_email, draft) -> None:
        self.sent.append((original_email.id, draft.subject))

    def mark_processed(self, email_id: str, outcome: str | None = None) -> None:
        self.processed.append((email_id, outcome))


class _MemoryStoreStub:
    def __init__(self) -> None:
        self.enabled = False
        self.updated_states: list[dict] = []

    def update_after_run(self, state: dict) -> None:
        self.updated_states.append(dict(state))


def _review_item_with_state() -> dict:
    return {
        "review_id": "review-123",
        "email_id": "email-123",
        "thread_id": "thread-123",
        "from_address": "sender@example.com",
        "subject": "Need help",
        "reason": "Needs human review",
        "status": "pending",
        "draft": {
            "subject": "Re: Need help",
            "body": "Draft body",
            "version": 1,
        },
        "state_snapshot": {
            "email": {
                "id": "email-123",
                "from_address": "sender@example.com",
                "to_address": "you@example.com",
                "subject": "Need help",
                "body": "Can you help?",
                "received_at": datetime(2026, 3, 28, 10, 0, tzinfo=timezone.utc).isoformat(),
            },
            "email_id": "email-123",
            "thread_id": "thread-123",
            "normalized_email": {
                "email_id": "email-123",
                "thread_id": "thread-123",
                "sender": "sender@example.com",
                "subject": "Need help",
                "clean_body": "Can you help?",
                "summary": "Can you help?",
                "has_attachments": False,
                "detected_language": "en",
            },
            "classification": {
                "intent": "support",
                "urgency": "low",
                "risk": "low",
                "action": "draft",
                "reason": "Support request",
                "confidence": 0.92,
            },
            "safety_result": {
                "safe_to_send": True,
                "needs_human": False,
                "issues": [],
                "policy_tags": [],
            },
            "draft": {
                "subject": "Re: Need help",
                "body": "Draft body",
                "version": 1,
            },
        },
    }


class ReviewResumeServiceTests(unittest.TestCase):
    def test_approve_review_continues_to_delivery_and_processing(self) -> None:
        mailbox = _MailboxStub()
        memory_store = _MemoryStoreStub()
        captured: dict = {}

        def _apply_review_decision(*args, **kwargs):
            captured["kwargs"] = kwargs
            return {"status": "approve", **kwargs.get("extra_updates", {})}

        with patch(
            "email_agent.services.review_resume_service.get_review_item",
            return_value=_review_item_with_state(),
        ), patch(
            "email_agent.services.review_resume_service._build_runtime",
            return_value=(SimpleNamespace(auto_send=False), mailbox, memory_store, None),
        ), patch(
            "email_agent.services.review_resume_service.apply_review_decision",
            side_effect=_apply_review_decision,
        ):
            result = approve_review("review-123", comments="Looks good.", reviewer="satya")

        self.assertEqual(mailbox.saved, [("email-123", "Re: Need help")])
        self.assertEqual(mailbox.sent, [])
        self.assertEqual(mailbox.processed, [("email-123", "draft_saved")])
        self.assertEqual(result["delivery_status"], "draft_saved")
        self.assertTrue(result["resumed"])
        self.assertEqual(captured["kwargs"]["decision"], "approve")

    def test_revise_review_updates_draft_and_keeps_item_pending(self) -> None:
        memory_store = _MemoryStoreStub()

        def _update_review_item(*args, **kwargs):
            return kwargs["updates"]

        def _make_revise_reply_node(_llm):
            def _revise(state: dict) -> dict:
                return {
                    "draft": {
                        "subject": "Re: Need help (revised)",
                        "body": "Updated body",
                        "version": 2,
                    }
                }

            return _revise

        with patch(
            "email_agent.services.review_resume_service.get_review_item",
            return_value=_review_item_with_state(),
        ), patch(
            "email_agent.services.review_resume_service._build_runtime",
            return_value=(SimpleNamespace(auto_send=False), None, memory_store, object()),
        ), patch(
            "email_agent.services.review_resume_service.make_revise_reply_node",
            side_effect=_make_revise_reply_node,
        ), patch(
            "email_agent.services.review_resume_service.update_review_item",
            side_effect=_update_review_item,
        ):
            result = revise_review("review-123", comments="Make it warmer.", reviewer="satya")

        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["decision"], "pending")
        self.assertEqual(result["draft"]["subject"], "Re: Need help (revised)")
        self.assertEqual(result["reviewer"], "satya")
        self.assertEqual(result["review_history"][0]["decision"], "revise")


if __name__ == "__main__":
    unittest.main()
