"""End-to-end CLI command tests for AI Web Bridge lifecycle and flags."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE_SCRIPT = ROOT / "bridge" / "argon_bridge.py"
PYTHON_EXE = ROOT / ".venv" / "Scripts" / "python.exe"


class CliCommandTests(unittest.TestCase):
    def run_cli(self, args: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
        cmd = [str(PYTHON_EXE), str(BRIDGE_SCRIPT)] + args
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return proc.returncode, proc.stdout, proc.stderr

    def test_existing_flags_backward_compatibility(self):
        # --list-providers
        code, stdout, stderr = self.run_cli(["--list-providers"])
        self.assertEqual(code, 0)
        self.assertIn("gemini", stdout)
        self.assertIn("claude", stdout)
        self.assertIn("chatgpt", stdout)

    def test_bridge_init_sync_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # 1. bridge init
            code, stdout, stderr = self.run_cli(["init", "--goal", "Build test microservice"], cwd=tmppath)
            self.assertEqual(code, 0)
            self.assertIn("Initialized .bridge", stdout)
            self.assertTrue((tmppath / ".bridge" / "HANDOFF.md").is_file())
            self.assertTrue((tmppath / ".bridge" / "ledger.jsonl").is_file())

            # 2. bridge status
            code, stdout, stderr = self.run_cli(["status"], cwd=tmppath)
            self.assertEqual(code, 0)
            self.assertIn("## Current state", stdout)
            self.assertIn("## Next step", stdout)
            self.assertLessEqual(len(stdout.splitlines()), 15)

            # 3. Create a manual edit
            (tmppath / "new_feature.py").write_text("def feature(): return True\n", encoding="utf-8")

            # 4. bridge sync
            code, stdout, stderr = self.run_cli(["sync"], cwd=tmppath)
            self.assertEqual(code, 0)
            self.assertIn("Auto-synced manual edits", stdout)

            # Check ledger
            ledger_lines = (tmppath / ".bridge" / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
            user_events = [json.loads(line) for line in ledger_lines if json.loads(line).get("actor") == "user"]
            self.assertTrue(len(user_events) > 0)


if __name__ == "__main__":
    unittest.main()
