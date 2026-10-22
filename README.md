# AI Web Bridge 🌐🤖

> **A local bridge that lets coding CLIs delegate work to browser-based AI.**
> It supports configured Gemini, ChatGPT, and Claude adapters in Chrome or Edge
> through Chromium CDP, plus a separate Google Stitch API client and reusable Agent Skills. Web AI access
> still depends on the provider account, subscription, and usage limits.

---

## What Is This?

**AI Web Bridge** uses Playwright's Chrome DevTools Protocol (CDP) to automate a
dedicated, already-logged-in Chromium browser profile. Provider UI controls can
change and visible model choices depend on each signed-in account.

```
Your CLI (Antigravity / Cursor / Aider…)
        │  writes a compact prompt or context packet
        ▼
  argon_bridge.py  ──CDP──►  Chrome or Edge (dedicated profile)
        │                      provider web UI
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
| **Browser-based AI queries** | Playwright CDP → configured Gemini, ChatGPT, or Claude adapter in Chrome or Edge |
| **Project/profile-scoped conversation metadata** | Stores provider chat URLs locally; does not store browser credentials or cookies |
| **Portable project handoff** | Bounded version 1 context packets with path-based sensitive-file exclusions |
| **Opt-in run metadata** | Local `--record-run` log stores references and provider metadata, never prompt or response contents |
| **Actionable bridge errors** | Distinguishes browser, login, selector, model, timeout, and response extraction failures |
| **Google Stitch UI generation** | Direct MCP API calls via `stitch_client.py` |
| **Token-conscious Agent Skills** | Skills favor compact context and concise output; savings depend on the CLI and task |
| **No hardcoded secrets** | All secrets via environment variables or `.env` |

### Current support status

| Area | Supported now | Not supported yet |
|---|---|---|
| Browser AI provider | Configured Gemini, ChatGPT, and Claude adapters; validate each signed-in UI before relying on it | Other browser AI sites; provider UI selectors can change and need validation against your signed-in account |
| Browser | Chrome and Microsoft Edge using Chromium CDP | Firefox, Safari, and other non-Chromium browser connections |
| Model selection | List and select visible model choices per configured provider; selection must be confirmed by the visible picker | Guaranteed access to account-restricted models or models not shown in your account |
| Multi-provider runs | Explicit sequential `--providers` / `--all`, separate response files and status summary | Concurrent fan-out; providers run one at a time |
| Project context | Explicit JSON packet, local provider/project chat URL metadata | Automatic access to CLI history, repository contents, or another provider’s chat |

---

## Token reduction goal

Reducing the coding CLI’s token use is a core project goal. The skills send
concise, task-relevant context and use the browser AI for substantial reasoning
or drafting. The CLI still needs enough information to
apply changes, and it consumes tokens when it reads responses. Results therefore
vary by task and CLI; this project does not promise a fixed savings percentage.

For best results, pass only the relevant excerpts or diff, request a concise
answer or unified diff, and avoid unnecessary browser-AI follow-up calls. A web
AI account may still have subscription fees, message caps, or other limits.

---

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Bridge scripts |
| pip / uv | latest | Package management |
| playwright | 1.40+ | Chrome automation |
| Chrome or Microsoft Edge | Chromium-based | Dedicated logged-in browser profile |

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

### 2. Launch Chrome or Edge with remote debugging

**Windows:**
```bat
bridge\launch_chrome.bat
```

**Mac / Linux:**
```bash
bash bridge/launch_chrome.sh
```

A browser window opens. Log in to the selected provider in its dedicated
profile and keep the window open.

### 3. Send your first prompt

```bash
echo "What is the time complexity of quicksort?" > _argon_prompt.txt
python bridge/argon_bridge.py --prompt-file _argon_prompt.txt --out _argon_response.md
cat _argon_response.md
```

For coding work, pass a compact JSON context packet. Review the exact assembled
prompt locally before sending, then opt in to a metadata-only run record if useful:

```bash
python bridge/argon_bridge.py --context-file _argon_context.json --review-context
python bridge/argon_bridge.py --context-file _argon_context.json --out _argon_response.md --record-run
```

The context packet is capped at 24,000 characters by default. Sensitive-looking
file paths are excluded and truncation is reported. This path filter does not
scan ordinary file contents for secrets, so include only excerpts you intend to
send. `--record-run` stores provider/model labels, a sanitized chat URL, local
file references, and time in `.ai-web-bridge/runs.jsonl`; it never stores prompt,
context, or response contents.

---

## Environment Variables

Browser configuration is read from process environment variables or CLI flags.
The bridge does not load browser settings from `.env` automatically:

| Variable | Default | Description |
|---|---|---|
| `BROWSER` | `chrome` | `chrome` or `edge` |
| `BROWSER_EXE` | detected | Optional full path to Chrome or Edge executable |
| `BROWSER_PROFILE_DIR` | provider-specific | Shared profile override; pair it with `CDP_PORT` to reuse one browser endpoint. Otherwise use the provider-specific profile variables below |
| `CHROME_PROFILE_DIR` | Gemini profile | Legacy Gemini profile override |
| `CHATGPT_PROFILE_DIR` | ChatGPT profile | ChatGPT profile override |
| `CLAUDE_PROFILE_DIR` | Claude profile | Claude profile override |
| `CDP_HOST` | `127.0.0.1` | CDP host; local loopback is the default |
| `GEMINI_CDP_PORT` | `9222` | Gemini browser CDP port |
| `CHATGPT_CDP_PORT` | `9223` | ChatGPT browser CDP port |
| `CLAUDE_CDP_PORT` | `9224` | Claude browser CDP port |
| `CDP_PORT` | `9222` | Shared endpoint override when `BROWSER_PROFILE_DIR` is set; also overrides Gemini’s default port |
| `CHROME_DEBUG_PORT` | — | Legacy Gemini CDP port alias |
| `STITCH_API_KEY` | *(required for Stitch)* | API key from https://aistudio.google.com/apikey |

Browser bridge settings can also be passed with `--browser`, `--profile-dir`,
`--cdp-host`, and `--cdp-port`. Bridge settings are read from process
environment variables; the bridge does not load `.env` automatically. The
Stitch client can read `STITCH_API_KEY` from `.env`.

---

## Bridge CLI Flags (`argon_bridge.py`)

| Flag | Description |
|---|---|
| `--prompt-file FILE` | Path to a `.txt` file containing the prompt |
| `--context-file FILE` | Version 1 JSON context packet (see [Context packet](#context-packet)) |
| `--context-limit-chars N` | Maximum assembled context size (default: 24,000) |
| `--review-context` | Print the exact assembled prompt and exit without opening a browser |
| `--record-run` | Opt in to local metadata-only logging under `.ai-web-bridge/runs.jsonl` |
| `--diagnostics-dir DIR` | Opt in to page screenshots on query errors; screenshots can contain private chat data |
| `--prompt TEXT` | Inline prompt text (alternative to `--prompt-file`) |
| `--provider NAME` | Select `gemini` (default), `chatgpt`, or `claude` |
| `--providers IDS` | Explicit multi-provider run, e.g. `gemini,chatgpt` |
| `--all` | Send the same prompt/context to every configured provider (explicit opt-in) |
| `--provider-model ID=LABEL` | Set a provider-specific visible model; repeat as needed |
| `--compare-provider NAME` | Ask a chosen provider to synthesize successful responses from at least two providers |
| `--list-providers` | List configured providers and their adapters |
| `--out FILE` | Write the response to this file (default: stdout) |
| `--new-chat` | Start a brand-new conversation thread |
| `--timeout SECS` | Maximum seconds to wait for a response (default: 300) |
| `--model NAME` | Select a unique matching label from the selected provider’s visible model picker |
| `--list-models` | List model choices visible for the selected provider |
| `--launch-only` | Launch the configured browser and exit |
| `--doctor` | Check the browser endpoint and selected provider page without sending a prompt |
| `--browser chrome\|edge` | Select the Chromium browser |
| `--cdp-host HOST` | Override the CDP host |
| `--cdp-port PORT` | Override the CDP port |
| `--profile-dir DIR` | Override the dedicated browser profile directory |

Each provider gets its own browser profile and CDP port by default. Sign in to
each site once in the corresponding profile. For example:

```bash
python bridge/argon_bridge.py --provider chatgpt --launch-only
python bridge/argon_bridge.py --provider chatgpt --list-models
python bridge/argon_bridge.py --provider chatgpt --model "visible model label" --prompt "Review this design"

