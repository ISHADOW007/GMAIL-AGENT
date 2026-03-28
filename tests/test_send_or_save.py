from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from email_agent.graph.nodes.send_or_save import make_send_or_save_node


class RecordingMailbox:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self.saved: list[tuple[str, str]] = []

    def fetch_unread(self, limit: int):  # pragma: no cover - not used in these tests
        raise NotImplementedError

    def save_draft(self, original_email, draft) -> None:
        self.saved.append((original_email.id, draft.subject))

    def send_email(self, original_email, draft) -> None:
        self.sent.append((original_email.id, draft.subject))

    def mark_processed(self, email_id: str) -> None:  # pragma: no cover - not used
        raise NotImplementedError

    def flag_for_human_review(self, original_email, reason: str) -> None:  # pragma: no cover - not used
        raise NotImplementedError


def _state(**classification_overrides: object) -> dict:
    return {
        "email": {
            "id": "email-123",
            "from_address": "sender@example.com",
            "to_address": "you@example.com",
            "subject": "Subject",
            "body": "Body",
            "received_at": datetime(2026, 3, 27, 12, 0, tzinfo=timezone.utc).isoformat(),
        },
        "draft": {
            "subject": "Re: Subject",
            "body": "Reply body",
            "version": 1,
        },
        "safety_result": {
            "safe_to_send": True,
            "needs_human": False,
            "issues": [],
            "policy_tags": [],
        },
        "classification": {
            "intent": "sales",
            "urgency": "low",
            "risk": "low",
            "action": "draft",
            "reason": "Normal reply flow.",
            "confidence": 0.9,
            **classification_overrides,
        },
    }


class SendOrSaveGuardTests(unittest.TestCase):
    def test_ignore_action_is_not_sent_or_saved(self) -> None:
        mailbox = RecordingMailbox()
        node = make_send_or_save_node(mailbox, SimpleNamespace(auto_send=True))

        result = node(_state(intent="other", action="ignore"))

        self.assertEqual(result["delivery_status"], "ignored")
        self.assertEqual(mailbox.sent, [])
        self.assertEqual(mailbox.saved, [])

    def test_safe_auto_send_still_sends(self) -> None:
        mailbox = RecordingMailbox()
        node = make_send_or_save_node(mailbox, SimpleNamespace(auto_send=True))

        result = node(_state())

        self.assertEqual(result["delivery_status"], "sent")
        self.assertEqual(mailbox.sent, [("email-123", "Re: Subject")])
        self.assertEqual(mailbox.saved, [])


if __name__ == "__main__":
    unittest.main()
