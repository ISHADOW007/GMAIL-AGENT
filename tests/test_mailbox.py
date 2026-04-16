from __future__ import annotations

import unittest
from datetime import datetime, timezone

from email_agent.mailbox import (
    _gmail_fetch_window,
    _gmail_outcome_label_name,
    _sort_emails_newest_first,
)
from email_agent.models import EmailMessage


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


if __name__ == "__main__":
    unittest.main()
