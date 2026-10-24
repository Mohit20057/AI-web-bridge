"""Handoff and ledger management for AI Web Bridge."""

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HANDOFF_MAX_CHARS = 6000  # ~1500 tokens


def sanitize_secrets(text: str, project_dir: Path | None = None) -> str:
    """Scrub known secret tokens and values loaded from .env files."""
    if not text or not isinstance(text, str):
        return text

    sanitized = text
    # 1. Scrub values from existing .env files if present
    if project_dir:
        try:
            for env_path in project_dir.glob(".env*"):
                if env_path.is_file():
                    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            _, val = line.split("=", 1)
                            val = val.strip().strip("'\"")
                            if len(val) >= 4:
                                sanitized = sanitized.replace(val, "[REDACTED_SECRET]")
        except Exception:
            pass

    # 2. Scrub common secret patterns
    patterns = [
        r"(?i)(?:api_key|token|secret|password|bearer|auth)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{6,})['\"]?",
        r"(sk-[a-zA-Z0-9_\-]{6,})",
        r"(ghp_[a-zA-Z0-9]{20,})",
        r"(xox[baprs]-[a-zA-Z0-9_\-]{10,})",
    ]
    for pat in patterns:
        sanitized = re.sub(pat, "[REDACTED_SECRET]", sanitized)

    return sanitized


