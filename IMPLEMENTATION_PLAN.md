# AI Web Bridge Implementation Plan

## Goal

Reduce the coding CLI’s token use whenever these skills activate. This is a primary product requirement, not a secondary benefit. The bridge should move substantial reasoning and drafting to the browser AI while keeping the CLI’s context, round trips, and returned payload as small as the task allows. Do not claim savings without measuring them against a comparable CLI-only workflow.

Evolve AI Web Bridge from a Gemini-on-Chrome script into a provider-based bridge that can use browser-hosted AI assistants, preserve project context across providers, and be invoked consistently by coding CLIs through reusable skills.

This plan covers implementation and updates to the repository’s Agent Skills. It does not assume that browser AI websites automatically load local skills or expose stable model controls.

## Current state and gaps

- `bridge/argon_bridge.py` now routes through configured Gemini, ChatGPT, and Claude adapters; only Gemini, ChatGPT, and Claude are configured.
- Chrome and Edge use Chromium CDP, with separate default profiles and ports for each provider.
- `--provider`, `--list-providers`, provider-aware `--list-models`, and unique/verified model selection are implemented.
- ChatGPT and Claude selectors are provider-specific but have not yet been exercised against signed-in browser sessions; provider UI validation remains necessary.
- The README and skill format now match the implemented provider and browser scope.
- Skills now prepare bounded portable project context packets and support opt-in, sequential multi-provider fan-out.
- A browser AI conversation still cannot automatically see local files, CLI history, or another provider’s conversation.

## Proposed user experience

```text
CLI agent + skill
  ├─ prepares a small context packet from the task, selected files, and changes
  ├─ invokes the bridge with a provider and optional model request
  └─ reads the result and continues the task
          │
          ▼
Bridge CLI → provider adapter → browser/profile → web AI
          ├─ one provider: one browser conversation
          └─ multiple providers: separate conversations and output files
```

A project context packet is explicit input to each request. The provider’s own chat history may help within that provider, but is not treated as shared project memory.

## Design decisions

1. **Provider and browser are separate settings.** A provider defines the website and UI behavior. A browser connection defines how the browser is reached or launched.
2. **Start with adapters, not one universal selector set.** Each provider owns its URL, selectors, completion detection, model-picker behavior, and limitations.
3. **Support Chromium CDP first.** Add Chrome and Edge as the first documented browser options. Other Chromium browsers are best-effort. Firefox/WebKit support should use Playwright-managed persistent profiles and be a later milestone; it is not CDP attachment.
4. **Treat model selection as account/UI-dependent.** List visible choices, select by a provider-specific match, and verify the active choice. Never claim success if verification fails.
5. **Make context sharing visible.** The skill prepares bounded context from task inputs; it does not silently upload the entire repository.
6. **Keep provider chats isolated.** Each provider gets its own page/session and result. Requests to one profile are serialized to avoid interleaved prompts.
7. **Optimize for CLI token use.** Send only task-relevant context and the recent delta; request concise, directly usable output; avoid unnecessary browser-AI round trips and repeated history. Measure CLI token usage where the CLI exposes it.
8. **Keep a canonical skill.** Make `use-argon-web` the canonical skill initially and turn `ask-argon-web` into a small compatibility entry that points to it. Consider a neutral rename only with a migration note.

## Phase 0 — Align documentation with reality (complete)

**Changes**

- Rewrite README’s opening and feature list to say the current implementation is Gemini on Chrome until multi-provider support lands.
- Remove or correct claims of universal browser/provider support, guaranteed token savings, “zero cost,” and support for `--target` until implemented.
- Add a feature-status table: implemented, planned, and provider/browser-specific limitations.
- Add a browser and provider support matrix that distinguishes verified support from best-effort support.

**Completion criteria**

- Every README command and flag matches the parser.
- Marketing text does not promise support that the code does not provide.

## Phase 1 — Define provider and session contracts (complete)

**Changes**

- Add a provider configuration format (for example `bridge/providers.yaml`) with provider name, URL, browser connection, selectors, timeout behavior, and model-picker configuration.
- Define a small adapter interface: `connect`, `open_or_resume_chat`, `list_models`, `select_model`, `send_prompt`, `wait_for_response`, and `close`.
- Move Gemini selectors and interaction logic behind a Gemini adapter without changing the current default behavior.
- Add a session record keyed by provider and project, storing only non-secret metadata such as provider name, last known chat URL, and timestamps. Do not store cookies or credentials.
- Define clear errors for browser unavailable, login required, selector mismatch, model unavailable, timeout, and response extraction failure.

**Completion criteria**

- Gemini works through the adapter with the same basic CLI workflow.
- Adding a provider does not require editing shared orchestration code.
- Session metadata never contains browser cookies or credentials.

## Phase 2 — Browser connection options (complete)

**Changes**

