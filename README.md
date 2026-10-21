# AI Web Bridge 🌐🤖

> **Universal browser-automation bridge connecting any AI coding CLI
> (Antigravity, Cursor, Aider, Claude Code, Continue.dev, Gemini CLI…) to
> web-only frontier models (Gemini Argon, Claude Web, ChatGPT, Grok…) via your
> own logged-in Chrome — no API keys or billing needed.**  
> Includes Playwright multi-turn scraping, Google Stitch UI design automation,
> and ready-to-use Agent Skill definitions.

---

## What Is This?

Most frontier AI models have a web interface but no affordable API.
**AI Web Bridge** solves this by using Playwright's Chrome DevTools Protocol
(CDP) to automate your *already-logged-in* browser window, turning any web AI
into a programmable backend for your coding CLI.

```
Your CLI (Antigravity / Cursor / Aider…)
        │  writes prompt to _argon_prompt.txt
        ▼
  argon_bridge.py  ──CDP──►  Chrome (your logged-in session)
        │                      gemini.google.com / claude.ai / etc.
        │  reads response
        ▼
  _argon_response.md  ──►  CLI applies the answer
```

**Also included:** A Google Stitch client (`stitch_client.py`) that calls the
Stitch MCP API directly to generate UI screens — no web scraping needed there,
just set your `STITCH_API_KEY`.

---

## Features

| Feature | How |
|---|---|
| **Zero-API web AI queries** | Playwright CDP → your logged-in Chrome |
| **Multi-turn conversation** | Bridge tracks the active chat thread across calls |
| **Self-healing error loop** | Skills instruct the CLI to feed errors back to the web AI |
| **Google Stitch UI generation** | Direct MCP API calls via `stitch_client.py` |
| **Plug-and-play Agent Skills** | Drop-in SKILL.md files for Antigravity + adapter notes for Cursor, Claude Code, Aider |
| **No hardcoded secrets** | All secrets via environment variables or `.env` |

---

## 💡 How It Drastically Reduces CLI Token Usage & Costs

### Does it *really* save tokens? **Yes, significantly.**

When using AI coding assistants (Antigravity, Cursor, Aider, Claude Code), you pay for both **input tokens** (context, chat history, file dumps) and **output tokens** (generated code, explanations, deep reasoning traces). These costs escalate rapidly with frontier models like Claude 3.7 Sonnet, OpenAI o1/o3-mini, or Gemini 1.5 Pro.

Here is exactly how AI Web Bridge cuts your token consumption and billing:

#### 1. Zero-Cost Heavy Reasoning & Generation
- **Without the bridge:** Your CLI model must generate full 500+ line components, documentation, and multi-step plans. A single deep refactor or debug session can burn 10,000 to 50,000+ output and reasoning tokens.
- **With the bridge:** You offload that heavy generation to the web interface (Gemini Advanced / Argon, Claude Web, ChatGPT). The web model performs the deep thinking and code drafting for **$0 per token**, using your existing web subscription or free tier.

#### 2. The "Brain & Hands" Architecture (Use Cheap/Fast Models in CLI)
- Configure your CLI to run an extremely cheap, fast model (e.g. `Claude 3.5 Haiku`, `Gemini Flash`, `GPT-4o-mini`, or even local models via Ollama) to act as the **orchestrator** ("the hands").
- The CLI merely coordinates file reading, running terminal commands, and passing prompts to the bridge.
- The web browser model acts as the **frontier brain** ("the architect").
- **Result:** You get frontier-grade intelligence while paying tiny token fees for simple tool orchestration.

#### 3. Preventing Context Window Bloat
- When debugging complex errors over multiple turns, CLI chat histories balloon, forcing you to pay for re-sending thousands of tokens on every single prompt.
- With the bridge, multi-turn exploration and iterative debugging happen inside the browser chat session. Your CLI only ingests the final, validated code snippet into your repository, keeping the local context window lean and cheap.

#### 4. Flat-Rate / Free Quotas vs. Per-Token Metering
- Web AI models operate under flat monthly subscriptions ($20/mo) or generous free daily limits with no per-token metering.
- CLI APIs charge strictly per million tokens. Offloading 80–90% of token volume to web sessions eliminates surprise API bills.

---

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Bridge scripts |
| pip / uv | latest | Package management |
| playwright | 1.40+ | Chrome automation |
| Google Chrome | any | Your logged-in browser session |

Install Playwright:
```bash
pip install playwright
playwright install chromium
```

---

## Quick Start (5 minutes)

### 1. Clone & configure

```bash
git clone https://github.com/Mohit20057/AI-web-bridge.git
cd AI-web-bridge
cp .env.example .env
# Edit .env — set STITCH_API_KEY if you want the Stitch skill
```

### 2. Launch Chrome with remote debugging

**Windows:**
```bat
bridge\launch_chrome.bat
```

**Mac / Linux:**
```bash
bash bridge/launch_chrome.sh
```

A Chrome window opens. **Log in** to your target web AI (e.g.
`gemini.google.com`). Keep this window open.

### 3. Send your first prompt

```bash
echo "What is the time complexity of quicksort?" > _argon_prompt.txt
python bridge/argon_bridge.py --prompt-file _argon_prompt.txt --out _argon_response.md
cat _argon_response.md
```

