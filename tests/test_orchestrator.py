"""Unit and integration tests for BridgeOrchestrator, pipeline runner, verification, and caching."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "bridge"
sys.path.insert(0, str(BRIDGE))

from envelope import BRIDGE_START, BRIDGE_END
from orchestrator import BridgeOrchestrator


class MockAIExecutor:
    """Simulates AI responses for various roles and stages."""

    def __init__(self):
        self.call_count = 0
        self.prompts_received = []

    async def __call__(self, prompt: str, provider_id: str, new_chat: bool = True, output_file: str | None = None) -> str:
        self.call_count += 1
        self.prompts_received.append({"prompt": prompt, "provider": provider_id, "new_chat": new_chat})

        # Fixer request
        if "Check failed:" in prompt or "Return the corrected function" in prompt:
            return (
                f"{BRIDGE_START}\n"
                "STATUS: COMPLETE\n"
                "SUMMARY: Fixed calculation bug\n"
                "FILE: engine.js\n"
                "```javascript\n"
                "function calculateTotal(items) {\n"
                "    return items.reduce((sum, item) => sum + item.price, 0);\n"
                "}\n"
                "module.exports = { calculateTotal };\n"
                "```\n"
                "NEXT: Re-run check\n"
                f"{BRIDGE_END}"
            )

        # Analyst role
        if "role:analyst" in prompt or "Role: Analyst" in prompt:
            return (
                f"{BRIDGE_START}\n"
                "STATUS: COMPLETE\n"
                "SUMMARY: System health optimal. Manual edits detected in working tree.\n"
                "ANALYSIS:\n"
                "Core business modules intact.\n"
                "All unit tests passing.\n"
                "Manual edits reflect frontend layout adjustments.\n"
                "RISKS:\n"
                "Potential API contract drift.\n"
                "Unpinned dependencies.\n"
                "NEXT_STEPS:\n"
                "Run full regression suite.\n"
                "Finalize release packaging.\n"
                f"{BRIDGE_END}"
            )

        # Truncation test
        if "TRUNCATE_ME" in prompt:
            return (
                f"{BRIDGE_START}\n"
                "STATUS: COMPLETE\n"
                "SUMMARY: Partial response\n"
                "FILE: partial.js\n"
                "```javascript\n"
                "function init() {\n"
                '    console.log("starting");\n'
            )

        # Continuation response
        if prompt.strip() == "Continue exactly from the last line, no repeats, end with the END marker.":
            return (
                '    console.log("finished");\n'
                "    return true;\n"
                "}\n"
                "```\n"
                "NEXT: Done\n"
                f"{BRIDGE_END}"
            )

        # Architect stage
        if "role:architect" in prompt:
            return (
                f"{BRIDGE_START}\n"
                "STATUS: COMPLETE\n"
                "SUMMARY: Designed contract for PulseTask\n"
                "FILE: spec.md\n"
                "```markdown\n"
                "# CONTRACT\n"
                "File: engine.js\n"
                "Exports: calculateTotal(items)\n"
                "```\n"
                "NEXT: Implement engine\n"
                f"{BRIDGE_END}"
            )

        # Engine stage with initial failing bug (for fixer test)
        if "role:engine" in prompt and "FAIL_FIRST" in prompt:
            return (
                f"{BRIDGE_START}\n"
                "STATUS: COMPLETE\n"
                "SUMMARY: Implemented engine with intentional syntax error\n"
                "FILE: engine.js\n"
                "```javascript\n"
                "function calculateTotal(items) {\n"
                "    syntax error here;\n"
                "}\n"
                "```\n"
                f"{BRIDGE_END}"
            )

        # Engine stage passing
        if "role:engine" in prompt:
            return (
                f"{BRIDGE_START}\n"
                "STATUS: COMPLETE\n"
                "SUMMARY: Implemented engine logic\n"
                "FILE: engine.js\n"
                "```javascript\n"
                "function calculateTotal(items) {\n"
                "    return items.reduce((sum, item) => sum + item.price, 0);\n"
                "}\n"
                "module.exports = { calculateTotal };\n"
                "```\n"
                "NEXT: Build UI\n"
                f"{BRIDGE_END}"
            )

        # UI stage
        if "role:ui" in prompt:
            return (
                f"{BRIDGE_START}\n"
                "STATUS: COMPLETE\n"
                "SUMMARY: Built interactive dashboard\n"
                "FILE: index.html\n"
                "```html\n"
                "<!DOCTYPE html>\n"
                "<html>\n"
                "<head><title>PulseTask</title></head>\n"
                "<body><h1>PulseTask Dashboard</h1></body>\n"
                "</html>\n"
                "```\n"
                "NEXT: All stages complete\n"
                f"{BRIDGE_END}"
            )

        # Default fallback
        return (
            f"{BRIDGE_START}\n"
            "STATUS: COMPLETE\n"
            "SUMMARY: Executed standard task\n"
            "FILE: output.txt\n"
            "```text\n"
            "Task output\n"
            "```\n"
            f"{BRIDGE_END}"
        )


class OrchestratorTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_stage_execution_and_verify(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_ai = MockAIExecutor()
            orchestrator = BridgeOrchestrator(project_dir=tmpdir, query_executor=mock_ai)
            orchestrator.handoff_mgr.init_project("Test Project")

            res = await orchestrator.run_stage(
                task="Implement calculation engine",
                provider="chatgpt",
                role="engine",
                out_file="engine.js",
                verify_cmd="node -e \"const m = require('./engine.js'); if (m.calculateTotal([{price: 10}]) !== 10) process.exit(1);\"",
            )

            self.assertEqual(res.status, "COMPLETE")
            self.assertEqual(res.verify, "PASS")
            self.assertEqual(res.out_file, "engine.js")
            self.assertTrue((Path(tmpdir) / "engine.js").is_file())

            # Verify ledger was written
            events = orchestrator.handoff_mgr.read_ledger()
            self.assertTrue(any(e.get("actor") == "chatgpt" and e.get("verify") == "PASS" for e in events))

    async def test_truncation_recovery(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_ai = MockAIExecutor()
            orchestrator = BridgeOrchestrator(project_dir=tmpdir, query_executor=mock_ai)
            orchestrator.handoff_mgr.init_project("Truncation Test")

            res = await orchestrator.run_stage(
                task="TRUNCATE_ME please",
                provider="gemini",
                role="engine",
                out_file="partial.js",
            )

            self.assertEqual(res.status, "COMPLETE")
            # Continuation should have been requested
            self.assertEqual(mock_ai.call_count, 2)
            content = (Path(tmpdir) / "partial.js").read_text(encoding="utf-8")
            self.assertIn("console.log(\"finished\");", content)

    async def test_caching_mechanism(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_ai = MockAIExecutor()
            orchestrator = BridgeOrchestrator(project_dir=tmpdir, query_executor=mock_ai)
            orchestrator.handoff_mgr.init_project("Cache Test")

            # First run: cache miss
            res1 = await orchestrator.run_stage(
                task="Static task",
                provider="claude",
                role="engine",
                out_file="res.txt",
                use_cache=True,
            )
            self.assertEqual(mock_ai.call_count, 1)

            # Second run with exact same task & cache: should hit cache
            res2 = await orchestrator.run_stage(
                task="Static task",
                provider="claude",
                role="engine",
                out_file="res.txt",
                use_cache=True,
            )
            self.assertEqual(mock_ai.call_count, 1)  # No new AI call!
            self.assertEqual(res1.status, res2.status)

    async def test_fixer_loop_recovers_failing_check(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_ai = MockAIExecutor()
            orchestrator = BridgeOrchestrator(project_dir=tmpdir, query_executor=mock_ai)
            orchestrator.handoff_mgr.init_project("Fixer Test")

            res = await orchestrator.run_stage(
                task="FAIL_FIRST: Create engine",
                provider="chatgpt",
                role="engine",
                out_file="engine.js",
                verify_cmd="node -e \"const m = require('./engine.js'); if (typeof m.calculateTotal !== 'function') process.exit(1);\"",
                max_retries=2,
            )

            # Verify that the fixer loop triggered and passed
            self.assertEqual(res.verify, "PASS")
            self.assertGreater(mock_ai.call_count, 1)
            content = (Path(tmpdir) / "engine.js").read_text(encoding="utf-8")
            self.assertIn("function calculateTotal", content)

    async def test_pipeline_runner_three_stages(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_ai = MockAIExecutor()
            orchestrator = BridgeOrchestrator(project_dir=tmpdir, query_executor=mock_ai)
            orchestrator.handoff_mgr.init_project("Pipeline Test")

            pipeline_def = {
                "stages": [
                    {"provider": "claude", "template": "architect", "out": "spec.md"},
                    {
                        "provider": "chatgpt",
                        "template": "engine",
                        "in": "spec.md",
                        "out": "engine.js",
                        "verify": "node -e \"const m = require('./engine.js'); if (typeof m.calculateTotal !== 'function') process.exit(1);\"",
                    },
                    {
                        "provider": "gemini",
                        "template": "ui",
                        "in": ["spec.md", "engine.js"],
                        "out": "index.html",
                        "verify": "node -e \"const fs = require('fs'); if (!fs.readFileSync('index.html').includes('PulseTask')) process.exit(1);\"",
                    },
                ]
            }

            p_file = Path(tmpdir) / "pipeline.json"
            p_file.write_text(json.dumps(pipeline_def, indent=2), encoding="utf-8")

            results = await orchestrator.run_pipeline(p_file)
            self.assertEqual(len(results), 3)
            self.assertEqual(results[0].out_file, "spec.md")
            self.assertEqual(results[1].out_file, "engine.js")
            self.assertEqual(results[2].out_file, "index.html")
            for r in results:
                self.assertEqual(r.status, "COMPLETE")
                self.assertIn(r.verify, ("PASS", "none"))

            # All 3 files exist on disk
            self.assertTrue((Path(tmpdir) / "spec.md").is_file())
            self.assertTrue((Path(tmpdir) / "engine.js").is_file())
            self.assertTrue((Path(tmpdir) / "index.html").is_file())

    async def test_handoff_command_analyst(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_ai = MockAIExecutor()
            orchestrator = BridgeOrchestrator(project_dir=tmpdir, query_executor=mock_ai)
            orchestrator.handoff_mgr.init_project("Handoff Test")

            # Create manual edit
            (Path(tmpdir) / "manual_edit.py").write_text("# user change\n", encoding="utf-8")

            one_line = await orchestrator.handoff_command("claude", goal="Ship release 1.0")
            self.assertIn("OK handoff to=claude status=COMPLETE", one_line)

            # Verify that prompt sent to Claude mentioned the manual edit
            prompt_sent = mock_ai.prompts_received[-1]["prompt"]
            self.assertIn("manual_edit.py", prompt_sent)

            # Check ledger has analyst event
            ledger = orchestrator.handoff_mgr.read_ledger()
            analyst_events = [e for e in ledger if e.get("role") == "analyst"]
            self.assertTrue(len(analyst_events) > 0)


if __name__ == "__main__":
    unittest.main()
