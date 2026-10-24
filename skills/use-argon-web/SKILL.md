---
name: use-argon-web
description: Delegate queries, coding pipelines, reviews, and consensus to browser web AI models.
---
# AI Web Bridge (Gemini, Claude, ChatGPT, Grok, Blackbox)

CLI orchestrator connecting coding agents to logged-in browser AI models via loopback. Zero API keys.

## Agent Rules
1. Always run `bridge sync` before invoking any AI.
2. Pass FILE PATHS by reference (`--task-file`, `--in`, `--context-files`), NEVER paste full file contents into prompts.
3. Read ONLY the one-line CLI result and `bridge status`. Never inspect raw web UI responses.
4. Always verify `verify=PASS` and `status=COMPLETE` before applying code changes.

## Trigger Workflows
- **"use Argon web"** (Single query):
  `bridge --provider gemini --prompt "..."` or `--task-file task.txt --out result.md`
- **"build X with the bridge"** (Relay pipeline: Claude architect -> ChatGPT engine -> Gemini ui -> verify -> review):
  `bridge --pipeline pipeline.yaml`
- **"ask the council"** (Round 1 independent debate + Round 2 synthesis):
  `bridge --council --providers gemini,claude,chatgpt --compare-provider claude --task-file task.txt`
- **"review this with Claude"** (Reviewer role comparing implementation vs contract):
  `bridge --role reviewer --contract spec.md --in engine.js --provider claude`
- **"continue with {AI}" / "switch to {AI}"**:
  `bridge sync` then `bridge handoff --to {AI} --goal "..."`

*Detailed command documentation, flags, and pipeline schemas are in `docs/`.*
