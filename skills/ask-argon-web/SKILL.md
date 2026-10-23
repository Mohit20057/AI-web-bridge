---
name: ask-argon-web
description: |
  Delegate queries, coding tasks, architecture designs, multi-turn reasoning,
  and debugging to web AI models (Gemini Argon, Claude, ChatGPT, Grok, Blackbox)
  running in your own logged-in browser — no API key required.
  Supports multi-AI sequential handoffs, "all on one" council consensus, and
  self-healing error loops.
  Activate whenever the user says:
  - "ask argon"
  - "use argon web"
  - "use argon"
  - "use chatgpt"
  - "use claude"
  - "use grok"
  - "use blackbox"
  - "ask council" / "ask all ais"
license: Apache-2.0
metadata:
  version: v3
  author: Mohit20057
  repo: https://github.com/Mohit20057/AI-web-bridge
---

# Multi-AI Web Bridge (Gemini, ChatGPT, Claude, Grok, Blackbox)

This skill connects any AI coding CLI (Antigravity, Cursor, Aider, Claude Code)
directly to your logged-in browser AI models via the zero-click background extension
and CDP bridge. No API keys. Zero token costs.

---

## CRITICAL RULES (Read Every Time)

1. **MULTI-TURN PERSISTENCE (DO NOT STOP AFTER 1 OUTPUT)**
   - When the user asks to use web AI for a task, you are in **AI-Assisted Mode**.
   - For multi-step tasks, follow-up questions, or code-then-test cycles,
     **continue consulting the web AI for every subsequent step or error**.
   - Do NOT stop after 1 output or revert to answering alone unless the user
     explicitly says to exit this mode.

2. **SESSION CONTINUITY**
   - **New unrelated task**: pass `--new-chat` to start a fresh conversation thread.
   - **Follow-up / sub-step**: **omit `--new-chat`** so the web AI remembers previous context.

3. **MULTI-AI COMMUNICATION PATTERNS**
   - **Sequential Handoff (Relay)**:
     When using different AIs for different parts (e.g. Claude for architecture ➔
     ChatGPT for backend ➔ Gemini for frontend/docs):
     Extract the clean code or spec from AI #1, build a clean prompt in `_argon_prompt.txt`,
     and pass it to AI #2 with `--provider <next_provider>`.
   - **"All on One" (Council / Consensus Mode)**:
     When multiple models should evaluate the exact same tough problem:
     Use `--providers gemini,chatgpt,claude --compare-provider gemini` to collect
     all perspectives and produce an evaluated, synthesized consensus answer in `_argon_comparison_gemini.md`.
   - **Contract-First Domain Division**:
     When models work on different layers (frontend vs backend), lock the interface
     file (`types.ts` or `openapi.json`) on disk first. Instruct both models to adhere
     strictly to that contract.

4. **SELF-HEALING ERROR LOOP**
   - If code from any web AI fails with an error, do NOT give up or rewrite yourself.
   - Capture the full traceback, form a debugging prompt
     (*"Your previous solution gave this error: [traceback]. Please fix it."*),
     and call the bridge again. You can also pass the error to another provider for a second opinion.

---

## Execution Workflows

### 1. Standard Single AI Query (Default: Gemini)
```bash
echo "Explain this codebase" > _argon_prompt.txt
python bridge/argon_bridge.py --browser-mode extension --provider gemini --prompt-file _argon_prompt.txt --out _argon_response.md
```
*(Replace `--provider gemini` with `chatgpt`, `claude`, `grok`, or `blackbox` as requested).*

### 2. "All on One" Council Mode (Consensus & Synthesis)
When solving a difficult bug or architectural decision where multiple models should debate:
```bash
python bridge/argon_bridge.py --browser-mode extension \
    --providers gemini,chatgpt,claude \
    --compare-provider gemini \
    --prompt-file _argon_prompt.txt \
    --out _council_result.md
```
1. Queries each provider in turn on their open tabs.
2. Hands all candidate solutions to the comparison provider (`gemini`).
3. Reads the synthesized, consensus-verified solution from `_argon_comparison_gemini.md`.

### 3. Sequential Multi-AI Handoff
1. **Turn 1 (Claude - Architecture):**
   ```bash
   python bridge/argon_bridge.py --browser-mode extension --provider claude --prompt-file _arch_prompt.txt --out _arch_spec.md
   ```
2. **Turn 2 (ChatGPT - Backend Implementation):**
   Create `_backend_prompt.txt` bundling `_arch_spec.md` + task:
   ```bash
   python bridge/argon_bridge.py --browser-mode extension --provider chatgpt --prompt-file _backend_prompt.txt --out _backend_code.md
   ```
3. Apply files to project and run tests.