python bridge/argon_bridge.py --provider claude --launch-only
python bridge/argon_bridge.py --provider claude --list-models
```

Model choices are read from the signed-in account’s visible menu. A model may
not be available under every plan or workspace, and model labels can change.

### Verification status

Offline regression checks pass with `python -m unittest discover -s tests -v`.
They cover configuration and provider loading, context filtering and limits,
project-scoped session metadata, stored-URL validation, separate response
paths, and bounded comparison prompts. They use no browser and send no prompts.

Live Chrome checks were run in the bridge's isolated `ArgonChromeProfile`, not
the user's everyday Chrome profile. Gemini passed browser launch, CDP
connection, `--doctor` after the page settled, `--list-models`, and a minimal
prompt/response check. ChatGPT and Claude pages loaded (HTTP 200), but their
inputs were unavailable because those isolated profiles were not signed in;
no prompts were sent to them. The user's Chrome profile path/name has not yet
been provided, so it has not been tested. Edge end-to-end verification also
remains pending. Provider selectors can change; before relying on another
combination, run `--doctor`, `--list-models`, and one small, non-sensitive
prompt in the intended signed-in profile:

| Provider | Chrome | Edge |
|---|---|---|
| Gemini | Isolated profile: launch, doctor, model listing, and minimal prompt passed; user's profile pending | Pending live check |
| ChatGPT | Pending live check | Pending live check |
| Claude | Pending live check | Pending live check |

### Troubleshooting and migration

- Run `python bridge/argon_bridge.py --doctor --provider gemini` (or
  `chatgpt`/`claude`) to check CDP reachability and whether the provider's chat
  input is visible. It sends no prompt.
- If CDP is unreachable, start the dedicated browser with
  `bridge/launch_chrome.bat` or `bridge/launch_chrome.sh`; confirm that the
  selected `--browser`, profile directory, and port match the running browser.
- If sign-in times out, finish sign-in in that dedicated profile and rerun
  `--doctor`. If the input or model picker is missing, the provider UI may have
  changed; verify the visible page before updating selectors.
- To diagnose query failures with a screenshot, explicitly pass
  `--diagnostics-dir ./private-diagnostics`. The screenshot contains the
  browser page and may include private prompts or replies; keep that directory
  local and delete it when finished. No screenshot is saved by default.
- Existing Gemini use remains the default: `python bridge/argon_bridge.py`
  still selects Gemini. Legacy `CHROME_PROFILE_DIR` and
  `CHROME_DEBUG_PORT` remain supported as Gemini aliases. New setups should use
  `GEMINI_CDP_PORT` and the provider-specific profile variables. Old Gemini
  chat URLs in `.ai-web-bridge/sessions.json` continue to resume if their host
  matches the configured provider; remove a bad or edited entry and retry.

Run the offline regression checks with `python -m unittest discover -s tests -v`.
They do not launch a browser or contact a provider. Live site checks require a
signed-in dedicated Chrome or Edge profile and should be recorded separately.

### Multi-provider runs

Multi-provider runs are opt-in because each selected website receives the same
prompt/context and total provider usage increases. Runs execute sequentially,
which also avoids collisions when profiles or CDP endpoints are shared. Each
provider gets a distinct output file; a failure or timeout for one provider
does not remove results already saved by the others. The command prints the
selected destinations and a per-provider status/model/duration summary.

```bash
# Save one output per provider (_argon_response_<provider>.md by default)
python bridge/argon_bridge.py --providers gemini,chatgpt --context-file _argon_context.json

