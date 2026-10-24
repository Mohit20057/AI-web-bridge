"""Unit tests for the handoff and ledger management system."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "bridge"
sys.path.insert(0, str(BRIDGE))

from handoff import HandoffManager, HANDOFF_MAX_CHARS


class HandoffTests(unittest.TestCase):
    def test_init_creates_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = HandoffManager(tmpdir)
            msg = mgr.init_project("Test Goal")
            self.assertIn("Initialized .bridge", msg)
            self.assertTrue(mgr.ledger_path.exists())
            self.assertTrue(mgr.handoff_path.exists())
            self.assertTrue(mgr.checkpoint_path.exists())

            handoff = mgr.read_handoff()
            self.assertIn("Test Goal", handoff)
            self.assertIn("## Goal", handoff)
            self.assertIn("## Current state", handoff)

    def test_auto_sync_detects_manual_file_creation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = HandoffManager(tmpdir)
            mgr.init_project("Sync Test")

            # Create a manual file
            manual_file = Path(tmpdir) / "manual_code.py"
            manual_file.write_text("print('user edited this')\n", encoding="utf-8")

            sync_res = mgr.auto_sync()
            self.assertIsNotNone(sync_res)
            self.assertIn("Auto-synced manual edits", sync_res)

            ledger = mgr.read_ledger()
            self.assertTrue(any(e.get("actor") == "user" for e in ledger))

            handoff = mgr.read_handoff()
            self.assertIn("Manual edit", handoff)

    def test_compaction_under_hard_cap(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = HandoffManager(tmpdir)
            mgr.init_project("Compaction Test")

            # Add 25 large ledger events
            for i in range(25):
                mgr.record_job(
                    job_id=f"job_{i}",
                    actor="claude",
                    role="engine",
                    action="write",
                    files=[f"file_{i}.py"],
                    verify="PASS",
                    status="COMPLETE",
                    summary="A" * 300,
                    next_step="Next step " + str(i),
                )

            handoff = mgr.read_handoff()
            self.assertLessEqual(len(handoff), HANDOFF_MAX_CHARS)
            self.assertIn("earlier ledger events compacted", handoff)

    def test_status_max_15_lines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = HandoffManager(tmpdir)
            mgr.init_project("Status Test")
            status = mgr.get_status_summary()
            lines = status.splitlines()
            self.assertLessEqual(len(lines), 15)
            self.assertIn("## Current state", status)


if __name__ == "__main__":
    unittest.main()
