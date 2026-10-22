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

Skills are loaded by a compatible coding CLI at runtime, not baked into a
model. A browser AI website does not read a local `SKILL.md`; browser-only use
means manually pasting a compact prompt/context packet and carrying the answer
back yourself.

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
- Script paths use environment variables (`$BRIDGE_SCRIPT`)
  rather than hardcoded paths, so the skill works wherever you clone the repo.
- Temp files (`_*_prompt.txt`, `_*_response.md`) are cleaned up only when the
  full task is done, never between steps of a multi-turn task.

---

## CLI integration

The stable bridge entry point is `python bridge/argon_bridge.py`. Its arguments
are CLI-neutral; each coding tool only needs a way to load the skill and run a
shell command. `BRIDGE_SCRIPT` may point to an absolute path when the project
root is not the current directory.

The browser can be selected with `--browser chrome|edge`. Use
`--list-browser-profiles` to find a profile directory ID and
`--profile-directory ID` to select it; add `--profile-dir ROOT` for a
nonstandard browser data folder. Selecting an everyday profile may require
closing its browser first so the bridge can launch it with debugging enabled;
the bridge does not close an already-open browser. `--doctor` checks sign-in
readiness and lists model choices without sending a prompt. `--review-context` prints the exact
assembled request without contacting a provider. Multi-provider mode is always
explicit and sends the same request to every selected service.

### Gemini CLI

Gemini CLI supports Agent Skills. Install the skill in a workspace discovery
directory:

```bash
# Windows PowerShell
New-Item -ItemType Directory -Force .agents/skills | Out-Null
Copy-Item -Recurse skills/use-argon-web .agents/skills/

# macOS / Linux
mkdir -p .agents/skills
cp -R skills/use-argon-web .agents/skills/
```

Then invoke `/use-argon-web` or let Gemini CLI activate it when relevant. A
user-level install can use `~/.agents/skills/`. Gemini CLI also supports
`gemini skills install` for repositories or local skill paths; see its current
[Agent Skills guide](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/skills.md).

### Claude Code

Install a project skill at `.claude/skills/use-argon-web/SKILL.md`:

```bash
# Windows PowerShell
New-Item -ItemType Directory -Force .claude/skills | Out-Null
Copy-Item -Recurse skills/use-argon-web .claude/skills/

# macOS / Linux
mkdir -p .claude/skills
cp -R skills/use-argon-web .claude/skills/
```

Invoke `/use-argon-web`, or keep the skill in the repository and use it where
Claude Code discovers project skills. Personal skills can be copied beneath
`~/.claude/skills/`. See [Claude Code Skills](https://code.claude.com/docs/en/skills).

### Cursor

Cursor discovers Agent Skills under `.agents/skills/` and `.cursor/skills/`.
For a project install, use:

```bash
# Windows PowerShell
New-Item -ItemType Directory -Force .agents/skills | Out-Null
Copy-Item -Recurse skills/use-argon-web .agents/skills/

# macOS / Linux
mkdir -p .agents/skills
cp -R skills/use-argon-web .agents/skills/
```

Use `/use-argon-web` or attach it with `@`. Avoid making this workflow an
always-loaded user rule; keeping it on-demand uses fewer context tokens. See
[Cursor Skills](https://cursor.com/help/customization/skills).

### Aider

Aider's documented workflow is to read selected instruction or result files;
it does not use this repository's skill activation protocol. Avoid loading the
full skill on every run. Compose the compact packet and invoke the bridge, then
read only the response you need:

```bash
python bridge/argon_bridge.py --context-file _argon_context.json --out _argon_response.md
aider --read _argon_response.md
```

Use `aider --read skills/use-argon-web/SKILL.md` only for a session that needs
the complete workflow instructions. See [Aider conventions](https://aider.chat/docs/usage/conventions.html).

### Plain script or another CLI

Any tool that can write a UTF-8 prompt/context file, run Python, and read an
output can use the same contract:

```bash
python bridge/argon_bridge.py --context-file _argon_context.json --out _argon_response.md
```

Use `--prompt-file` for a simple question. For an explicitly requested fan-out,
use `--providers gemini,chatgpt` or `--all`; keep the default single-provider
path to limit usage.

### Browser-only user

There is no automatic skill installation inside Gemini, ChatGPT, Claude, or
another browser AI website. Prepare or review the packet locally with
`--review-context`, paste only the resulting task context into the website, and
copy its answer back. The website cannot access local files or another site's
history unless the user manually provides that information.

The packet schema and review/logging behavior are documented in
[CONTEXT_PACKET.md](CONTEXT_PACKET.md). Multi-provider mode remains opt-in:
each site receives the same context and total provider usage increases.

The optional project handoff saves only a task summary, project summary, and
recent changes from submitted context packets. `--no-handoff` disables it for a
request. The `--forget-*` options remove chosen project-local records. Optional
token comparisons accept counts reported by the coding CLI; they do not
estimate savings automatically.

Google Stitch is isolated as a companion folder under
[stitch-design/](stitch-design/) because it uses Google's Stitch MCP service
and separate credentials rather than a signed-in browser-AI session.

---

## Adding a New Browser AI Provider

The bridge reads provider metadata from `bridge/providers.json` and loads the
provider's adapter class from `bridge/providers/`. Gemini, ChatGPT, and Claude
adapters are configured. A provider is not enabled by adding selectors alone;
its adapter must implement the provider-specific chat lifecycle:

- `open_or_resume_chat(context, chat_url, new_chat)`
- `wait_for_login(page, timeout)`
- `list_models(page)` and `select_model(page, model_name)`
- `send_prompt(page, prompt_text)`
- `get_response_elements(page)` and `wait_for_response(page, initial_count, timeout)`
- `close()`

Add a provider entry with its adapter import path, URL, Chromium/CDP defaults,
timeouts, and selectors. Then implement and verify the adapter against that
provider's current signed-in UI. Select a configured provider with
`--provider NAME`; use `--list-providers` to list adapters and
`--provider NAME --list-models` to inspect model labels shown to that account.
`--model LABEL` must match one visible option and the selected label must be
confirmed before the prompt is submitted. For fan-out, `--providers` and `--all`
run sequentially and save distinct outputs; the same context is sent to each
selected provider. See [multi-provider usage](README.md#multi-provider-runs).

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
