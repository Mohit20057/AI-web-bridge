# Agent Skill Specification (Open Format)

This document defines the **Agent Skill** format used in AI Web Bridge and
explains how to adapt skills to any AI coding CLI.

---

## What Is an Agent Skill?

An **Agent Skill** is a self-contained folder containing:

```
skill-name/
├── SKILL.md          ← required: instructions the AI reads at runtime
└── scripts/          ← optional: Python/shell helpers the AI calls
    └── *.py
```

The `SKILL.md` file tells the AI agent:
- **When** to activate (trigger phrases)
- **What** to do step-by-step (workflow)
- **How** to call supporting scripts
- **What rules** govern multi-turn behavior

Skills are loaded by the CLI at runtime, not baked into the model — so they
work with any LLM that can read context files.

---

## SKILL.md Format

```yaml
---
name: skill-name          # unique identifier
description: |
  One-paragraph description + trigger phrases.
  Activate when the user says:
  - "trigger phrase 1"
  - "trigger phrase 2"
license: Apache-2.0
metadata:
  version: v1
  author: your-handle
---

# Skill Title

Brief description of what this skill does.

---

## CRITICAL RULES (Read Every Time)
<numbered list of hard rules the agent must never violate>

---

## Execution Workflow

### Step 1 — ...
<step-by-step instructions>

### Step 2 — ...
```

**Key conventions:**
- **CRITICAL RULES** are always read and applied before anything else.
- Steps are numbered and self-contained.
- Script paths use environment variables (`$BRIDGE_SCRIPT`, `$STITCH_CLIENT`)
  rather than hardcoded paths, so the skill works wherever you clone the repo.
- Temp files (`_*_prompt.txt`, `_*_response.md`) are cleaned up only when the
  full task is done, never between steps of a multi-turn task.

---

## Adapting to Each CLI

### Antigravity (Google)

1. Copy the skill folder into `~/.gemini/config/skills/`:
   ```bash
   cp -r skills/use-argon-web ~/.gemini/config/skills/
   ```
2. The CLI reads `SKILL.md` automatically when trigger phrases appear in chat.
3. The `description.Activate when the user says:` block controls activation.

### Cursor

Cursor uses `.cursorrules` (plain text) loaded into every prompt:

```markdown
## Web AI Bridge Rules

When the user says "use argon" or "ask argon":
1. Write their request to `_argon_prompt.txt`.
2. Run: `python bridge/argon_bridge.py --prompt-file _argon_prompt.txt --out _argon_response.md`
3. Read `_argon_response.md` and apply the answer.
4. For follow-ups, omit `--new-chat` to keep context.
5. Feed errors back to the bridge — don't rewrite the code yourself.
```

Paste the **CRITICAL RULES** and **Execution Workflow** sections from the
relevant `SKILL.md` into `.cursorrules`.

### Claude Code

Claude Code reads `CLAUDE.md` at the project root before every task.
Same approach as Cursor — paste the rules section into `CLAUDE.md`:

```markdown
<!-- CLAUDE.md -->
## Web AI Bridge

[paste CRITICAL RULES and Execution Workflow from SKILL.md here]
```

### Aider

Pass skill files with `--read` so Aider includes them in its context:

```bash
aider \
  --read bridge/argon_bridge.py \
  --read skills/use-argon-web/SKILL.md \
  --read _argon_response.md \
  your_file.py
```

Aider will follow the workflow instructions in SKILL.md for the current session.

### Continue.dev

Add the skill content to your Continue system prompt in
`.continue/config.json`:

```json
{
  "systemMessage": "...[paste CRITICAL RULES + Execution Workflow here]..."
}
```

### Gemini CLI

Pass the skill as a context file:

```bash
gemini -f skills/use-argon-web/SKILL.md "use argon to explain this code"
```

### Plain Python / No CLI

Call the bridge directly without any CLI:

```python
import subprocess, pathlib

pathlib.Path("_argon_prompt.txt").write_text("Your prompt here")

subprocess.run([
    "python", "bridge/argon_bridge.py",
    "--prompt-file", "_argon_prompt.txt",
    "--out", "_argon_response.md",
])

answer = pathlib.Path("_argon_response.md").read_text()
print(answer)
```

---

## Adding a New Web AI Target

The bridge script (`bridge/argon_bridge.py`) uses a `SELECTORS` dictionary
that maps target names to CSS selectors for that site's chat UI.

To add a new target:

1. Open `bridge/argon_bridge.py` and locate the `SELECTORS` dict.
2. Inspect the target site's DOM to find:
   - The text input selector (textarea or contenteditable div)
   - The send button selector
   - The response container selector
3. Add your entry:
   ```python
   SELECTORS["my-ai"] = {
       "url": "https://my-ai.example.com/chat",
       "input": "textarea#chat-input",
       "send_btn": "button[data-testid='send']",
       "response": "div.message.assistant",
   }
   ```
4. Use it: `python bridge/argon_bridge.py --target my-ai --prompt-file p.txt`

---

## Creating a New Skill

1. Create the folder: `skills/my-skill/`
2. Copy the template below into `skills/my-skill/SKILL.md` and fill it in.
3. Add any helper scripts to `skills/my-skill/scripts/`.
4. Test it manually before publishing.
5. Submit a PR — skills are the easiest contribution!

### Minimal SKILL.md Template

```yaml
---
name: my-skill
description: |
  What this skill does and when to activate it.
  Activate when the user says:
  - "trigger phrase"
license: Apache-2.0
metadata:
  version: v1
  author: your-handle
---

# My Skill

Brief description.

---

## CRITICAL RULES (Read Every Time)

1. Rule one.
2. Rule two.

---

## Execution Workflow

### Step 1 — Do X
Instructions...

### Step 2 — Do Y
Instructions...
```

---

## Why This Format?

- **Plain Markdown** — readable by any LLM, no schema lock-in.
- **CLI-agnostic** — the same SKILL.md works in Antigravity, Cursor, Claude Code,
  Aider, or any tool that can inject context.
- **Script-driven** — heavy lifting goes into standalone Python scripts, not
  embedded in the skill prose, so scripts can be tested independently.
- **Stateless trigger** — CLIs decide when to activate based on the
  `description` block; no runtime registry or plugin system needed.