class HandoffManager:
    """Manages .bridge/ledger.jsonl and .bridge/HANDOFF.md with auto-sync and compaction."""

    def __init__(self, project_dir: Path | str | None = None):
        self.project_dir = Path(project_dir or Path.cwd()).resolve()
        self.bridge_dir = self.project_dir / ".bridge"
        self.ledger_path = self.bridge_dir / "ledger.jsonl"
        self.handoff_path = self.bridge_dir / "HANDOFF.md"
        self.checkpoint_path = self.bridge_dir / "checkpoint.json"
        self.logs_dir = self.bridge_dir / "logs"

    def ensure_dirs(self) -> None:
        self.bridge_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def is_git_repo(self) -> bool:
        return (self.project_dir / ".git").exists()

    def get_git_state(self) -> dict[str, Any]:
        """Return git hash and diff status, or file-hash manifest if not a git repo."""
        if self.is_git_repo():
            try:
                head_rev = subprocess.check_output(
                    ["git", "rev-parse", "--short", "HEAD"],
                    cwd=str(self.project_dir),
                    stderr=subprocess.DEVNULL,
                    text=True,
                ).strip()
            except Exception:
                head_rev = "no-commits"

            try:
                diff_stat = subprocess.check_output(
                    ["git", "diff", "--stat", "HEAD", "--", ":!.env*", ":!*.key", ":!*.pem"],
                    cwd=str(self.project_dir),
                    stderr=subprocess.DEVNULL,
                    text=True,
                ).strip()
            except Exception:
                try:
                    diff_stat = subprocess.check_output(
                        ["git", "diff", "--stat", "--", ":!.env*", ":!*.key", ":!*.pem"],
                        cwd=str(self.project_dir),
                        stderr=subprocess.DEVNULL,
                        text=True,
                    ).strip()
                except Exception:
                    diff_stat = ""

            try:
                untracked_raw = subprocess.check_output(
                    ["git", "status", "--porcelain"],
                    cwd=str(self.project_dir),
                    stderr=subprocess.DEVNULL,
                    text=True,
                ).strip()
                untracked_lines = []
                for uline in untracked_raw.splitlines():
                    parts = uline.strip().split(maxsplit=1)
                    if len(parts) == 2:
                        fname = parts[1].strip()
                        if not (fname == ".env" or fname.startswith(".env.") or fname.endswith(".key") or fname.endswith(".pem")):
                            untracked_lines.append(uline)
                untracked = "\n".join(untracked_lines)
            except Exception:
                untracked = ""

            summary_stat = diff_stat if diff_stat else (
                f"{len(untracked.splitlines())} modified/untracked files" if untracked else "clean"
            )
            return {
                "type": "git",
                "hash": head_rev,
                "stat": summary_stat,
                "has_changes": bool(diff_stat or untracked),
            }
        else:
            # File-hash manifest fallback
            manifest = {}
            for path in sorted(self.project_dir.rglob("*")):
                if path.is_file() and not any(part.startswith(".") for part in path.parts):
                    try:
                        content = path.read_bytes()
                        manifest[str(path.relative_to(self.project_dir))] = hashlib.sha256(content).hexdigest()[:12]
                    except Exception:
                        pass
            manifest_hash = hashlib.sha256(json.dumps(manifest).encode("utf-8")).hexdigest()[:8]
            return {
                "type": "manifest",
                "hash": manifest_hash,
                "stat": f"{len(manifest)} files tracked",
                "has_changes": False,
                "manifest": manifest,
            }

    def init_project(self, goal: str = "Project initialization") -> str:
        """Scan existing repo, create .bridge/ and initial HANDOFF.md."""
        self.ensure_dirs()
        state = self.get_git_state()

        checkpoint_data = {
            "last_hash": state["hash"],
            "last_stat": state["stat"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "goal": goal,
        }
        self.checkpoint_path.write_text(json.dumps(checkpoint_data, indent=2), encoding="utf-8")

        init_event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "job_id": "init",
            "actor": "cli",
            "role": "init",
            "action": "init",
            "files": [],
            "git_before": state["hash"],
            "git_after": state["hash"],
            "verify": "none",
            "status": "COMPLETE",
            "summary": f"Initialized AI Web Bridge tracking for {self.project_dir.name}",
        }
        self._append_ledger_raw(init_event)
        self.regenerate_handoff(goal=goal)
        return f"Initialized .bridge/ in {self.project_dir}"

    def auto_sync(self) -> str | None:
        """Compare working tree with last checkpoint; record user edits if any."""
        if not self.bridge_dir.exists() or not self.checkpoint_path.exists():
            return None

        try:
            last_checkpoint = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
        except Exception:
            last_checkpoint = {}

        current_state = self.get_git_state()
        last_hash = last_checkpoint.get("last_hash")
        last_stat = last_checkpoint.get("last_stat")

        changed = False
        diff_summary = ""

        if current_state["type"] == "git":
            if current_state["hash"] != last_hash or current_state["stat"] != last_stat:
                changed = True
                diff_summary = current_state["stat"]
        else:
            if current_state["hash"] != last_hash:
                changed = True
                diff_summary = current_state["stat"]

        if changed:
            changed_files = []
            if current_state["type"] == "git":
                try:
                    changed_out = subprocess.check_output(
                        ["git", "diff", "--name-only", "HEAD"],
                        cwd=str(self.project_dir),
                        stderr=subprocess.DEVNULL,
                        text=True,
                    ).strip()
                    if changed_out:
                        changed_files = [line.strip() for line in changed_out.splitlines() if line.strip()]
                except Exception:
                    pass
                if not changed_files:
                    try:
                        status_out = subprocess.check_output(
                            ["git", "status", "--porcelain"],
                            cwd=str(self.project_dir),
                            stderr=subprocess.DEVNULL,
                            text=True,
                        ).strip()
                        for sline in status_out.splitlines():
                            parts = sline.strip().split(maxsplit=1)
                            if len(parts) == 2:
                                changed_files.append(parts[1].strip())
                    except Exception:
                        pass

            files_mention = f" in {', '.join(changed_files)}" if changed_files else ""
            event = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "job_id": f"sync_{datetime.now(timezone.utc).strftime('%H%M%S')}",
                "actor": "user",
                "role": "developer",
                "action": "manual_edit",
                "files": changed_files,
                "git_before": last_hash or "unknown",
                "git_after": current_state["hash"],
                "verify": "none",
                "status": "COMPLETE",
                "summary": f"Manual edit detected{files_mention}: {diff_summary}",
            }
            self._append_ledger_raw(event)
            last_checkpoint["last_hash"] = current_state["hash"]
            last_checkpoint["last_stat"] = current_state["stat"]
            last_checkpoint["updated_at"] = datetime.now(timezone.utc).isoformat()
            self.checkpoint_path.write_text(json.dumps(last_checkpoint, indent=2), encoding="utf-8")
            self.regenerate_handoff()
            return f"Auto-synced manual edits ({diff_summary})"

        return None

    def record_job(
        self,
        job_id: str,
        actor: str,
        role: str,
        action: str,
        files: list[str],
        verify: str,
        status: str,
        summary: str,
        next_step: str = "",
        decisions: list[str] | None = None,
        open_issues: list[str] | None = None,
    ) -> None:
        """Append job event to ledger, update checkpoint, and refresh HANDOFF.md."""
        self.ensure_dirs()
        state = self.get_git_state()
        try:
            last_checkpoint = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
        except Exception:
            last_checkpoint = {"goal": "General development"}

        event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "job_id": job_id,
            "actor": actor,
            "role": role,
            "action": action,
            "files": files,
            "git_before": last_checkpoint.get("last_hash", "init"),
            "git_after": state["hash"],
            "verify": verify,  # PASS, FAIL, none
            "status": status,
            "summary": summary.strip(),
            "next_step": next_step.strip(),
        }
        if decisions:
            event["decisions"] = decisions
        if open_issues:
            event["open_issues"] = open_issues

        self._append_ledger_raw(event)

        last_checkpoint["last_hash"] = state["hash"]
        last_checkpoint["last_stat"] = state["stat"]
        last_checkpoint["updated_at"] = datetime.now(timezone.utc).isoformat()
        if next_step.strip():
            last_checkpoint["next_step"] = next_step.strip()
        self.checkpoint_path.write_text(json.dumps(last_checkpoint, indent=2), encoding="utf-8")

        self.regenerate_handoff()

    def _append_ledger_raw(self, event: dict[str, Any]) -> None:
        self.ensure_dirs()
        # Never store credentials or .env secrets
        clean_event = {}
        for k, v in event.items():
            if isinstance(v, str):
                clean_event[k] = sanitize_secrets(v, self.project_dir)
            elif isinstance(v, list):
                clean_event[k] = [sanitize_secrets(item, self.project_dir) if isinstance(item, str) else item for item in v]
            elif isinstance(v, dict):
                clean_event[k] = {dk: sanitize_secrets(dv, self.project_dir) if isinstance(dv, str) else dv for dk, dv in v.items()}
            else:
                clean_event[k] = v
        with self.ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(clean_event) + "\n")

    def read_ledger(self) -> list[dict[str, Any]]:
        if not self.ledger_path.exists():
            return []
        events = []
        with self.ledger_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except Exception:
                        pass
        return events

    def regenerate_handoff(self, goal: str | None = None) -> str:
        """Regenerate HANDOFF.md from ledger with rolling compaction under 1500 tokens."""
        self.ensure_dirs()
        events = self.read_ledger()
        state = self.get_git_state()

        try:
            checkpoint = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
        except Exception:
            checkpoint = {}

        current_goal = goal or checkpoint.get("goal") or "Build and maintain software components"
        checkpoint["goal"] = current_goal
        proposed_next = checkpoint.get("next_step", "")

        # Extract verified accomplishments & current state
        verified_items: list[str] = []
        open_issues: list[str] = []
        decisions: list[str] = []

        for ev in events:
            if ev.get("verify") == "PASS":
                files_str = f" ({', '.join(ev.get('files', []))})" if ev.get("files") else ""
                verified_items.append(f"{ev.get('role', 'task')}: {ev.get('summary', '')}{files_str}")
            if ev.get("next_step"):
                proposed_next = ev["next_step"]
            if ev.get("decisions"):
                decisions.extend(ev["decisions"])
            if ev.get("open_issues"):
                open_issues.extend(ev["open_issues"])
            if ev.get("verify") == "FAIL":
                open_issues.append(f"Verification failure in {ev.get('job_id')}: {ev.get('summary')}")

        current_state_str = (
            "\n".join(f"- {item}" for item in verified_items[-5:])
            if verified_items
            else "- Project initialized; ready for initial contract/architecture phase."
        )

        decisions_str = (
            "\n".join(f"- {d}" for d in decisions[-5:])
            if decisions
            else "- Contract-first modular pipeline architecture."
        )

        open_issues_str = (
            "\n".join(f"- {issue}" for issue in open_issues[-5:])
            if open_issues
            else "- None."
        )

        # Recent changes: last 10 full, older ones compacted to 1 line each
        recent_lines: list[str] = []
        if len(events) <= 10:
            for ev in reversed(events):
                ts = ev.get("ts", "")[:19].replace("T", " ")
                recent_lines.append(
                    f"- [{ts}] {ev.get('actor', 'ai')}/{ev.get('role', '')}: {ev.get('summary', '')} "
                    f"(verify={ev.get('verify', 'none')}, status={ev.get('status', 'COMPLETE')})"
                )
        else:
            last_10 = events[-10:]
            older = events[:-10]
            # Compact older
            recent_lines.append(f"- *... {len(older)} earlier ledger events compacted (see ledger.jsonl)*")
            for ev in reversed(last_10):
                ts = ev.get("ts", "")[:19].replace("T", " ")
                recent_lines.append(
                    f"- [{ts}] {ev.get('actor', 'ai')}/{ev.get('role', '')}: {ev.get('summary', '')} "
                    f"(verify={ev.get('verify', 'none')}, status={ev.get('status', 'COMPLETE')})"
                )

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        git_hash = state["hash"]

        handoff_content = f"""# HANDOFF | {self.project_dir.name} | {now_str} | checkpoint({git_hash})

## Goal
{current_goal}

## Current state (what works, what is verified)
{current_state_str}

## Decisions + why
{decisions_str}

## Recent changes (last 10; older ones compacted to 1 line each)
{chr(10).join(recent_lines)}

## Open issues
{open_issues_str}

## Next step (proposed)
{proposed_next or "Proceed with the next planned pipeline stage."}
"""

        # Enforce hard cap ~1500 tokens (approx 6000 chars)
        if len(handoff_content) > HANDOFF_MAX_CHARS:
            # Aggressive compaction on recent changes and history
            compacted_recent = [f"- Event {ev.get('job_id')}: {ev.get('summary', '')[:60]}" for ev in events[-5:]]
            handoff_content = f"""# HANDOFF | {self.project_dir.name} | {now_str} | checkpoint({git_hash})

## Goal
{current_goal}

## Current state (what works, what is verified)
{current_state_str[:1000]}

## Decisions + why
{decisions_str[:800]}

## Recent changes (compacted)
{chr(10).join(compacted_recent)}

## Open issues
{open_issues_str[:400]}

## Next step (proposed)
{proposed_next[:200]}
"""

        handoff_content = sanitize_secrets(handoff_content, self.project_dir)
        self.handoff_path.write_text(handoff_content, encoding="utf-8")
        return handoff_content

    def read_handoff(self) -> str:
        if self.handoff_path.exists():
            return self.handoff_path.read_text(encoding="utf-8", errors="ignore")
        return self.regenerate_handoff()

    def get_status_summary(self) -> str:
        """Return HANDOFF 'Current state' + 'Next step' only (max 15 lines)."""
        self.regenerate_handoff()
        handoff = self.read_handoff()
        lines = handoff.splitlines()

        extracting = False
        result_lines: list[str] = []

        for line in lines:
            if line.startswith("## Current state"):
                extracting = True
                result_lines.append(line)
            elif line.startswith("## Next step"):
                extracting = True
                result_lines.append(line)
            elif line.startswith("## ") and extracting:
                extracting = False
            elif extracting:
                if line.strip():
                    result_lines.append(line)

        # Clip to max 15 lines
        clipped = result_lines[:15]
        return "\n".join(clipped) if clipped else "No status available. Run 'bridge init' to initialize."
