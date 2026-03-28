from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from email_agent.services import agent_service


class ProgressSnapshotTests(unittest.TestCase):
    def test_collect_progress_snapshot_returns_idle_defaults_without_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            progress_path = Path(tmpdir) / "run_progress.json"
            with patch.object(agent_service, "PROGRESS_PATH", progress_path):
                payload = agent_service.collect_progress_snapshot()

        self.assertEqual(payload["status"], "idle")
        self.assertEqual(payload["processed_count"], 0)
        self.assertEqual(payload["total_emails"], 0)
        self.assertEqual(payload["recent_results"], [])
        self.assertIsNone(payload["current_email"])

    def test_collect_progress_snapshot_reads_saved_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            progress_path = Path(tmpdir) / "run_progress.json"
            progress_path.write_text(
                json.dumps(
                    {
                        "status": "running",
                        "backend": "gmail",
                        "total_emails": 3,
                        "processed_count": 1,
                        "percent_complete": 33,
                        "current_email": {"subject": "Live progress"},
                        "recent_results": [{"subject": "Done"}],
                        "started_at": "2026-03-28T00:00:00+00:00",
                        "updated_at": "2026-03-28T00:01:00+00:00",
                        "error_message": None,
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(agent_service, "PROGRESS_PATH", progress_path):
                payload = agent_service.collect_progress_snapshot()

        self.assertEqual(payload["status"], "running")
        self.assertEqual(payload["backend"], "gmail")
        self.assertEqual(payload["processed_count"], 1)
        self.assertEqual(payload["percent_complete"], 33)
        self.assertEqual(payload["current_email"]["subject"], "Live progress")


if __name__ == "__main__":
    unittest.main()
