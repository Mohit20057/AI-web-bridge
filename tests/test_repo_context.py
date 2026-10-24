"""Unit tests for repository context and signature extraction."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "bridge"
sys.path.insert(0, str(BRIDGE))

from repo_context import (
    build_repo_context,
    extract_js_ts_signatures,
    extract_python_signatures,
    generate_file_tree,
)


class RepoContextTests(unittest.TestCase):
    def test_python_signature_extraction(self):
        code = """
class Calculator(Base):
    def add(self, a: int, b: int) -> int:
        return a + b

async def fetch_data(url: str):
    pass
"""
        sigs = extract_python_signatures(code)
        self.assertIn("class Calculator(Base):", sigs)
        self.assertTrue(any("def add" in s for s in sigs))
        self.assertTrue(any("async def fetch_data" in s for s in sigs))

    def test_js_signature_extraction(self):
        code = """
export function processOrder(id, amount) {
    return true;
}
export const getPrice = (item) => item.price;
interface UserState {
    name: string;
}
"""
        sigs = extract_js_ts_signatures(code)
        self.assertTrue(any("function processOrder" in s for s in sigs))
        self.assertTrue(any("const getPrice" in s for s in sigs))
        self.assertTrue(any("interface UserState" in s for s in sigs))

    def test_repo_context_generation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            src = tmppath / "src"
            src.mkdir()
            (src / "math.py").write_text("def multiply(x, y):\n    return x * y\n", encoding="utf-8")
            (tmppath / "README.md").write_text("# Demo Project\n", encoding="utf-8")

            context = build_repo_context(tmppath, context_files=["README.md"])
            self.assertIn("math.py", context)
            self.assertIn("multiply", context)
            self.assertIn("Full File: README.md", context)
            self.assertIn("# Demo Project", context)


if __name__ == "__main__":
    unittest.main()
