---
name: stitch-design
description: |
  Design UI pages and full applications with Google Stitch (stitch.withgoogle.com)
  via the Stitch MCP API, download the generated assets (HTML & screenshots),
  and implement them into the project codebase.
  Activate whenever the user says:
  - "use stitch"
  - "use stitch for design"
  - "design with stitch"
  - "generate UI with stitch"
  - or wants to use Google Stitch for application or website design.
license: Apache-2.0
metadata:
  version: v2
  author: Mohit20057
  repo: https://github.com/Mohit20057/AI-web-bridge
---

# Google Stitch UI Design & Implementation

This skill drives the complete UI/UX design workflow using **Google Stitch**
(`stitch.withgoogle.com`), downloads screen assets, and translates the generated
designs into production-ready code in the user's project.

---

## Prerequisites

1. **Stitch API key** — get one at https://aistudio.google.com/apikey
2. Set the key in your environment:
   ```bash
   # Windows
   set STITCH_API_KEY=your_key_here

   # Mac / Linux
   export STITCH_API_KEY=your_key_here
   ```
   Or put it in a `.env` file in the project root:
   ```
   STITCH_API_KEY=your_key_here
   ```

3. **Python 3.11+** — the scripts use only the standard library; no extra packages needed.

---

## CRITICAL RULES (Read Every Time)

1. **MULTI-TURN PERSISTENCE — DO NOT STOP AFTER 1 SCREEN**
   When the user asks for a feature or website, carry out the entire lifecycle:
   1. Design the anchor screen (Home/Landing).
   2. Generate follow-up screens (Pricing, Dashboard, etc.) keeping style consistent.
   3. Download HTML and screenshot assets into `design/stitch/`.
   4. Translate the HTML into the project's actual frontend framework (React, Vue, etc.).
   5. Test and visually verify against the screenshot.
   6. Ask the user if revisions or additional screens are needed.

2. **ONE STITCH PROJECT PER REPOSITORY**
   - Check `.stitch/project.json`.
   - If it exists, reuse its `projectId`. Never create duplicate projects.
   - If missing, create one named after the current repo/workspace and save:
     `{ "projectId": "...", "title": "...", "screens": {} }`

3. **ANCHOR PATTERN FOR VISUAL CONSISTENCY**
   - The first generated screen is the "Anchor".
   - Before prompting subsequent screens, inspect its palette, typography, and
     card styles, and explicitly append:
     *"Keep the exact same visual style, colors, and typography as the anchor page."*

4. **REFERENCE CODE VS. PRODUCTION CODE**
   - Files in `design/stitch/` are reference designs.
   - Translate them cleanly into the project's own design tokens, components,
     and structure. Do not blindly copy-paste raw export code.

---

## Execution Methods

You can interact with Stitch in two ways:

### Option A — Direct MCP Tools (if loaded in the session)
Call the following tools directly if they are available:
- `create_project`
- `list_projects`
- `generate_screen_from_text`
- `get_screen`
- `list_screens`
- `edit_screens`

*(Tools may have prefixes such as `mcp__stitch__` depending on your CLI.)*

### Option B — CLI Script (always available)
Use `scripts/stitch_client.py` (set `STITCH_API_KEY` first):

```bash
# List projects
python scripts/stitch_client.py list

# Create project
python scripts/stitch_client.py create --title "My App"

# Generate screen
python scripts/stitch_client.py generate \
    --project-id "<PROJECT_ID>" \
    --prompt "<PROMPT>" \
    --device DESKTOP

# List screens
python scripts/stitch_client.py screens --project-id "<PROJECT_ID>"
```

---

## Step-by-Step Workflow

### Step 1 — Analyze Project Context & Write Brief
1. Inspect the codebase: check `package.json`, styling framework (Tailwind, CSS
   modules, Shadcn UI), component library, brand colors, and assets.
2. Write `design/stitch/brief.md` containing:
   - Target audience & goal
   - Required pages/screens
   - Style direction (colors, mood, typography)
   - Real copy (avoid lorem ipsum)

### Step 2 — Formulate Stitch Prompts
Write high-fidelity prompts using the template at:
`references/prompt-template.md`
- Specify platform (`DESKTOP` or `MOBILE`).
- Include explicit hex codes with functional roles.
- Structure top-to-bottom layout with real content.

### Step 3 — Generate Screen in Stitch
1. Call `generate_screen_from_text` with `projectId` and the formulated prompt.
2. **Polling**: Generation takes 30–90 seconds. If the call times out,
   poll `list_screens` every 15–30 seconds until the new screen appears.
3. Record the screen ID in `.stitch/project.json` under `screens`
   (e.g. `"home": "<screen_id>"`).

### Step 4 — Download Design Assets
Call `get_screen` to obtain the HTML and screenshot URLs, then run:
```bash
python scripts/fetch_assets.py \
    --name <page-name> \
    --html "<html_url>" \
    --image "<image_url>" \
    --out design/stitch
```
This saves:
- `design/stitch/<page-name>.html`
- `design/stitch/<page-name>.png`

### Step 5 — Implement into Project Stack
1. Read `design/stitch/<page-name>.html`.
2. Break it into modular components matching the repository's framework
   (e.g. `Header`, `Hero`, `Features`, `Footer`).
3. Wire up responsive layouts and interactions.
4. Run the project build or dev server to verify no errors.

### Step 6 — Multi-Turn Iterations & Edits
- If the user asks to modify a screen:
  - Call `edit_screens` with the `screenId` and precise instructions.
  - Re-fetch assets using Step 4.
  - Update component code per Step 5.
- If additional screens are needed, repeat Steps 2–5 referencing the anchor design.

---

## Adapter Notes for Other CLIs

| CLI | How to use this skill |
|---|---|
| **Gemini CLI / Cursor** | Install this folder in `.agents/skills/stitch-design/` |
| **Claude Code** | Install this folder in `.claude/skills/stitch-design/` |
| **Aider** | Load the relevant instructions with `aider --read` when needed |
| **Claude Code** | Paste the rules section into `CLAUDE.md` |
| **Plain script** | Run `scripts/stitch_client.py` from this folder |

See [`SKILL_SPEC.md`](../../SKILL_SPEC.md) for the full adapter guide.
