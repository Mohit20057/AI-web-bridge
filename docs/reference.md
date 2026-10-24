# AI Web Bridge CLI & Architecture Reference

## Overview
AI Web Bridge turns your signed-in browser sessions into an automated CLI orchestrator.
No API keys, no cookies, loopback only (127.0.0.1).

## Lifecycle Commands
- `bridge init [--goal "..."]`: Scans existing repo, creates `.bridge/` directory, initializes `ledger.jsonl` and rolling `HANDOFF.md`.
- `bridge sync`: Compares working tree / git state with checkpoint, detects outside manual edits, logs them with diff stat. Runs automatically on every bridge command.
- `bridge status`: Prints `HANDOFF.md` "Current state" and "Next step" (max 15 lines).
- `bridge handoff --to {provider} [--goal "..."]`: Assembles envelope with `HANDOFF.md`, repo map, and last diff, executes the `analyst` role, appends results to ledger, and prints a single summary line.

## Multi-Stage Pipelines (`--pipeline x.yaml`)
Run multi-stage relays from a single command:
```yaml
stages:
  - provider: claude
    template: architect
    out: spec.md
    task: "Design the PulseTask application contract"

  - provider: chatgpt
    template: engine
    in: spec.md
    out: engine.js
    verify: "node --check engine.js"

  - provider: gemini
    template: ui
    in: [spec.md, engine.js]
    out: index.html
    verify: "node -e \"require('fs').readFileSync('index.html')\""
```
Intermediate files pass stage-to-stage on disk. The agent sees only one line per stage:
`OK job=ab12 stage=2/3 out=engine.js lines=668 status=COMPLETE verify=PASS`

## Verification & Fixer Loop
When `verify: "<command>"` fails:
1. Captures trimmed stderr (last 15 lines).
2. Dispatches fixer prompt to the same chat thread:
   `Check failed: {command}\nError:\n{stderr}\nReturn the corrected function(s) as a unified diff; if the patch will not apply, return the COMPLETE file.`
3. Applies unified diff patch or overwrites complete file fallback.
4. Reruns check up to `--max-retries` (default: 2).

## Council Mode
- **Round 1 (Independent)**: Models evaluate the same task in isolation under schema: `Recommendation`, `Reasoning`, `Risks`, `Confidence` (max 150 words).
- **Round 2 (Synthesis)**: Synthesizer receives anonymized candidates (`Candidate A/B/C`). Outputs: `Decision`, `Rejected options + why`, `Risks`, `What would change this decision`.

## CLI Flags Reference
- `--template`: Role template from `prompts/*.txt` (architect, engine, ui, reviewer, analyst, fixer, synthesizer).
- `--role`: Role identifier in prompt envelope.
- `--task-file`: File path containing task description.
- `--context-files`: Full file paths to include in envelope context.
- `--contract`: Path to binding contract file.
- `--in`: Input file(s) from previous stage.
- `--verify`: Shell command to validate generated code.
- `--max-retries`: Maximum fixer retries (default 2).
- `--cache`: Cache responses by hash of prompt + context.
- `--quiet`: Suppress verbose browser output; print one-line summary.
- `--print-output`: Preview extracted output on stdout.
- `--max-output-lines`: Truncation cap for stdout preview (default 20).
- `--to`: Target provider for handoff command.
- `--goal`: High-level goal string for init/handoff.