---

## Environment Variables

All configuration is done via environment variables (or `.env`):

| Variable | Default | Description |
|---|---|---|
| `CHROME_PROFILE_DIR` | `~/ArgonChromeProfile` | Chrome user-data-dir for the debug session |
| `CHROME_DEBUG_PORT` | `9222` | CDP port Chrome listens on |
| `STITCH_API_KEY` | *(required for Stitch)* | API key from https://aistudio.google.com/apikey |

---

## Bridge CLI Flags (`argon_bridge.py`)

| Flag | Description |
|---|---|
| `--prompt-file FILE` | Path to a `.txt` file containing the prompt |
| `--prompt TEXT` | Inline prompt text (alternative to `--prompt-file`) |
| `--out FILE` | Write the response to this file (default: stdout) |
| `--new-chat` | Start a brand-new conversation thread |
| `--port PORT` | Override CDP port (default: `$CHROME_DEBUG_PORT` or 9222) |
| `--timeout SECS` | Max seconds to wait for a response (default: 120) |

---

## Stitch Client (`stitch_client.py`)

Set `STITCH_API_KEY` first, then:

```bash
# List your Stitch projects
python skills/stitch-design/scripts/stitch_client.py list

# Create a new project
python skills/stitch-design/scripts/stitch_client.py create --title "My SaaS App"

# Generate a screen
python skills/stitch-design/scripts/stitch_client.py generate \
    --project-id "projects/abc123" \
    --prompt "Design a dark-themed SaaS landing page..." \
    --device DESKTOP

# List screens in a project
python skills/stitch-design/scripts/stitch_client.py screens --project-id "projects/abc123"
```

---

## Agent Skills

Drop these into your CLI's skill directory:

| Skill folder | What it does |
|---|---|
| `skills/use-argon-web/` | Ask any web AI, multi-turn, self-healing |
| `skills/ask-argon-web/` | Alternate trigger name (same behavior) |
| `skills/stitch-design/` | Full UI design lifecycle with Google Stitch |

### Antigravity

```bash
# Copy skills into Antigravity config
cp -r skills/use-argon-web  ~/.gemini/config/skills/
cp -r skills/ask-argon-web  ~/.gemini/config/skills/
cp -r skills/stitch-design  ~/.gemini/config/skills/
```

Then in any Antigravity chat: *"use argon web for this"* or *"design with stitch"*.

### Cursor

Paste the **CRITICAL RULES** and **Execution Workflow** sections from any
`SKILL.md` into your `.cursorrules` file.

### Claude Code

Paste the same sections into `CLAUDE.md` at the root of your project.

### Aider

```bash
aider --read bridge/argon_bridge.py \
      --read skills/use-argon-web/SKILL.md \
      --read _argon_response.md
```

### Plain Python

```python
import subprocess, pathlib

prompt = pathlib.Path("_argon_prompt.txt")
prompt.write_text("Explain async/await in Python")

subprocess.run([
    "python", "bridge/argon_bridge.py",
    "--prompt-file", str(prompt),
    "--out", "_argon_response.md"
])

print(pathlib.Path("_argon_response.md").read_text())
```

---

## Adding a New Web AI Target

1. Open `bridge/argon_bridge.py`.
2. Find the `SELECTORS` dict near the top.
3. Add an entry for your target site:
   ```python
   "claude": {
       "url": "https://claude.ai/new",
       "input": 'div[contenteditable="true"]',
       "send_btn": 'button[aria-label="Send message"]',
       "response": 'div.font-claude-message',
   }
   ```
4. Pass `--target claude` when calling the bridge.

See [`SKILL_SPEC.md`](SKILL_SPEC.md) for full details.

---

## Repository Structure

```
AI-web-bridge/
├── .env.example                  # Copy to .env and fill in secrets
├── .gitignore                    # Blocks .env, chrome profiles, response files
├── README.md                     # This file
├── SKILL_SPEC.md                 # Open Agent Skill format specification
├── bridge/
│   ├── argon_bridge.py           # Core Playwright bridge script
│   ├── launch_chrome.bat         # Windows: launch Chrome with CDP
│   └── launch_chrome.sh          # Mac/Linux: launch Chrome with CDP
└── skills/
    ├── use-argon-web/
    │   └── SKILL.md              # Agent skill — trigger: "use argon"
    ├── ask-argon-web/
    │   └── SKILL.md              # Agent skill — trigger: "ask argon"
    └── stitch-design/
        ├── SKILL.md              # Agent skill — trigger: "use stitch"
        ├── references/
        │   └── prompt-template.md
        └── scripts/
            ├── stitch_client.py  # Google Stitch MCP API client
            └── fetch_assets.py   # Download Stitch HTML & screenshots
```

---

## Security Notes

- **No secrets in this repo.** All API keys and local paths are loaded from
  environment variables or `.env` (which is gitignored).
- Chrome profile directories contain your browser session cookies — keep them
  on your local machine only. They are gitignored by default.
- The bridge only automates your own logged-in session. It does not create
  accounts or bypass authentication.

---

## Contributing

PRs welcome! Priority areas:
- New web AI targets in `SELECTORS` (Claude, ChatGPT, Grok…)
- Better response extraction heuristics
- Windows/Mac parity for Chrome launcher
- Tests

---

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
