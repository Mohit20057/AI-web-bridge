# Portable context packet

The bridge does not read CLI history, another provider's chat, or the repository
automatically. A skill or user prepares this packet with only the context needed
for the current request.

## Version 1 format

```json
{
  "version": 1,
  "task": "Implement the cache invalidation fix.",
  "project_summary": "Small Python service; cache keys are in bridge/cache.py.",
  "recent_changes": "The parser now normalizes keys before lookup.",
  "files": [
    {"path": "bridge/cache.py", "content": "selected relevant excerpt or focused diff"}
  ],
  "errors": ["Lookup returns stale values after a key rename."],
  "constraints": ["Keep the public function signature unchanged."],
  "requested_output": "Return a minimal unified diff and one-sentence rationale."
}
```

Required fields are `version` (integer `1`) and non-empty `task`. Optional text
fields are `project_summary`, `recent_changes`, and `requested_output`.
`errors` and `constraints` are arrays of strings. `files` is an array of objects
with string `path` and `content` fields. Unknown fields are rejected so typos do
not silently lose context.

Use `--context-file packet.json` to submit a packet. The default maximum is
24,000 characters; set `--context-limit-chars N` to change it. Fixed task and
summary sections are preserved; file excerpts are truncated or omitted with a
warning when needed. If fixed sections alone exceed the limit, shorten them.
When adding `--prompt` or `--prompt-file`, its text is appended as an
“Additional request” and included in the same size cap. `--review-context`
prints the exact assembled payload locally and exits before browser connection.

The bridge excludes common sensitive-looking paths by name, including `.env*`
except `.env.example`, private-key extensions, and paths named for credentials
or secrets. This is only a path filter: it does not detect secrets embedded in
ordinary file contents. Select and review excerpts before sending them to a web
provider.

`--record-run` is off by default. When enabled, `.ai-web-bridge/runs.jsonl`
stores timestamps, project identifier, provider and selected model labels,
query-stripped chat URL, and local input/output references. It does not store
prompt text, packet contents, or response text. The directory is gitignored.
In multi-provider mode, each successful provider submission produces its own
metadata record; an optional comparison submission is recorded separately.

When a context packet is submitted, the bridge saves only its task, project
summary, and recent-changes notes in a project-local handoff. A later packet
can carry forward a missing summary or recent-changes note, including when
switching providers. It never saves file excerpts from the packet in the
handoff. Use `--no-handoff` to disable loading and saving for one request, or
`--forget-handoff` to remove the saved notes. `--forget-chats`, `--forget-runs`,
and `--forget-usage` remove those project-local records; `--forget-local-data`
removes all four categories. Interactive removal asks for confirmation; use
`--yes` for an intentional non-interactive cleanup.

## Optional token comparison

If your coding assistant reports token counts, you can record comparable
before-and-after counts with `--record-usage-sample`, a short task category, and
the baseline/bridge input and output totals. `--usage-report` groups those
samples by category and reports the measured difference. The bridge does not
estimate or retrieve token counts from the coding assistant, and usage records
do not include prompts or responses.
