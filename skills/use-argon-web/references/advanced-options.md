# Advanced bridge options

Read only the section needed for the current request.

## Browser and profile

- The skill asks which browser to use only once per chat if the user has not
  already chosen one. It reuses that choice for later requests in the chat.
- Choose Chrome or Edge with `--browser chrome|edge`.
- Use `--list-browser-profiles` to see profile display names and directory IDs.
- Select an ID with `--profile-directory ID`; use `--profile-dir ROOT` for a
  nonstandard browser data folder.
- The bridge prints the selected browser and profile before connecting. An
  everyday profile in managed mode may need its browser closed first so the
  bridge can launch it with debugging enabled; the bridge never closes an
  already-open browser.
- To use the AI tab already signed in to Chrome or Edge without enabling
  Remote Debugging, install the optional extension from `browser-extension/`.
  In Chrome or Edge, open the extensions page, enable Developer mode, and load
  that folder as an unpacked extension. Copy its ID and register the native
  helper once by running:

  ```sh
  python "$BRIDGE_SCRIPT" --extension-setup --extension-id YOUR_EXTENSION_ID
  ```

  On Windows this registers the helper for the current user without admin
  access. If Chrome and Edge show different extension IDs, repeat
  `--extension-id` for each. Then run a request with `--browser-mode extension`.
  When the CLI waits, open the signed-in provider tab, click the AI Web Bridge
  extension, and choose **Run waiting request in this tab**. The extension only
  acts on that tab after the click. It requests no Chrome debugger or cookie
  access.

  ```sh
  python "$BRIDGE_SCRIPT" --browser chrome --browser-mode extension --provider gemini --prompt "Summarize the selected task"
  ```

  The extension uses `127.0.0.1:8765` by default. If the port is occupied,
  choose a different one with `--extension-port PORT` during setup and for each
  query, then save that port in the extension popup. Rotate the local secret by
  rerunning setup with `--extension-rotate` and the registered extension ID.
- The safer default is the bridge-managed profile. To attach to an existing,
  signed-in Chrome session, use Chrome 144 or newer and install Node.js LTS/npm.
  In Chrome, open `chrome://inspect/#remote-debugging` and enable Remote
  Debugging. Then pass `--browser chrome --browser-mode existing` on the bridge
  command. Chrome will ask you to approve access; review the dialog and click
  Allow. This mode is currently Chrome-only. While connected, the bridge can
  access the active Chrome session and its signed-in sites. The bridge disables
  Chrome DevTools MCP usage statistics and performance URL reporting.

  ```sh
  python "$BRIDGE_SCRIPT" --browser chrome --browser-mode existing --doctor
  python "$BRIDGE_SCRIPT" --browser chrome --browser-mode existing --context-file _argon_context.json --out _argon_response.md
  ```

  To keep using an isolated bridge profile, use the default `managed` mode.

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