- Add CLI/config options for browser type, CDP endpoint/port, and dedicated profile directory.
- Implement Chromium CDP connections for Chrome and Edge, with separate ports and profiles for concurrent browser sessions.
- Make browser launch behavior explicit: detect an existing endpoint or launch the configured browser; do not silently connect to an arbitrary daily-use profile.
- Add a `status`/`doctor` command that checks configuration, endpoint reachability, current page, login/input availability, and provider readiness without sending a prompt.
- Document how users sign in once to each dedicated profile.

**Completion criteria**

- Users can select supported Chromium browsers without modifying Python constants.
- The status command explains the next corrective action when setup is incomplete.
- Default CDP endpoints bind to localhost and are never exposed publicly by the launcher.

## Phase 3 — Provider adapters and model controls (implemented; live UI validation pending)

**Changes**

- Add adapters one at a time, starting with Gemini, then ChatGPT and Claude after verifying each current UI flow.
- Add `--provider NAME`, `--list-providers`, and provider-aware `--list-models` commands.
- Make `--model` select from the visible model menu and verify the selected label before submission.
- If the requested model is absent or ambiguous, stop before sending and show the available choices.
- Add provider-specific response completion detection and extraction; do not reuse Gemini selectors for other sites.
- Record provider/version selector assumptions in adapter docs so UI changes can be maintained independently.

**Completion criteria**

- Each provider clearly reports whether it supports listing and selecting models.
- A model request is either confirmed or fails clearly; it is never silently ignored.
- Unsupported providers and inaccessible model options are described without claiming a specific account entitlement.
- ChatGPT and Claude selectors have not yet been exercised against the user's signed-in sessions; verify those UI flows before treating the adapters as stable.

## Phase 4 — Project context and history handoff (implemented; manual provider validation pending)

**Changes**

- Define a portable context packet format containing: task goal, relevant project facts, selected files/snippets, recent changes, errors, constraints, and the next question/action.
- Update the canonical skill so the CLI prepares a compact packet before calling any provider. Prefer a short summary and relevant diff/snippets over full files, full chat history, or broad repository dumps.
- Prefer explicitly selected files and relevant diffs; set size limits and tell the user when context is truncated. Include a token-conscious budget and remove redundant context before submission.
- Add optional local run records containing prompt/context references, provider, model label, chat URL, and output path. Make storage opt-in or clearly configurable, and add generated data to `.gitignore`.
- Add `--context-file` to send an already prepared packet. Keep bridge output separate from the context packet. Ask the browser AI for the smallest useful result: a unified diff, exact replacement, concise decision, or short diagnosis, as appropriate.
- Add `--review-context` to print the exact assembled payload without opening a browser, and `--context-limit-chars` with a 24,000-character default, visible truncation/exclusion notes, and actionable overflow errors.
- Add `--record-run` as an explicit opt-in. Append provider and selected model labels, sanitized chat URL, input/output references, project identifier, and timestamp only; never persist prompt, context, or response contents.
- Exclude common sensitive-looking paths (`.env*` except `.env.example`, private-key files, and credential/secret paths) from packet file excerpts. Document that this is path-based filtering and does not scan included file contents.
- Tell the CLI skill to summarize accepted changes back into project notes when the user requests durable project memory; do not silently rewrite project docs.

**Completion criteria**

- Skills default to selected excerpts and focused changes, with no full transcript, repository, or unchanged-file replay.
- A packet is validated and assembled within the configured character cap; a review-only command is available before submission.
- Run records are off by default and metadata-only when enabled.
- Switching from Gemini to another provider sends the same compact project summary and relevant changes, without replaying the full conversation.
- A fresh chat can continue the task from the context packet without relying on another website’s chat history.
- Sensitive files are excluded by default or require explicit selection; context submitted to a web AI is visible to the user before submission when review mode is enabled.

## Phase 5 — Multi-provider runs (implemented; live provider validation pending)

**Changes**

- Add `--providers gemini,chatgpt` or `--all` to submit the same prepared context to multiple configured providers.
- Make fan-out explicit and print which providers receive the same context; keep single-provider mode as the default.
- Use provider-specific sessions and separate output files; run sequentially so shared CDP profiles cannot collide.
- Support shared `--model` and repeated `--provider-model ID=LABEL` overrides, verifying requested labels through each adapter before submission.
- Return a run summary with provider status, selected model label (when requested and verified), duration, output path, and failure reason. Continue after an individual provider fails or times out.
- Add optional `--compare-provider NAME` synthesis in a separate output, with bounded excerpts and original provider outputs preserved.
- Apply each provider's response timeout independently. Ctrl+C stops the active run while completed output files remain available.

**Completion criteria**

- One provider failing does not discard other provider responses.
- Replies cannot be written to the wrong provider’s output.
- The user can see exactly which providers received the prompt and which completed. Multi-provider mode is opt-in because duplicating full context across providers increases total usage and exposure.
- Optional synthesis is labeled and saved separately, and its assembled prompt is bounded.

## Phase 6 — Skill and CLI integration (implemented; CLI installation validation pending)

**Changes**

