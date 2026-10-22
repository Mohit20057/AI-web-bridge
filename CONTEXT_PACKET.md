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

This packet is a handoff for one request, not automatically maintained project
memory. Update durable project notes only when the user asks for that.
