# AI Web Bridge Browser Extension (Zero-Click Auto Mode)

This Manifest V3 extension allows any AI coding CLI (Antigravity, Cursor, Aider, Claude Code) to seamlessly automate web AI chats (Gemini, ChatGPT, Claude, Grok, Blackbox, etc.) using your existing, logged-in browser session with **zero manual clicking**.

---

## Key Features

- **⚡ Zero-Click Automatic Execution**: When your CLI sends a request, the extension automatically finds or opens the matching provider tab, types the prompt, and sends the answer back to your CLI. You never have to click "Run" in a popup.
- **🌐 Universal Multi-Model Support**: Works out of the box with:
  - **Gemini** (`gemini.google.com`)
  - **ChatGPT** (`chatgpt.com` / `chat.openai.com`)
  - **Claude** (`claude.ai`)
  - **Grok** (`grok.com` / `x.com`)
  - **Blackbox AI** (`blackbox.ai`)
  - Any other custom web AI via universal selector fallbacks.
- **🛡️ 100% Anti-Bot & Cloudflare Bypass**: Because it runs as a standard browser extension inside your normal everyday browser, `navigator.webdriver` is `false`. Cloudflare, Google, and OpenAI treat your requests as ordinary human browsing.
- **🔄 Multi-Tab & Multi-Provider**: Seamlessly routes tasks across multiple tabs (e.g. `--providers gemini,chatgpt,claude`) without opening new profiles or losing your logins.

---

## One-Time Setup

1. **Load the Extension into Chrome/Edge**:
   - Open `chrome://extensions` or `edge://extensions`.
   - Turn on **Developer mode** (top-right toggle).
   - Click **Load unpacked** and select the `browser-extension` folder.
   - Note the 32-character **Extension ID** displayed on the extension card.

2. **Register the Local Native Helper**:
   In your terminal, run:
   ```sh
   python bridge/argon_bridge.py --extension-setup --extension-id YOUR_EXTENSION_ID
   ```
   *(This registers the local native messaging host in your user registry so Chrome can communicate with the local CLI bridge).*

---

## How to Use

Simply run your CLI commands with `--browser-mode extension`:

### 1. Single Provider Query (e.g. Gemini)
```sh
python bridge/argon_bridge.py --browser-mode extension --provider gemini --prompt "Explain event loops in Node.js"
```
The extension will automatically:
1. Detect the pending CLI request.
2. Find your open Gemini tab (or open one if not already open).
3. Type the prompt, click send, wait for generation, and output the response.

### 2. Querying Other Providers (ChatGPT, Claude, Grok, Blackbox)
```sh
# Ask ChatGPT
python bridge/argon_bridge.py --browser-mode extension --provider chatgpt --prompt "Write a Python binary search"

# Ask Claude
python bridge/argon_bridge.py --browser-mode extension --provider claude --prompt "Refactor this architecture"

# Ask Grok
python bridge/argon_bridge.py --browser-mode extension --provider grok --prompt "What is quantum computing?"

# Ask Blackbox
python bridge/argon_bridge.py --browser-mode extension --provider blackbox --prompt "Generate a Tailwind navbar"
```

### 3. Multi-Provider Runs
Run across multiple models in a single command:
```sh
python bridge/argon_bridge.py --browser-mode extension --providers gemini,chatgpt,claude --prompt "Review this code"
```

---

## Settings & Popup Controls

Click the extension icon in your browser toolbar to:
- **Toggle Auto-Run**: Enable or disable zero-click background mode.
- **Check Status**: See real-time connection status with the CLI bridge.
- **Change Port**: Customize the loopback port (default: `8765`).