- Rewrite `skills/use-argon-web/SKILL.md` around the provider-neutral workflow: prepare context, select provider/model, invoke bridge, read result, continue or summarize.
- Replace `skills/ask-argon-web/SKILL.md` with a short compatibility skill that refers users/agents to the canonical workflow, or remove it in a documented major-version cleanup.
- Update `SKILL_SPEC.md` with installation/adaptation guidance for supported CLIs and the common invocation contract.
- Provide small adapters/examples for Gemini CLI, Claude Code, Cursor, Aider, and plain scripts; make clear that support means the CLI can read the skill and run the command.
- Explain that browser AI websites do not load `SKILL.md` by themselves. A browser-only user can paste the generated prompt/context packet; a browser extension is a separate future feature.
- Use a single documented executable name and stable arguments; provide a compatibility wrapper if renaming `argon_bridge.py`.
- Keep the canonical skill concise and provider-neutral; keep the alternate trigger as a short compatibility skill to reduce duplicated instruction tokens.

**Completion criteria**

- The skill avoids unnecessary CLI and browser-AI turns: it consults the browser AI for delegated reasoning/drafting, then follows up only when the answer is incomplete, an error needs diagnosis, or the user requests another pass.
- Each adapter example uses real flags and paths.
- CLI skill installation and browser-only usage are clearly distinguished.
- Gemini CLI, Claude Code, Cursor, Aider, and direct script examples use their supported skill/instruction loading paths and the same `bridge/argon_bridge.py` interface.

## Phase 7 — Validation, security, and release readiness (offline checks complete; Gemini live check partial)

**Planned verification**

- Unit-level checks for configuration parsing, provider routing, context packet assembly, and result naming.
- Manual end-to-end checks with dedicated test accounts/profiles for each supported provider and browser.
- Validate login-required, missing-selector, unavailable-model, timeout, partial multi-provider failure, and new-chat flows.
- Review prompt/output retention, `.gitignore`, local endpoint exposure, and screenshots/logs for accidental personal data.
- Update README quick start, troubleshooting, screenshots if useful, and migration notes.
- Add offline regression tests for config validation, context filtering/limits, session metadata, URL resumption safety, and bounded comparison prompts.
- Keep full-page diagnostic screenshots opt-in because they can contain prompts and replies; document loopback CDP and browser-profile privacy.
- Replace the wildcard CDP WebSocket origin exception with the two exact loopback origins on the configured port in every launcher.
- Record Chrome live checks: Gemini launch, CDP, settled-page doctor, model listing, and minimal prompt passed in the bridge's isolated profile; ChatGPT and Claude pages loaded but were not signed in, and the user's everyday Chrome profile and Edge end-to-end remain unverified.
- Scope saved conversation URLs to browser/profile settings so one browser profile cannot resume another profile's chat URL.

**Completion criteria**

- Supported combinations have a documented verification record.
- Failures are actionable, and diagnostic output avoids cookies, tokens, and unnecessary page contents.
- Existing Gemini users have a short migration path and their current command continues to work during the transition.
- Offline checks pass and README records the verified Gemini/Chrome isolated-profile subset plus the remaining provider/browser/profile gaps without overstating coverage.

## Suggested delivery order

1. Phase 0: correct the README and define supported scope.
2. Phase 1: isolate Gemini behind the provider contract.
3. Phase 2: make browser connection configurable and add diagnostics.
4. Phase 3: add and verify provider adapters/model selection incrementally.
5. Phase 4: implement context handoff and update the canonical skill.
6. Phase 5: add multi-provider runs after single-provider isolation is reliable.
7. Phase 6: finish CLI adapters and browser-only guidance.
8. Phase 7: validate each supported combination and prepare release notes.

## Token-efficiency requirements for the skills

When a bridge skill activates, it must:

- Keep the CLI in an orchestration role: gather only relevant context, invoke the browser AI for delegated work, and apply the returned answer without re-deriving it in a long CLI discussion.
- Avoid sending the whole CLI transcript, repository, or unchanged files. Send a compact task summary, relevant excerpts, and only new changes/errors since the previous request.
- Ask for compact, actionable output by default. Prefer a unified diff or exact file edits for code tasks, and concise answers for questions. Request explanation only to the level the user needs.
- Avoid automatic follow-up calls for every sub-step. Re-query only when necessary to resolve a gap, diagnose an error, or honor a user request.
- Avoid reading large browser-AI outputs back into the CLI when a focused diff or short result is sufficient.
- Treat multi-provider mode as explicit opt-in and disclose that it sends context to each selected provider.
- Provide an optional usage benchmark comparing a representative CLI-only task with the bridge workflow, using token metrics exposed by the CLI. Report measurements as environment-specific, not guaranteed savings.

**Acceptance criteria:** Skill instructions make token-saving behavior the default; prompts omit irrelevant context; browser-AI replies are usable without verbose repackaging; and a benchmark can report CLI token use and turn count when available.

## Explicitly out of scope for the first release

- A browser extension that injects skills or reads local repository files.
- Automatic access to another provider’s conversation history.
- Guaranteeing every account can select every model shown in vendor announcements.
- Supporting every browser/provider combination without verification.
- Sending prompts to all configured providers without an explicit user/CLI request.
