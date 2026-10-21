---
name: ask-argon-web
description: |
  Alternate trigger name for the use-argon-web skill.
  Delegate queries, coding tasks, architecture designs, multi-turn reasoning,
  and debugging to a web-based AI model (Gemini Argon, Claude, ChatGPT, etc.)
  running in your own logged-in browser — no API key required.
  Activate whenever the user says:
  - "ask argon"
  - "use argon"
  - "use argon web"
  - "run through argon"
  - "query argon"
license: Apache-2.0
metadata:
  version: v2
  author: Mohit20057
  repo: https://github.com/Mohit20057/AI-web-bridge
---

<!-- This skill is identical to use-argon-web — it exists so both trigger names
     ("use argon" and "ask argon") activate the same workflow. -->

# Use Web AI Bridge (Argon / Claude / ChatGPT)

This skill delegates reasoning, code generation, and debugging to a **web-based
AI model** through the user's own browser session via Playwright CDP automation.
No API keys. No billing. Uses your existing logged-in session.

---

## Prerequisites

1. **Python 3.11+** with `playwright` installed:
   ```bash
   pip install playwright
   playwright install chromium
   ```

2. **Chrome running with remote debugging** — launch it once with:
   ```bash
   # Windows
   bridge\launch_chrome.bat

   # Mac / Linux
   bash bridge/launch_chrome.sh
   ```
   Then log in to your target web AI (e.g. `gemini.google.com`) in that window.

3. **Environment variables** (put in `.env` or export before running):
   | Variable | Default | Description |
   |---|---|---|
   | `CHROME_PROFILE_DIR` | `~/ArgonChromeProfile` | Chrome profile with saved session |
   | `CHROME_DEBUG_PORT` | `9222` | CDP port Chrome is listening on |
   | `BRIDGE_SCRIPT` | `bridge/argon_bridge.py` | Path to the bridge script |

---

## CRITICAL RULES (Read Every Time)

1. **MULTI-TURN PERSISTENCE — DO NOT STOP AFTER 1 OUTPUT**
   - When the user asks to use the web AI for a task, enter **Web-AI-Assisted Mode**.
   - For multi-step tasks, follow-up questions, or code-then-test cycles, **continue
     consulting the web AI for every subsequent step or error**.
   - Do NOT stop after 1 output or revert to answering alone unless the user
     explicitly says to exit this mode.

2. **SESSION CONTINUITY**
   - **New unrelated task**: pass `--new-chat` to start a fresh conversation thread.
   - **Follow-up / sub-step**: **omit `--new-chat`** so the web AI remembers the
     previous code, context, and discussion.

3. **SELF-HEALING ERROR LOOP**
   - If code from the web AI fails with an error, do NOT give up or rewrite yourself.
   - Capture the full traceback, form a debugging prompt
     (*"Your previous solution gave this error: [traceback]. Please fix it."*),
     and call the bridge again.

4. **ONE TRUSTED BRIDGE**
   - Always invoke via the `BRIDGE_SCRIPT` path (resolved from env var or project root).

---

## Execution Workflow

### Step 1 — Formulate the Prompt

The web AI cannot see your local files. Bundle into a single message:
- The user's exact request
- Relevant code snippets or schema
- Any error messages or terminal logs
- Key constraints (language, framework, token budget)

Write the prompt to `_argon_prompt.txt` in the workspace root.

### Step 2 — Clean Stage & Execute

Always delete stale output first:
```bash
# Windows PowerShell
Remove-Item -Path "_argon_response.md" -Force -ErrorAction SilentlyContinue

# Mac / Linux
rm -f _argon_response.md
```

Run the bridge:
```bash
# Follow-up / multi-turn step (DEFAULT — keeps conversation alive):
python "$BRIDGE_SCRIPT" --prompt-file _argon_prompt.txt --out _argon_response.md

# Brand-new topic:
python "$BRIDGE_SCRIPT" --prompt-file _argon_prompt.txt --new-chat --out _argon_response.md
```

Where `$BRIDGE_SCRIPT` is the absolute path to `bridge/argon_bridge.py`
(or wherever you cloned this repo).

### Step 3 — Handle Chrome Connection Errors

If the bridge reports Chrome is not reachable on port 9222:
1. Launch Chrome: run `bridge/launch_chrome.bat` (Windows) or `bridge/launch_chrome.sh`.
2. Confirm the user is logged into the target web AI.
3. Re-run the bridge command.

### Step 4 — Apply & Continue

1. Read `_argon_response.md`.
2. Apply code changes or present the answer to the user.
3. If the user asks a follow-up, or the next plan step needs execution,
   **immediately go back to Step 1 for the next turn** — do not stop.
4. Delete temp files (`_argon_prompt.txt`, `_argon_response.md`) only when the
   entire task is fully complete.

---

## Adapter Notes for Other CLIs

| CLI | How to use this skill |
|---|---|
| **Antigravity** | Drop this file in `~/.gemini/config/skills/ask-argon-web/SKILL.md` |
| **Cursor** | Paste the rules section into `.cursorrules` |
| **Claude Code** | Paste the rules section into `CLAUDE.md` |
| **Aider** | `aider --read bridge/argon_bridge.py --read _argon_response.md` |
| **Plain script** | `python bridge/argon_bridge.py --prompt-file prompt.txt --out out.md` |

See [`SKILL_SPEC.md`](../../SKILL_SPEC.md) for the full adapter guide.
