from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from email_agent.mailbox import (
    LocalMailboxClient,
    _gmail_fetch_window,
    _gmail_outcome_label_name,
    _sort_emails_newest_first,
)
from email_agent.models import EmailMessage


def _iso(year: int, month: int, day: int, hour: int, minute: int) -> str:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc).isoformat()


class MailboxOrderingTests(unittest.TestCase):
    def test_gmail_outcome_label_name_maps_expected_outcomes(self) -> None:
        self.assertEqual(_gmail_outcome_label_name("sent", "AI"), "AI-Sent")
        self.assertEqual(
            _gmail_outcome_label_name("pending_human_review", "Ops"),
            "Ops-Needs-Human",
        )
        self.assertIsNone(_gmail_outcome_label_name("unknown", "AI"))

    def test_gmail_fetch_window_bounds_recent_scan(self) -> None:
        self.assertEqual(_gmail_fetch_window(1), 5)
        self.assertEqual(_gmail_fetch_window(5), 25)
        self.assertEqual(_gmail_fetch_window(30), 100)

    def test_sort_emails_newest_first_orders_descending(self) -> None:
        older = EmailMessage(
            id="older",
            from_address="old@example.com",
            to_address="you@example.com",
            subject="Older",
            body="old",
            received_at=datetime(2026, 3, 27, 8, 0, tzinfo=timezone.utc),
        )
        newer = EmailMessage(
            id="newer",
            from_address="new@example.com",
            to_address="you@example.com",
            subject="Newer",
            body="new",
            received_at=datetime(2026, 3, 27, 9, 0, tzinfo=timezone.utc),
        )

        ordered = _sort_emails_newest_first([older, newer])

        self.assertEqual([email.id for email in ordered], ["newer", "older"])

    def test_sort_emails_newest_first_is_stable_for_same_timestamp(self) -> None:
        first = EmailMessage(
            id="first",
            from_address="first@example.com",
            to_address="you@example.com",
            subject="First",
            body="first",
            received_at=datetime(2026, 3, 27, 9, 0, tzinfo=timezone.utc),
        )
        second = EmailMessage(
            id="second",
            from_address="second@example.com",
            to_address="you@example.com",
            subject="Second",
            body="second",
            received_at=datetime(2026, 3, 27, 9, 0, tzinfo=timezone.utc),
        )

        ordered = _sort_emails_newest_first([first, second])

        self.assertEqual([email.id for email in ordered], ["first", "second"])

    def test_local_mailbox_fetch_unread_sorts_before_limiting(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            inbox_path = temp_path / "inbox.json"
            outbox_path = temp_path / "outbox.json"
            inbox_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "older",
                            "from_address": "older@example.com",
                            "to_address": "you@example.com",
                            "subject": "Older",
                            "body": "older body",
                            "received_at": _iso(2026, 3, 27, 8, 0),
                            "is_unread": True,
                        },
                        {
                            "id": "newest",
                            "from_address": "newest@example.com",
                            "to_address": "you@example.com",
                            "subject": "Newest",
                            "body": "newest body",
                            "received_at": _iso(2026, 3, 27, 10, 0),
                            "is_unread": True,
                        },
                        {
                            "id": "middle",
                            "from_address": "middle@example.com",
                            "to_address": "you@example.com",
                            "subject": "Middle",
                            "body": "middle body",
                            "received_at": _iso(2026, 3, 27, 9, 0),
                            "is_unread": True,
                        },
                        {
                            "id": "read",
                            "from_address": "read@example.com",
                            "to_address": "you@example.com",
                            "subject": "Read",
                            "body": "already handled",
                            "received_at": _iso(2026, 3, 27, 11, 0),
                            "is_unread": False,
                        },
                    ]
                ),
                encoding="utf-8",
            )
            outbox_path.write_text("[]", encoding="utf-8")
            mailbox = LocalMailboxClient(inbox_path, outbox_path)

            emails = mailbox.fetch_unread(limit=2)

            self.assertEqual([email.id for email in emails], ["newest", "middle"])


if __name__ == "__main__":
    unittest.main()
