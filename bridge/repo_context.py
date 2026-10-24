"""Repository context generator: file tree, function/class signatures, and selective file inclusion."""

import ast
import os
import re
from pathlib import Path

DEFAULT_IGNORE_DIRS = {
    ".git",
    ".bridge",
    ".ai-web-bridge",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    ".idea",
    ".vscode",
}

DEFAULT_IGNORE_FILES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.test",
    "id_rsa",
    "id_ed25519",
    "credentials.json",
    "client_secret.json",
}

def is_secret_path(p: Path) -> bool:
    name = p.name.lower()
    if name == ".env" or name.startswith(".env.") or name.endswith(".env"):
        return True
    if name in DEFAULT_IGNORE_FILES:
        return True
    if p.suffix.lower() in {".pem", ".key", ".pfx", ".p12"}:
        return True
    return False

DEFAULT_IGNORE_EXTS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".mp4",
    ".webm",
    ".mp3",
    ".wav",
    ".zip",
    ".tar",
    ".gz",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
}


def parse_gitignore(root_dir: Path) -> set[str]:
    """Parse .gitignore patterns if available."""
    gitignore = root_dir / ".gitignore"
    patterns = set(DEFAULT_IGNORE_DIRS)
    if gitignore.is_file():
        try:
            for line in gitignore.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    clean = line.rstrip("/").lstrip("/")
                    if clean:
                        patterns.add(clean)
        except Exception:
            pass
    return patterns


def generate_file_tree(root_dir: Path, max_depth: int = 4, max_files: int = 150) -> tuple[str, list[Path]]:
    """Build a compact ASCII tree of files and return collected source files."""
    root = root_dir.resolve()
    ignored_patterns = parse_gitignore(root)
    collected_files: list[Path] = []
    lines: list[str] = [f"{root.name}/"]

    def _walk(directory: Path, prefix: str = "", depth: int = 1):
        if depth > max_depth or len(collected_files) >= max_files:
            return
        try:
            entries = sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return

        filtered: list[Path] = []
        for e in entries:
            if is_secret_path(e) or e.name in ignored_patterns or e.name in DEFAULT_IGNORE_DIRS or e.suffix in DEFAULT_IGNORE_EXTS:
                continue
            filtered.append(e)

        count = len(filtered)
        for i, entry in enumerate(filtered):
            is_last = (i == count - 1)
            connector = "└── " if is_last else "├── "
            child_prefix = prefix + ("    " if is_last else "│   ")

            if entry.is_dir():
                lines.append(f"{prefix}{connector}{entry.name}/")
                _walk(entry, child_prefix, depth + 1)
            else:
                lines.append(f"{prefix}{connector}{entry.name}")
                collected_files.append(entry)
                if len(collected_files) >= max_files:
                    lines.append(f"{child_prefix}... (truncated after {max_files} files)")
                    break

    _walk(root)
    return "\n".join(lines), collected_files


def extract_python_signatures(content: str) -> list[str]:
    """Extract class, method, and function signatures using AST."""
    signatures: list[str] = []
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = [ast.unparse(b) for b in node.bases]
                base_str = f"({', '.join(bases)})" if bases else ""
                signatures.append(f"class {node.name}{base_str}:")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                async_prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
                args = ast.unparse(node.args)
                ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
                signatures.append(f"{async_prefix}def {node.name}({args}){ret}")
    except Exception:
        # Fallback to regex if parsing fails
        for line in content.splitlines():
            line_str = line.strip()
            if line_str.startswith(("def ", "async def ", "class ")):
                signatures.append(line_str)
    return signatures


def extract_js_ts_signatures(content: str) -> list[str]:
    """Extract JS/TS function, class, and interface signatures using regex."""
    signatures: list[str] = []
    patterns = [
        re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*([a-zA-Z0-9_$]+)\s*\([^)]*\)", re.MULTILINE),
        re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>", re.MULTILINE),
        re.compile(r"^\s*(?:export\s+)?class\s+([a-zA-Z0-9_$]+)(?:\s+extends\s+[a-zA-Z0-9_$]+)?", re.MULTILINE),
        re.compile(r"^\s*(?:export\s+)?interface\s+([a-zA-Z0-9_$]+)", re.MULTILINE),
        re.compile(r"^\s*(?:export\s+)?type\s+([a-zA-Z0-9_$]+)\s*=", re.MULTILINE),
    ]
    for pattern in patterns:
        for match in pattern.finditer(content):
            signatures.append(match.group(0).strip())
    return signatures


def extract_signatures(file_path: Path) -> str:
    """Extract code signatures from a source file."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

    ext = file_path.suffix.lower()
    sigs: list[str] = []
    if ext == ".py":
        sigs = extract_python_signatures(content)
    elif ext in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
        sigs = extract_js_ts_signatures(content)

    if sigs:
        # Limit to top 15 signatures per file to keep tokens minimal
        clipped = sigs[:15]
        return "\n  ".join(clipped)
    return ""


def build_repo_map(root_dir: Path, max_depth: int = 3, max_files: int = 60) -> str:
    """Build a concise repository map with file tree and exported signatures."""
    tree_str, files = generate_file_tree(root_dir, max_depth=max_depth, max_files=max_files)
    sections: list[str] = ["### File Tree", tree_str]

    sig_sections: list[str] = []
    for f in files:
        if f.suffix.lower() in {".py", ".ts", ".tsx", ".js", ".jsx"}:
            sigs = extract_signatures(f)
            if sigs:
                rel_path = f.relative_to(root_dir)
                sig_sections.append(f"**{rel_path}**:\n  {sigs}")

    if sig_sections:
        sections.append("### Key Signatures")
        # Keep top 12 files signatures
        sections.append("\n".join(sig_sections[:12]))

    return "\n\n".join(sections)


def build_repo_context(
    root_dir: Path,
    context_files: list[str | Path] | None = None,
    max_depth: int = 3,
) -> str:
    """Assemble file tree, signatures, and full text for selected context files."""
    repo_map = build_repo_map(root_dir, max_depth=max_depth)
    sections: list[str] = [repo_map]

    if context_files:
        full_sections: list[str] = []
        for item in context_files:
            p = (root_dir / item).resolve() if not Path(item).is_absolute() else Path(item).resolve()
            if is_secret_path(p):
                continue
            if p.is_file():
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                    rel_name = p.relative_to(root_dir) if root_dir in p.parents else p.name
                    full_sections.append(f"#### Full File: {rel_name}\n```\n{text}\n```")
                except Exception as exc:
                    full_sections.append(f"#### File: {p.name} (Error reading: {exc})")
        if full_sections:
            sections.append("### Context Files (Full Content)\n" + "\n\n".join(full_sections))

    return "\n\n".join(sections)
