"""Verification loop and unified diff patch application for AI Web Bridge."""

import re
import subprocess
from pathlib import Path


def run_verification(command: str, cwd: Path | str | None = None, timeout: int = 60) -> tuple[bool, str]:
    """Execute a verification command and return (passed, trimmed_error_log)."""
    if not command or not command.strip():
        return True, ""

    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode == 0:
            return True, proc.stdout.strip()

        combined = (proc.stderr or proc.stdout or f"Process exited with code {proc.returncode}").strip()
        lines = combined.splitlines()
        trimmed = "\n".join(lines[-15:])  # Trimmed to 15 lines as required
        return False, trimmed
    except subprocess.TimeoutExpired:
        return False, f"Verification command timed out after {timeout}s: {command}"
    except Exception as exc:
        return False, f"Could not execute verification command: {exc}"


def apply_unified_diff(original_text: str, diff_text: str) -> str | None:
    """Apply a unified diff patch to original_text. Supports standard numbered hunks and unadorned LLM hunks."""
    diff_match = re.search(r"```(?:diff)?\r?\n(.*?)\r?\n```", diff_text, re.DOTALL)
    clean_diff = diff_match.group(1) if diff_match else diff_text

    # 1. Try standard line-offset patch if numbered hunk headers exist
    hunk_pattern = re.compile(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@", re.MULTILINE)
    hunk_matches = list(hunk_pattern.finditer(clean_diff))
    if hunk_matches:
        orig_lines = original_text.splitlines()
        result_lines = list(orig_lines)
        offset = 0
        success = True
        for i, match in enumerate(hunk_matches):
            start_orig = int(match.group(1)) - 1
            hunk_start = match.end()
            hunk_end = hunk_matches[i + 1].start() if i + 1 < len(hunk_matches) else len(clean_diff)
            hunk_body = clean_diff[hunk_start:hunk_end]

            new_hunk_lines: list[str] = []
            old_hunk_lines: list[str] = []

            for line in hunk_body.splitlines():
                if line.startswith("+"):
                    new_hunk_lines.append(line[1:])
                elif line.startswith("-"):
                    old_hunk_lines.append(line[1:])
                elif line.startswith(" "):
                    new_hunk_lines.append(line[1:])
                    old_hunk_lines.append(line[1:])

            target_idx = start_orig + offset
            if target_idx < 0:
                target_idx = 0
            match_len = len(old_hunk_lines)
            if match_len > 0 and target_idx + match_len <= len(result_lines):
                result_lines[target_idx : target_idx + match_len] = new_hunk_lines
                offset += len(new_hunk_lines) - match_len
            else:
                success = False
                break
        if success:
            return "\n".join(result_lines)

    # 2. Content-based hunk replacement (supports unadorned @@ or approximate LLM diffs)
    lines = clean_diff.splitlines()
    hunk_bodies: list[list[str]] = []
    current_hunk: list[str] | None = None

    for line in lines:
        if line.startswith("@@"):
            if current_hunk is not None:
                hunk_bodies.append(current_hunk)
            current_hunk = []
        elif current_hunk is not None:
            if not (line.startswith("---") or line.startswith("+++")):
                current_hunk.append(line)
    if current_hunk is not None:
        hunk_bodies.append(current_hunk)

    if not hunk_bodies:
        return None

    current_text = original_text
    for hunk in hunk_bodies:
        old_lines = []
        new_lines = []
        for line in hunk:
            if line.startswith("+"):
                new_lines.append(line[1:])
            elif line.startswith("-"):
                old_lines.append(line[1:])
            elif line.startswith(" ") or not line:
                val = line[1:] if line.startswith(" ") else line
                old_lines.append(val)
                new_lines.append(val)
            else:
                old_lines.append(line)
                new_lines.append(line)

        old_block = "\n".join(old_lines).strip()
        new_block = "\n".join(new_lines).strip()

        if not old_block:
            continue

        if old_block in current_text:
            current_text = current_text.replace(old_block, new_block, 1)
        else:
            old_re = re.escape(old_block)
            old_re = re.sub(r"\\\s+", r"\\s+", old_re)
            if re.search(old_re, current_text):
                current_text = re.sub(old_re, lambda _: new_block, current_text, count=1)
            else:
                return None

    return current_text


def apply_patch_or_fallback(target_file: Path, fix_content: str) -> bool:
    """Apply unified diff to target_file; on failure or if complete file returned, overwrite target_file."""
    target_path = Path(target_file).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Try unified diff if diff indicators exist
    is_diff = "@@" in fix_content or ("---" in fix_content and "+++" in fix_content)
    if is_diff:
        if target_path.exists():
            orig_text = target_path.read_text(encoding="utf-8", errors="ignore")
            patched = apply_unified_diff(orig_text, fix_content)
            if patched is not None:
                target_path.write_text(patched, encoding="utf-8")
                return True
        # If it was a diff but couldn't be applied, don't corrupt target_path with diff syntax
        return False

    # 2. Fallback: Provider returned complete file (or fenced block)
    code_match = re.search(r"```[a-zA-Z0-9_\-\+]*\r?\n(.*?)\r?\n```", fix_content, re.DOTALL)
    clean_code = code_match.group(1) if code_match else fix_content.strip()

    # Strip any residual envelope markers
    clean_code = re.sub(r"<<<BRIDGE_[A-Z_]+>>>", "", clean_code).strip()
    target_path.write_text(clean_code, encoding="utf-8")
    return True


def format_fixer_prompt(command: str, stderr_log: str, attempt: int, max_retries: int) -> str:
    """Generate exact prompt for fixer role."""
    return (
        f"Check failed: {command}\n"
        f"Error:\n{stderr_log}\n"
        "Return the corrected function(s) as a unified diff; if the patch will not apply, return the COMPLETE file. "
        f"Change only what is needed. Attempt {attempt}/{max_retries}."
    )
