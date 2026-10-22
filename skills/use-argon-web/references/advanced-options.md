# Advanced bridge options

Read only the section needed for the current request.

## Browser and profile

- Choose Chrome or Edge with `--browser chrome|edge`.
- Use `--list-browser-profiles` to see profile display names and directory IDs.
- Select an ID with `--profile-directory ID`; use `--profile-dir ROOT` for a
  nonstandard browser data folder.
- The bridge prints the selected browser and profile before connecting. An
  everyday profile may need its browser closed first so the bridge can launch
  it with debugging enabled; the bridge never closes an already-open browser.

## Readiness and review

- `--doctor` checks whether the provider is ready and lists model choices visible
  to the signed-in account. It sends no prompt.
- `--review-context` prints the exact assembled request locally and exits
  without contacting a provider. Use it when the user requests review or the
  selected content needs careful inspection. Avoid loading the entire preview
  back into the coding model unless needed.
- A requested model must be visible in that account's model picker. Provider
  plans and model availability vary.

## Local data cleanup

- `--forget-chats`, `--forget-runs`, `--forget-handoff`, and `--forget-usage`
  remove only the selected project's saved data of that type.
- `--forget-local-data` removes all four types for the current project.
- Interactive runs ask for confirmation. Add `--yes` for intentional
  non-interactive cleanup.
- `--no-handoff` disables loading and saving compact notes for one request.

## Token comparison

When the coding CLI exposes usage counts, record baseline and bridge-workflow
input/output counts for comparable tasks. Use a category label, not prompt text:

```sh
python bridge/argon_bridge.py --record-usage-sample --usage-task "bug-fix" \
  --baseline-input-tokens 12000 --baseline-output-tokens 800 \
  --bridge-input-tokens 2500 --bridge-output-tokens 500
python bridge/argon_bridge.py --usage-report
```

The local report contains the task category and token counts only. It compares
counts reported by the user; it cannot retrieve metrics from every coding CLI
or guarantee savings.
