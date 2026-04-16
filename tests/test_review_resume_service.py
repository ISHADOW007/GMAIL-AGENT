from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from email_agent.services.review_resume_service import (
    approve_review,
    reject_review,
    revise_review,
)


class _MailboxStub:
    def __init__(self) -> None:
        self.saved: list[tuple[str, str]] = []
        self.sent: list[tuple[str, str]] = []
        self.processed: list[tuple[str, str | None]] = []

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

    def update_after_run(self, state: dict, *, llm=None) -> None:
        self.updated_states.append({"state": dict(state), "llm": llm})


class _ShortTermMemoryStub:
    def build_config(self, thread_id: str, checkpoint_id: str | None = None) -> dict:
        config = {"configurable": {"thread_id": thread_id}}
        if checkpoint_id:
            config["configurable"]["checkpoint_id"] = checkpoint_id
        return config


class _InterruptingGraphStub:
    def __init__(self, result: dict) -> None:
        self.result = result
        self.invocations: list[tuple[object, dict]] = []

    def get_state(self, config: dict) -> SimpleNamespace:
        return SimpleNamespace(values={"review_id": "review-123"}, next=("human_review",))

    def invoke(self, command, config: dict | None = None) -> dict:
        self.invocations.append((command, config or {}))
        return dict(self.result)


class _LegacyGraphStub:
    def __init__(self) -> None:
        self.updated: list[tuple[dict, dict, str | None]] = []

    def get_state(self, config: dict) -> SimpleNamespace:
        return SimpleNamespace(values={}, next=())

    def update_state(self, config: dict, values: dict, as_node: str | None = None) -> dict:
        self.updated.append((config, values, as_node))
        return config


def _review_item_with_state() -> dict:
    return {
        "review_id": "review-123",
        "email_id": "email-123",
        "thread_id": "thread-123",
        "checkpoint_thread_id": "email-123",
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


def _review_item_without_draft() -> dict:
    item = _review_item_with_state()
    item["draft"] = None
    item["state_snapshot"] = {
        **item["state_snapshot"],
        "draft": None,
    }
    return item


class ReviewResumeServiceTests(unittest.TestCase):
    def test_approve_review_resumes_paused_langgraph_run(self) -> None:
        graph = _InterruptingGraphStub(
            {
                "delivery_status": "sent",
                "final_action": "sent",
                "draft": {
                    "subject": "Re: Need help",
                    "body": "Draft body",
                    "version": 1,
                },
            }
        )
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
            return_value=(
                SimpleNamespace(auto_send=True),
                _MailboxStub(),
                memory_store,
                _ShortTermMemoryStub(),
                graph,
                None,
            ),
        ), patch(
            "email_agent.services.review_resume_service.apply_review_decision",
            side_effect=_apply_review_decision,
        ):
            result = approve_review("review-123", comments="Looks good.", reviewer="satya")

        command, config = graph.invocations[0]
        self.assertEqual(command.resume["decision"], "approve")
        self.assertEqual(command.resume["comments"], "Looks good.")
        self.assertEqual(config["configurable"]["thread_id"], "email-123")
        self.assertEqual(result["delivery_status"], "sent")
        self.assertTrue(result["resumed"])
        self.assertEqual(captured["kwargs"]["decision"], "approve")

    def test_reject_review_resumes_paused_langgraph_run(self) -> None:
        graph = _InterruptingGraphStub(
            {
                "delivery_status": "rejected_after_review",
                "final_action": "reject",
                "draft": {
                    "subject": "Re: Need help",
                    "body": "Draft body",
                    "version": 1,
                },
            }
        )
        memory_store = _MemoryStoreStub()
        captured: dict = {}

        def _apply_review_decision(*args, **kwargs):
            captured["kwargs"] = kwargs
            return {"status": "reject", **kwargs.get("extra_updates", {})}

        with patch(
            "email_agent.services.review_resume_service.get_review_item",
            return_value=_review_item_with_state(),
        ), patch(
            "email_agent.services.review_resume_service._build_runtime",
            return_value=(
                SimpleNamespace(auto_send=False),
                _MailboxStub(),
                memory_store,
                _ShortTermMemoryStub(),
                graph,
                None,
            ),
        ), patch(
            "email_agent.services.review_resume_service.apply_review_decision",
            side_effect=_apply_review_decision,
        ):
            result = reject_review("review-123", comments="Do not send.", reviewer="satya")

        command, _ = graph.invocations[0]
        self.assertEqual(command.resume["decision"], "reject")
        self.assertEqual(result["delivery_status"], "rejected_after_review")
        self.assertEqual(result["final_action"], "reject")
        self.assertEqual(captured["kwargs"]["decision"], "reject")

    def test_revise_review_resumes_langgraph_and_keeps_item_pending(self) -> None:
        graph = _InterruptingGraphStub(
            {
                "delivery_status": "pending_human_review",
                "final_action": "human_review",
                "draft": {
                    "subject": "Re: Need help (revised)",
                    "body": "Updated body",
                    "version": 2,
                },
                "__interrupt__": ("waiting",),
            }
        )
        memory_store = _MemoryStoreStub()
        updated_review_item = {
            **_review_item_with_state(),
            "draft": {
                "subject": "Re: Need help (revised)",
                "body": "Updated body",
                "version": 2,
            },
        }

        def _update_review_item(*args, **kwargs):
            return kwargs["updates"]

        with patch(
            "email_agent.services.review_resume_service.get_review_item",
            side_effect=[_review_item_with_state(), updated_review_item],
        ), patch(
            "email_agent.services.review_resume_service._build_runtime",
            return_value=(
                SimpleNamespace(auto_send=False),
                _MailboxStub(),
                memory_store,
                _ShortTermMemoryStub(),
                graph,
                None,
            ),
        ), patch(
            "email_agent.services.review_resume_service.update_review_item",
            side_effect=_update_review_item,
        ):
            result = revise_review("review-123", comments="Make it warmer.", reviewer="satya")

        command, _ = graph.invocations[0]
        self.assertEqual(command.resume["decision"], "revise")
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["decision"], "pending")
        self.assertEqual(result["draft"]["subject"], "Re: Need help (revised)")
        self.assertEqual(result["review_history"][0]["decision"], "revise")

    def test_approve_review_without_checkpoint_falls_back_to_legacy_flow(self) -> None:
        mailbox = _MailboxStub()
        memory_store = _MemoryStoreStub()
        graph = _LegacyGraphStub()
        captured: dict = {}

        def _apply_review_decision(*args, **kwargs):
            captured["kwargs"] = kwargs
            return {"status": "approve", **kwargs.get("extra_updates", {})}

        with patch(
            "email_agent.services.review_resume_service.get_review_item",
            return_value=_review_item_without_draft(),
        ), patch(
            "email_agent.services.review_resume_service._build_runtime",
            return_value=(
                SimpleNamespace(auto_send=False),
                mailbox,
                memory_store,
                _ShortTermMemoryStub(),
                graph,
                None,
            ),
        ), patch(
            "email_agent.services.review_resume_service.apply_review_decision",
            side_effect=_apply_review_decision,
        ):
            result = approve_review("review-123", comments="Safe to close.", reviewer="satya")

        self.assertEqual(mailbox.saved, [])
        self.assertEqual(mailbox.sent, [])
        self.assertEqual(mailbox.processed, [("email-123", "approved_without_delivery")])
        self.assertEqual(result["delivery_status"], "approved_without_delivery")
        self.assertEqual(result["final_action"], "approved")
        self.assertTrue(result["resumed"])
        self.assertEqual(captured["kwargs"]["decision"], "approve")


if __name__ == "__main__":
    unittest.main()
