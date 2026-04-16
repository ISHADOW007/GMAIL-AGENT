from __future__ import annotations

import unittest
from datetime import datetime, timezone

from email_agent.graph.nodes.load_thread import make_load_thread_node
from email_agent.models import EmailMessage
from email_agent.services.thread_service import (
    serialize_thread_messages,
    summarize_thread_messages,
)


class ThreadLoadingTests(unittest.TestCase):
    def test_load_thread_node_populates_summary_and_messages(self) -> None:
        current_email = EmailMessage(
            id="current",
            thread_id="thread-1",
            from_address="sender@example.com",
            to_address="you@example.com",
            subject="Current email",
            body="Current body",
            received_at=datetime(2026, 3, 27, 11, 0, tzinfo=timezone.utc),
        )
        prior_messages = [
            EmailMessage(
                id="reply-1",
                thread_id="thread-1",
                from_address="you@example.com",
                to_address="sender@example.com",
                subject="Oldest prior reply",
                body="First message in the thread.",
                received_at=datetime(2026, 3, 27, 9, 0, tzinfo=timezone.utc),
            ),
            EmailMessage(
                id="reply-2",
                thread_id="thread-1",
                from_address="sender@example.com",
                to_address="you@example.com",
                subject="Newest prior reply",
                body="Latest message in the thread.",
                received_at=datetime(2026, 3, 27, 10, 0, tzinfo=timezone.utc),
            ),
        ]

        class StubMailbox:
            def fetch_thread_messages(self, thread_id: str | None, current_email_id: str | None = None):
                self.thread_id = thread_id
                self.current_email_id = current_email_id
                return prior_messages

        mailbox = StubMailbox()
        node = make_load_thread_node(mailbox)

        result = node({"email": current_email.model_dump(mode="json")})

        self.assertEqual(mailbox.thread_id, "thread-1")
        self.assertEqual(mailbox.current_email_id, "current")
        self.assertEqual(
            [item["email_id"] for item in result["thread_messages"]],
            ["reply-1", "reply-2"],
        )
        self.assertIn("Latest message in the thread.", result["thread_summary"])

    def test_thread_service_helpers_return_recent_serialized_messages(self) -> None:
        messages = [
            EmailMessage(
                id=f"reply-{index}",
                thread_id="thread-1",
                from_address="sender@example.com",
                to_address="you@example.com",
                subject=f"Reply {index}",
                body=f"Body {index}",
                received_at=datetime(2026, 3, 27, index, 0, tzinfo=timezone.utc),
            )
            for index in range(1, 7)
        ]

        serialized = serialize_thread_messages(messages, limit=3)
        summary = summarize_thread_messages(messages, limit=2)

        self.assertEqual([item["email_id"] for item in serialized], ["reply-4", "reply-5", "reply-6"])
        self.assertIn("Body 5", summary)
        self.assertIn("Body 6", summary)


if __name__ == "__main__":
    unittest.main()
