from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from email_agent.services.review_service import apply_review_decision, list_review_items


class ReviewServiceTests(unittest.TestCase):
    def test_list_review_items_normalizes_legacy_rows_and_filters_pending(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            review_path = Path(temp_dir) / "review_queue.json"
            review_path.write_text(
                json.dumps(
                    [
                        {
                            "email_id": "one",
                            "subject": "Legacy row",
                            "from_address": "sender@example.com",
                            "reason": "Needs review",
                            "created_at": "2026-03-28T10:00:00+00:00",
                        },
                        {
                            "review_id": "review-two",
                            "email_id": "two",
                            "subject": "Resolved row",
                            "from_address": "sender@example.com",
                            "reason": "Already resolved",
                            "status": "approve",
                            "created_at": "2026-03-28T09:00:00+00:00",
                        },
                    ]
                ),
                encoding="utf-8",
            )

            items = list_review_items(status="pending", path=review_path)

            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["email_id"], "one")
            self.assertEqual(items[0]["status"], "pending")
            self.assertTrue(items[0]["review_id"].startswith("one:"))
            self.assertFalse(items[0]["resumable"])
            self.assertTrue(items[0]["legacy"])

    def test_apply_review_decision_updates_row_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            review_path = Path(temp_dir) / "review_queue.json"
            review_path.write_text(
                json.dumps(
                    [
                        {
                            "review_id": "review-one",
                            "email_id": "one",
                            "subject": "Pending row",
                            "from_address": "sender@example.com",
                            "reason": "Needs review",
                            "status": "pending",
                            "created_at": "2026-03-28T10:00:00+00:00",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            item = apply_review_decision(
                "review-one",
                decision="approve",
                comments="Looks good.",
                reviewer="satya",
                path=review_path,
            )

            self.assertEqual(item["status"], "approve")
            self.assertEqual(item["decision"], "approve")
            self.assertEqual(item["comments"], "Looks good.")
            self.assertEqual(item["reviewer"], "satya")

            stored = json.loads(review_path.read_text(encoding="utf-8"))
            self.assertEqual(stored[0]["status"], "approve")


if __name__ == "__main__":
    unittest.main()
