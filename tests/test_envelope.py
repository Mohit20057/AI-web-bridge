"""Unit tests for prompt envelope builder, extraction, and truncation stitching."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "bridge"
sys.path.insert(0, str(BRIDGE))

from envelope import (
    BRIDGE_START,
    BRIDGE_END,
    build_prompt_envelope,
    extract_bridge_payload,
    stitch_continuation,
)


class EnvelopeTests(unittest.TestCase):
    def test_build_prompt_envelope_structure(self):
        env = build_prompt_envelope(
            job_id="job123",
            task="Build a Fibonacci generator",
            role="engine",
            stage_num=2,
            total_stages=3,
            handoff_content="## Current state\nSetup complete.",
            previous_output="spec v1.0",
        )
        self.assertIn("[BRIDGE JOB] id:job123 | stage 2/3 | role:engine", env)
        self.assertIn("# TASK\nBuild a Fibonacci generator", env)
        self.assertIn("# HANDOFF (project state)\n## Current state\nSetup complete.", env)
        self.assertIn("<<<PREV_START>>>\nspec v1.0\n<<<PREV_END>>>", env)
        self.assertIn(BRIDGE_START, env)
        self.assertIn(BRIDGE_END, env)

    def test_extract_payload_complete(self):
        sample = f"""
Some web chat greeting hello!
{BRIDGE_START}
STATUS: COMPLETE
SUMMARY: Implemented Fibonacci sequence
ASSUMPTIONS: Python 3.10+
FILE: fib.py
```python
def fib(n):
    return [0, 1] if n == 2 else []
```
NEXT: Run unit tests
{BRIDGE_END}
Trailing web page garbage
"""
        res = extract_bridge_payload(sample)
        self.assertEqual(res.status, "COMPLETE")
        self.assertEqual(res.summary, "Implemented Fibonacci sequence")
        self.assertEqual(res.assumptions, "Python 3.10+")
        self.assertEqual(len(res.files), 1)
        self.assertEqual(res.files[0].filename, "fib.py")
        self.assertEqual(res.files[0].lang, "python")
        self.assertIn("def fib(n):", res.files[0].content)
        self.assertEqual(res.next_step, "Run unit tests")
        self.assertFalse(res.truncated)

    def test_truncation_detection_and_stitching(self):
        partial = f"""
{BRIDGE_START}
STATUS: COMPLETE
SUMMARY: Writing long file
FILE: app.js
```javascript
function main() {{
    console.log("hello");
"""
        res1 = extract_bridge_payload(partial)
        self.assertTrue(res1.truncated)
        self.assertEqual(res1.status, "TRUNCATED")

        continuation = """
    console.log("hello");
    return true;
}
```
NEXT: Done
<<<BRIDGE_END>>>
"""
        stitched = stitch_continuation(partial, continuation)
        res2 = extract_bridge_payload(stitched)
        self.assertFalse(res2.truncated)
        self.assertEqual(res2.status, "COMPLETE")
        self.assertEqual(len(res2.files), 1)
        self.assertIn("return true;", res2.files[0].content)


if __name__ == "__main__":
    unittest.main()