# Use account-visible, provider-specific model names
python bridge/argon_bridge.py --all --context-file _argon_context.json \
  --provider-model gemini="visible Gemini model" \
  --provider-model chatgpt="visible ChatGPT model" \
  --out _argon_response.md

# Optional synthesis; original answers remain in their own files
python bridge/argon_bridge.py --providers gemini,chatgpt --context-file _argon_context.json \
  --compare-provider claude
```

When `--out BASE` is supplied, the bridge writes `BASE.<provider>.response.md`
per provider and `BASE.<provider>.comparison.md` for optional synthesis. The
comparison provider receives a bounded excerpt of the original context and the
successful provider responses. A timeout is applied independently to each web
request. Pressing Ctrl+C stops the active run; response files already completed
remain on disk.

### Context packet

See [CONTEXT_PACKET.md](CONTEXT_PACKET.md) for the complete schema and handling
rules.

Create a UTF-8 JSON file with `version: 1` and a non-empty `task`. Optional
fields are `project_summary`, `recent_changes`, `errors` (string array),
`constraints` (string array), `requested_output`, and `files` (array of
`{"path": "relative/path", "content": "selected excerpt"}`). Use excerpts or
focused diffs and keep the task summary concise. `.env*` files except
`.env.example`, private-key files, and paths named like credentials or secrets
are excluded by path. The bridge does not read the whole repository or discover
files automatically. Use `--review-context` before submission when you want to
inspect the exact payload.

### Install the skills

The canonical workflow is `skills/use-argon-web/SKILL.md`; the shorter
`skills/ask-argon-web/SKILL.md` keeps the alternate trigger working. The
per-tool install locations and direct invocation examples are in
[SKILL_SPEC.md](SKILL_SPEC.md). A coding CLI can load skills or instructions;
browser AI websites do not read local skill files. For website-only use, prepare
or review the prompt/context locally and paste it manually.

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

`skills/use-argon-web/` is the canonical, provider-neutral workflow.
`skills/ask-argon-web/` is a short compatibility trigger. Installation steps
for Gemini CLI, Claude Code, Cursor, Aider, plain scripts, and browser-only use
are in [SKILL_SPEC.md](SKILL_SPEC.md).

| Skill folder | What it does |
|---|---|
| `skills/use-argon-web/` | Delegate to a configured Gemini, ChatGPT, or Claude browser adapter |
| `skills/ask-argon-web/` | Short alias that points to the canonical workflow |
| `skills/stitch-design/` | Full UI design lifecycle with Google Stitch |

Browser AI websites do not read these local skill files. Browser-only users
must manually paste a compact, reviewed prompt/context packet and copy the
answer back. They do not get automatic local-file or cross-provider history
access.

---

## Adding another browser AI provider

The bridge separates provider configuration (`bridge/providers.json`) from UI
behavior (`bridge/providers/`). Gemini, ChatGPT, and Claude adapters are
configured. Adding another provider requires its adapter class, selectors, and
provider configuration. Editing selectors in JSON alone does not enable a new
site; login, model picker, response completion, and extraction behavior must be
implemented. Web UI selectors can change. Use `--doctor` to check the page/input
and `--list-models` to inspect visible model options; make a normal query to
verify response extraction for your account.

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
│   ├── config.py                 # Provider config and browser settings
│   ├── providers.json            # Gemini URL, CDP defaults, selectors, timeouts
│   ├── sessions.py               # Local provider/project chat metadata
│   └── providers/
│       ├── base.py               # Adapter contract and error types
│       ├── gemini.py             # Gemini browser UI adapter
│       ├── selector_chat.py      # Shared configurable chat interaction
│       ├── chatgpt.py            # ChatGPT provider adapter
│       └── claude.py             # Claude provider adapter
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
- AI Web Bridge default browser profiles are `ArgonChromeProfile`,
  `ArgonEdgeProfile`, and `AIWebBridge*Profile`; these are gitignored if placed
  inside the repository. Do not commit or share any browser profile directory.
- The CDP debugging endpoint can control the signed-in browser session. Keep it
  bound to loopback (`127.0.0.1`); only point `CDP_HOST` at a remote endpoint
  that you control and trust. Do not expose the debugging port to a network.
- Browser launchers allow only the `localhost` and `127.0.0.1` origins for
  their configured CDP port; they do not use a wildcard origin allowlist.
- Diagnostic screenshots are disabled by default. `--diagnostics-dir` opts in
  to saving full browser screenshots, which can include private chat content.
- The default Edge profile (`ArgonEdgeProfile/`) is gitignored as well.
- `.ai-web-bridge/sessions.json` stores a hashed project key, provider name,
  chat URL path, and timestamp. It is gitignored and does not store cookies or
  credentials.
- CDP grants powerful control over the browser. Keep the endpoint on localhost
  unless you intentionally configure and secure a remote endpoint.
- The bridge only automates your own logged-in session. It does not create
  accounts or bypass authentication.

---

## Contributing

PRs welcome! Priority areas:
- New provider adapters (Claude, ChatGPT, Grok…)
- Better response extraction heuristics
- Windows/Mac parity for Chrome launcher
- Tests

---

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
