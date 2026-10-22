---
name: ask-argon-web
description: |
  Compatibility trigger for the use-argon-web workflow. Activate when the user
  says "ask argon" or asks to delegate work to browser-based AI through Argon.
license: Apache-2.0
metadata:
  version: v5
  author: Mohit20057
  repo: https://github.com/Mohit20057/AI-web-bridge
---

# Ask Argon Web

Use the canonical [`use-argon-web`](../use-argon-web/SKILL.md) skill when it is
available. Otherwise follow this short path:

1. Build a compact request with only task-relevant excerpts; never send the
   transcript, repository, or unchanged files.
2. Run `python bridge/argon_bridge.py --context-file _argon_context.json --out _argon_response.md`
   for a version 1 context packet, or use `--prompt-file` for a simple question.
3. Use one provider by default. Only use `--providers` or `--all` when the user
   asks for multiple opinions; the same context goes to each site.
4. Apply the concise result and follow up only if it is incomplete, an error
   needs diagnosis, or the user requests another pass.

The bridge and website cannot share chat history automatically. See the
repository [SKILL_SPEC.md](../../SKILL_SPEC.md) for setup and browser-only use.
