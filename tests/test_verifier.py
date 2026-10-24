"""Unit tests for verification commands, patch application, and fallback."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "bridge"
sys.path.insert(0, str(BRIDGE))

from verifier import (
    apply_patch_or_fallback,
    apply_unified_diff,
    format_fixer_prompt,
    run_verification,
)


class VerifierTests(unittest.TestCase):
    def test_run_verification_pass_and_fail(self):
        # Passing command
        passed, out = run_verification("python -c \"print('ok')\"")
        self.assertTrue(passed)

        # Failing command
        passed, out = run_verification("python -c \"raise ValueError('boom')\"")
        self.assertFalse(passed)
        self.assertIn("ValueError", out)
        self.assertLessEqual(len(out.splitlines()), 15)

    def test_apply_unified_diff_success(self):
        orig = "def add(a, b):\n    return a - b\n"
        diff = """--- a/math.py
+++ b/math.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a - b
+    return a + b
"""
        patched = apply_unified_diff(orig, diff)
        self.assertIsNotNone(patched)
        self.assertIn("return a + b", patched)

    def test_apply_patch_or_fallback_full_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "calc.py"
            file_path.write_text("broken code", encoding="utf-8")

            # Fallback complete code block
            fix = """Here is the complete file:
```python
def add(x, y):
    return x + y
```
"""
            success = apply_patch_or_fallback(file_path, fix)
            self.assertTrue(success)
            content = file_path.read_text(encoding="utf-8")
            self.assertEqual(content, "def add(x, y):\n    return x + y")

    def test_fixer_prompt_format(self):
        prompt = format_fixer_prompt("pytest tests/", "AssertionError: 2 != 3", 1, 2)
        self.assertIn("Check failed: pytest tests/", prompt)
        self.assertIn("Attempt 1/2.", prompt)
        self.assertIn("unified diff", prompt)


if __name__ == "__main__":
    unittest.main()
