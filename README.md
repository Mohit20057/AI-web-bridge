<div align="center">

![AI Web Bridge Banner](assets/banner.jpg)

# 🌐 AI Web Bridge
### Multi-AI Browser Orchestrator & Local CLI Bridge
**Use Gemini Argon, Claude 3.5 Sonnet, ChatGPT, Grok, and Blackbox directly from your terminal or AI coding agent — 100% Free, Zero API Keys, Hands-Free.**

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Browser: Chrome & Edge](https://img.shields.io/badge/browser-Chrome%20%7C%20Edge-brightgreen.svg)]()
[![API Keys: None](https://img.shields.io/badge/API%20Keys-Zero%20Required-success.svg)]()
[![Tested: Multi--AI%20Relay](https://img.shields.io/badge/Multi--AI-Gemini%20%7C%20Claude%20%7C%20ChatGPT-orange.svg)]()

</div>

---

## 💡 What is AI Web Bridge?

**AI Web Bridge** turns your signed-in browser tabs into high-performance, cost-free AI copilots for your coding terminal or AI agent (**Antigravity**, **Cursor**, **Claude Code**, **Aider**, etc.).

Instead of paying expensive API token rates or hitting restrictive rate limits, AI Web Bridge sends prompts directly to your active web sessions in Chrome or Edge, monitors the generation stream in real-time, extracts the completed code or text, and saves it cleanly to disk.

---

## 🏛️ System Architecture & Workflow

![AI Web Bridge Workflow](assets/workflow.jpg)

The system operates across three tightly integrated layers:
1. **Developer CLI / Agent:** Dispatches high-level prompts, task contexts, or multi-AI relay pipelines.
2. **Local Broker & Native Messaging Host:** Authenticates requests via local loopback sockets and routes tasks securely to the Chrome extension.
3. **Zero-Click Browser Extension:** Runs in your browser, claims pending jobs, switches to the correct provider tab, inputs the prompt, detects streaming completion across modern DOM layouts, and extracts formatted output without user intervention.

---

## ⚡ 60-Second Quick Start

### 1. Install Dependencies
```bash
git clone https://github.com/Mohit20057/AI-web-bridge.git
cd AI-web-bridge
pip install -r requirements.txt
```

### 2. Register the Local Extension Host
Run the automated setup to link your browser with the local broker:
```bash
python bridge/argon_bridge.py --extension-setup
```

### 3. Load the Browser Extension
1. Open Chrome or Edge and navigate to `chrome://extensions`.
2. Enable **Developer mode** (top-right toggle).
3. Click **Load unpacked** and select the [`browser-extension/`](browser-extension/) directory from this repository.
4. If your extension ID differs from the default, re-run:
   ```bash
   python bridge/argon_bridge.py --extension-setup --extension-id YOUR_EXTENSION_ID
   ```

### 4. Run Your First Query!
Make sure your favorite AI provider is open and signed in on a browser tab, then run:
```bash
# Query Google Gemini (Argon)
python bridge/argon_bridge.py --browser-mode extension --provider gemini --prompt "Write a Python fibonacci generator"

# Query OpenAI ChatGPT
python bridge/argon_bridge.py --browser-mode extension --provider chatgpt --prompt "Explain event loops in Node.js"

# Query Anthropic Claude
python bridge/argon_bridge.py --browser-mode extension --provider claude --prompt "Design a clean REST API schema"
```

---

## 🤖 Supported AI Providers & Models

| Provider | ID | Default Web URL | Key Supported Models |
| :--- | :--- | :--- | :--- |
| **Google Gemini** | `gemini` | `https://gemini.google.com/app` | **Argon**, 3.1 Pro, 3.8 Flash, 3.5 Flash-Lite |
| **Anthropic Claude** | `claude` | `https://claude.ai/new` | **Claude 3.5 Sonnet**, Haiku, Opus |
| **OpenAI ChatGPT** | `chatgpt` | `https://chatgpt.com/` | **GPT-4o**, o1-preview, Canvas |
| **xAI Grok** | `grok` | `https://grok.com/` or `x.com/i/grok` | Grok 2, Fun mode |
| **Blackbox AI** | `blackbox` | `https://www.blackbox.ai/` | Blackbox Chat |

To inspect model choices visible on your signed-in tab:
```bash
python bridge/argon_bridge.py --browser-mode extension --provider gemini --list-models
```

---

## 🤝 Multi-AI Collaboration Workflows

AI Web Bridge acts as a **central conductor** enabling different AI models to collaborate sequentially or in consensus on complex tasks:

### 1. Sequential Relay (Specialist Pipeline)
Different models excel at different things. Let each model do what it does best:

```bash
# Step 1: Claude architects the system blueprint
python bridge/argon_bridge.py --browser-mode extension --provider claude \
  --prompt-file _arch_prompt.txt --out _arch_spec.md

# Step 2: ChatGPT builds the core business logic engine
python bridge/argon_bridge.py --browser-mode extension --provider chatgpt \
  --prompt-file _backend_prompt.txt --out _kanban_engine.js

# Step 3: Gemini Argon builds the responsive frontend UI
python bridge/argon_bridge.py --browser-mode extension --provider gemini --model "Argon" \
  --prompt-file _ui_prompt.txt --out _index.html
```

### 2. "All on One" Council Mode (Consensus & Synthesis)
When evaluating an ambiguous architectural decision or critical security bug, query all models at once and let one model synthesize the consensus:

```bash
python bridge/argon_bridge.py --browser-mode extension \
  --providers gemini,chatgpt,claude \
  --compare-provider gemini \
  --prompt "Should we use WebSockets or Server-Sent Events for our live collaborative dashboard?" \
  --out comparison_result.md
```
- Queries each open AI tab in sequence.
- Passes all candidate arguments to the evaluator (`gemini`).
- Writes a clear consensus summary with pros/cons and final recommendation.

### 3. Instant Recovery (`--read-latest`)
If you already had a conversation or answer visible on screen in your browser tab, grab it immediately into a file in 1 second without re-prompting:
```bash
python bridge/argon_bridge.py --browser-mode extension --provider chatgpt --read-latest --out response.md
```

---

## 🏆 Real-World Case Study: "PulseTask" App

AI Web Bridge was battle-tested by orchestrating a complete offline-first Kanban board application built **live and end-to-end** across three competing AI models in sequence:

- **Architecture Spec:** Designed by **Anthropic Claude 3.5 Sonnet** (Normalized schemas, actions, store contracts, and UI guidelines).
- **Logic Engine:** Coded by **OpenAI ChatGPT** (Pure JavaScript state engine — 668 lines, 0 syntax errors).
- **Frontend UI:** Built by **Google Gemini Argon** (Responsive layout with Tailwind CSS and HTML5 Drag-and-Drop — 1,696 lines).

---

## 🧠 Using with Google Antigravity (Skill Integration)

To let your Antigravity agent consult your browser AIs hands-free, the skill is installed directly into Antigravity:

```bash
# Installed skill path
~/.gemini/config/skills/use-argon-web/SKILL.md
```

### Natural Language Prompts:
Just talk to Antigravity as you normally would:
- *"Use Argon web to brainstorm database migrations for this model."*
- *"Ask Claude to review this security architecture."*
- *"Run this problem through ChatGPT and test the resulting script."*
- *"Ask the council (Gemini, Claude, ChatGPT) to compare approaches."*

Antigravity will automatically invoke the bridge, dispatch the task to the right browser tab, and apply the returned code to your project workspace.

---

## 🔒 Security & Privacy Guarantees

- **No Passwords or Cookies Exported:** The bridge never touches, extracts, or exports your session cookies, authentication tokens, or account credentials.
- **Local Loopback Only:** All communication between your terminal and the browser extension occurs strictly over local loopback (`127.0.0.1`), authenticated by random secrets.
- **Clean Whitespace & Code Preservation:** Strips out "Copy code", thumbs up/down, and action buttons from web pages so your saved code is never corrupted.

---

## 📄 License

This project is licensed under the [Apache 2.0 License](LICENSE).
Copyright (c) 2026 Mohit20057.
