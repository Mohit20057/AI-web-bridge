---
name: use-argon-web
description: |
  Delegate a question or coding task to a configured browser-based Gemini,
  ChatGPT, or Claude session through AI Web Bridge. Activate when the user says
  "use argon", "ask argon", "use argon web", or asks to consult browser AI.
license: Apache-2.0
metadata:
  version: v5
  author: Mohit20057
  repo: https://github.com/Mohit20057/AI-web-bridge
---

# Use AI Web Bridge

Send substantial reasoning or drafting to the selected browser AI. Keep CLI
context, returned text, and round trips small; savings depend on the task.

## Rules

- Choose the browser once per chat. Reuse a browser the user named earlier in
  this conversation. If they have not chosen one, ask once which to use (Chrome
  or Edge), remember it for this chat, and pass it with `--browser` on each
  bridge call. Ask again only if the user requests a change.
- Use one provider by default. Preserve that provider's chat for follow-ups. A
  different provider cannot see the old provider's history, so give it a small
  handoff packet.
- Never send the full CLI transcript, repository, or unchanged files. Include
  only the task, relevant changes/errors, constraints, and selected excerpts.
- Ask for a concise answer, focused diff, or exact replacement. Read only the
  output needed to apply the answer; do not restate its reasoning.
- Use `--providers` or `--all` only when the user requests multiple opinions.
  Every selected site receives the same context and provider use increases.
  Prefer `--compare-provider` over loading all answers into CLI context.
- Include only content appropriate to send to a web service. The bridge filters
  common secret-looking paths, but does not scan ordinary file contents.
- The bridge keeps a compact, project-local handoff from submitted context
  packets (task, project summary, and recent changes only). Use `--no-handoff`
  for a request that should neither read nor save it; use the forget options to
  clear saved data. Never place selected file contents or full chat transcripts
  into the handoff.

## Workflow

1. Resolve `BRIDGE_SCRIPT` to the repository's `bridge/argon_bridge.py`.
   Setup and browser-specific options are in the repository README.
   After changing provider or browser profile, run `--doctor` once; don't repeat
   it for every follow-up unless sign-in or browser state changed.
2. For project work, prepare `_argon_context.json` with `version: 1`, a short
   `task`, and only necessary `project_summary`, `recent_changes`, `files`,
   `errors`, `constraints`, or `requested_output` fields. The bridge carries
   forward a missing project summary or recent-changes note from its compact
   local handoff, including when switching providers. Use selected snippets or
   focused diffs; don't inspect more files just to fill the packet. For a
   simple question, use `_argon_prompt.txt` or `--prompt`.
3. Before sending sensitive context or when the user asks to review it, run
   `python "$BRIDGE_SCRIPT" --context-file _argon_context.json --review-context`.
   This prints the exact payload and does not contact a provider. Avoid reading
   the full preview into the CLI's model context unless it is needed for review.
4. Send one request and save the result:

   ```sh
   python "$BRIDGE_SCRIPT" --context-file _argon_context.json --out _argon_response.md
   ```

   For a simple prompt, use `--prompt-file _argon_prompt.txt`. To start fresh,
   add `--new-chat`. Select a provider with `--provider NAME`; inspect visible
   models using `--provider NAME --list-models`, then use `--model LABEL` only
   when the user wants a specific available model. Use repeated
   `--provider-model ID=LABEL` for different models in an explicit fan-out.
5. Read the concise response, apply or present it, and stop. Make one focused
   follow-up only if the result is incomplete, an error needs diagnosis, or the
   user asks. Clean temporary packet/prompt/response files when the task ends.

For an explicitly requested multi-provider run, use
`--providers gemini,chatgpt` or `--all`. The bridge saves one result per site
and prints a status summary. This is always opt-in because every selected site
receives the same task context. Add `--compare-provider NAME` only when
synthesis helps; its bounded comparison is saved separately.

For browser-profile selection, readiness checks, local-data cleanup, and
measured token comparisons, consult [advanced options](references/advanced-options.md)
only when that feature is needed.

## Browser-only use

Browser AI websites do not load this skill, local CLI history, or repository
files. A browser-only user must prepare or review a compact prompt/context
packet locally, paste it into the website, and carry the answer back manually.
No cross-site history or local-file access is implied.

See [SKILL_SPEC.md](../../SKILL_SPEC.md) for per-CLI installation paths and the
common invocation examples.
