(() => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const isVisible = (node) => {
    if (!node) return false;
    try {
      const rects = node.getClientRects();
      if (!rects || rects.length === 0) return false;
      const style = window.getComputedStyle(node);
      return style && style.visibility !== "hidden" && style.display !== "none";
    } catch {
      return false;
    }
  };

  const UNIVERSAL_INPUTS = [
    "#prompt-textarea",
    "rich-textarea div[contenteditable='true']",
    "div.ProseMirror[contenteditable='true']",
    "div[contenteditable='true'][role='textbox']",
    "div[contenteditable='true'][data-placeholder]",
    "textarea#chat-input",
    "textarea[placeholder*='Ask' i]",
    "textarea[placeholder*='prompt' i]",
    "textarea[placeholder*='message' i]",
    "div[contenteditable='true']",
    "textarea"
  ].join(", ");

  const UNIVERSAL_SENDS = [
    "button[data-testid='send-button']",
    "button[aria-label*='Send prompt' i]",
    "button[aria-label*='Send message' i]",
    "button[aria-label*='Send' i]",
    "button[aria-label*='Submit' i]",
    "button[aria-label*='Ask' i]",
    "button.send-button",
    "button[type='submit']"
  ].join(", ");

  const UNIVERSAL_STOPS = [
    "button[data-testid='stop-button']",
    "button[aria-label*='Stop generating' i]",
    "button[aria-label*='Stop streaming' i]",
    "button[aria-label*='Stop response' i]",
    "button[aria-label*='Stop' i]",
    "button[aria-label*='Cancel' i]"
  ].join(", ");

  function selectAll(selectorText) {
    if (!selectorText) return [];
    try {
      return [...document.querySelectorAll(selectorText)];
    } catch {
      const found = [];
      for (const selector of String(selectorText).split(",")) {
        const s = selector.trim();
        if (!s) continue;
        try { found.push(...document.querySelectorAll(s)); } catch (_e) {}
      }
      return [...new Set(found)];
    }
  }

  function firstVisible(selectorText) {
    return selectAll(selectorText).find(isVisible) || null;
  }

  function visibleText(node) {
    return String(node?.innerText || node?.textContent || "").trim();
  }

  function findAssistantMessages(selectors) {
    // 1. Explicit provider container selector if given
    if (selectors?.response_container) {
      const explicit = selectAll(selectors.response_container).filter(isVisible);
      if (explicit.length) return explicit;
    }

    // 2. Universal provider assistant tags (Gemini model-response, Claude font-claude-message, etc.)
    const assistantSpecific = selectAll([
      "model-response",
      ".model-response-text",
      "[data-message-author-role='assistant']",
      "div.agent-turn",
      ".font-claude-message",
      "div.chat-message-ai",
      "div[data-testid='grok-response']"
    ].join(", ")).filter(isVisible);
    if (assistantSpecific.length) return assistantSpecific;

    // 3. Modern ChatGPT: elements inside data-talvt-turn-state, data-turn-key
    const chatGptTurns = selectAll("[data-talvt-turn-state], [data-turn-key]");
    if (chatGptTurns.length) {
      const assistantBlocks = [];
      for (const turn of chatGptTurns) {
        if (!isVisible(turn)) continue;
        const asstBlock = turn.querySelector("[data-content-search-unit-key*='assistant'], [data-chatgpt-search-unit-key*='assistant']");
        if (asstBlock && isVisible(asstBlock)) {
          assistantBlocks.push(asstBlock);
        }
      }
      if (assistantBlocks.length) return assistantBlocks;
    }

    // 4. Conversation turn articles (ChatGPT older, modern chat UIs)
    const turns = selectAll("article[data-testid*='conversation-turn'], article, [data-testid*='message-container']").filter(isVisible);
    if (turns.length) {
      const assistantTurns = turns.filter((turn) => {
        // Exclude user messages
        if (turn.querySelector("[data-message-author-role='user']")) return false;
        if (turn.querySelector("button[data-testid*='edit'], button[aria-label*='Edit' i]")) return false;

        // Positive assistant indicators
        if (turn.querySelector("[data-message-author-role='assistant']")) return true;
        if (turn.querySelector("button[data-testid*='copy'], button[aria-label*='Copy' i]")) return true;
        if (turn.querySelector(".markdown, .prose")) return true;
        return true;
      });
      if (assistantTurns.length) return assistantTurns;
    }

    // 5. Fallback to markdown/prose blocks
    const markdowns = selectAll(".markdown, .prose, .response-content, [data-testid='message-content']").filter(isVisible);
    if (markdowns.length) return markdowns;

    return [];
  }

  function extractAssistantText(node) {
    if (!node) return "";
    const inner = node.querySelector(".markdown, .prose, .model-response-text, message-content, [data-testid='message-content']") || node;
    let text = "";
    try {
      const clone = inner.cloneNode(true);
      const codeBlocks = [];

      // 1. Gemini code-block custom element
      for (const cb of clone.querySelectorAll("code-block, .code-block")) {
        const langSpan = cb.querySelector(".code-block-decoration span");
        const lang = (langSpan?.textContent || "").trim();
        const codeEl = cb.querySelector("code[data-test-id='code-content'], pre code, pre") || cb;
        const codeText = codeEl.textContent || "";
        const placeholder = `__AI_BRIDGE_CODE_BLOCK_${codeBlocks.length}__`;
        codeBlocks.push("\n```" + (lang || "").toLowerCase() + "\n" + codeText.trimEnd() + "\n```\n");
        cb.replaceWith(document.createTextNode(placeholder));
      }

      // 2. Modern ChatGPT / CodeMirror code blocks
      const codeContainers = clone.querySelectorAll("[data-code-block='true'], .CodeBlock-zu1QM3, .cm-editor");
      for (const cb of codeContainers) {
        const cmContent = cb.querySelector(".cm-content");
        const lang = cmContent?.getAttribute("data-language") ||
                     cb.querySelector(".ActionBar-KWWAct .truncate, .sticky .truncate")?.textContent?.trim() || "";
        let codeText = "";
        if (cmContent) {
          const lines = [...cmContent.querySelectorAll(".cm-line")].map(line => {
            if (line.querySelector("br") && line.textContent.trim() === "") return "";
            return line.textContent || "";
          });
          codeText = lines.join("\n");
        } else {
          codeText = cb.textContent || "";
        }
        const placeholder = `__AI_BRIDGE_CODE_BLOCK_${codeBlocks.length}__`;
        codeBlocks.push("\n```" + (lang || "").toLowerCase() + "\n" + codeText.trimEnd() + "\n```\n");
        cb.replaceWith(document.createTextNode(placeholder));
      }

      // 3. Convert standard <pre> blocks into markdown blocks
      for (const pre of clone.querySelectorAll("pre")) {
        const codeEl = pre.querySelector("code") || pre;
        let lang = "";
        const m = (codeEl.className || "").match(/language-([a-zA-Z0-9_-]+)/);
        if (m) lang = m[1];
        const codeText = codeEl.textContent || "";
        const placeholder = `__AI_BRIDGE_CODE_BLOCK_${codeBlocks.length}__`;
        codeBlocks.push("\n```" + lang + "\n" + codeText.trimEnd() + "\n```\n");
        pre.replaceWith(document.createTextNode(placeholder));
      }

      // 3. Remove buttons, controls, action bars, svgs
      for (const el of clone.querySelectorAll("button, [role='button'], .copy-button, [aria-label*='Copy' i], [data-testid*='copy' i], .turn-action-controls, svg, .ActionBar-KWWAct")) {
        el.remove();
      }

      // 4. Attach clone temporarily offscreen to document.body with pre-wrap layout
      clone.style.cssText = "position: absolute !important; left: -99999px !important; top: 0 !important; width: 800px !important; opacity: 0 !important; pointer-events: none !important; white-space: pre-wrap !important;";
      for (const el of clone.querySelectorAll("p, div, span, blockquote")) {
        el.style.whiteSpace = "pre-wrap";
      }
      document.body.appendChild(clone);
      text = clone.innerText || clone.textContent || "";
      clone.remove();

      // 5. Restore pristine code blocks untouched by layout
      text = text.replace(/__AI_BRIDGE_CODE_BLOCK_(\d+)__/g, (_match, idx) => {
        return codeBlocks[Number(idx)] || "";
      });
    } catch {
      text = visibleText(inner);
    }
    // Clean assistant narration prefix if present
    text = text.replace(/^ChatGPT said:\s*/i, "").trim();
    return text;
  }

  function isGenerating(selectors) {
    const stopBtn = firstVisible(selectors?.stop_btn || UNIVERSAL_STOPS);
    if (stopBtn) return true;

    const streamingNode = document.querySelector(".result-streaming, [class*='result-streaming'], [data-is-streaming='true']");
    if (streamingNode && isVisible(streamingNode)) return true;

    return false;
  }

  function modelOptions(selectors) {
    const selector = selectors?.menu_item || "[role='menuitem'], [role='option'], [role='menuitemradio']";
    return selectAll(selector).filter(isVisible).map(visibleText).filter(Boolean);
  }

  async function listModels(selectors) {
    const button = firstVisible(selectors?.model_btn) || [...document.querySelectorAll("button")].find((item) => isVisible(item) && /model|mode|flash|sonnet|opus|gpt|pro/i.test(visibleText(item)));
    if (!button) return [];
    button.click();
    await wait(400);
    const models = modelOptions(selectors);
    const backdrop = document.querySelector(".cdk-overlay-backdrop, [class*='backdrop']");
    if (backdrop) backdrop.click();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    await wait(300);
    return models;
  }

  const DEFAULT_FALLBACK_CHAINS = {
    gemini: ["argon", "3.1 pro", "3.8 flash", "3.5 flash-lite", "pro", "flash"],
    chatgpt: ["o1", "gpt-4o", "gpt-4o mini", "4o", "mini"],
    claude: ["claude 3.5 sonnet", "claude 3 opus", "claude 3.5 haiku", "sonnet", "opus", "haiku"],
    grok: ["grok 2", "grok 2 mini", "grok"],
    blackbox: ["blackbox", "deepseek", "gpt-4o", "claude"]
  };

  async function chooseModel(selectors, requested, providerId) {
    if (!requested) return { model: "", fallback_from: null, fallback_notice: null };
    let button = firstVisible(selectors?.model_btn);
    if (!button) {
      button = [...document.querySelectorAll("button")].find((item) => isVisible(item) && /model|mode|flash|sonnet|opus|gpt|pro/i.test(visibleText(item)));
    }
    if (!button) return { model: "", fallback_from: null, fallback_notice: null };
    button.click();
    await wait(400);
    const candidates = selectAll(selectors?.menu_item || "[role='menuitem'], [role='option'], [role='menuitemradio']")
      .filter(isVisible)
      .map((node) => ({ node, label: visibleText(node) }))
      .filter((item) => item.label);
    const key = requested.toLocaleLowerCase().trim();
    const exact = candidates.filter((item) => item.label.toLocaleLowerCase() === key);
    let matches = exact.length ? exact : candidates.filter((item) => item.label.toLocaleLowerCase().includes(key));
    if (matches.length >= 1) {
      matches[0].node.click();
      await wait(500);
      return { model: matches[0].label, fallback_from: null, fallback_notice: null };
    }

    // Try fallback chain
    const chain = DEFAULT_FALLBACK_CHAINS[(providerId || "").toLowerCase()] || [];
    let fallbackMatch = null;
    for (const fbKey of chain) {
      if (fbKey.toLowerCase() === key) continue;
      const fbExact = candidates.filter((item) => item.label.toLocaleLowerCase() === fbKey);
      const fbMatches = fbExact.length ? fbExact : candidates.filter((item) => item.label.toLocaleLowerCase().includes(fbKey));
      if (fbMatches.length >= 1) {
        fallbackMatch = fbMatches[0];
        break;
      }
    }

    if (fallbackMatch) {
      fallbackMatch.node.click();
      await wait(500);
      const notice = `Requested model '${requested}' was not available in UI; switched to '${fallbackMatch.label}'.`;
      return { model: fallbackMatch.label, fallback_from: requested, fallback_notice: notice };
    }

    const backdrop = document.querySelector(".cdk-overlay-backdrop, [class*='backdrop']");
    if (backdrop) backdrop.click();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    await wait(300);
    const fallbackNotice = `Requested model '${requested}' was not available in UI; using current active model.`;
    return { model: "", fallback_from: requested, fallback_notice: fallbackNotice };
  }

  async function fillPrompt(input, prompt) {
    input.focus();
    if (input instanceof HTMLTextAreaElement || input instanceof HTMLInputElement) {
      const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(input), "value")?.set;
      if (setter) setter.call(input, prompt); else input.value = prompt;
      input.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: prompt }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
      return;
    }

    try {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(input);
      selection.removeAllRanges();
      selection.addRange(range);
    } catch (_e) {}

    // First: try document.execCommand insertText
    try {
      document.execCommand("insertText", false, prompt);
    } catch (_e) {}

    const snippet = prompt.slice(0, 15);
    let hasInserted = (input.innerText || input.textContent || "").includes(snippet);

    // Second: try ClipboardEvent paste (handles Claude ProseMirror)
    if (!hasInserted) {
      try {
        const dt = new DataTransfer();
        dt.setData("text/plain", prompt);
        input.dispatchEvent(new ClipboardEvent("paste", {
          bubbles: true,
          cancelable: true,
          clipboardData: dt
        }));
      } catch (_e) {}
      hasInserted = (input.innerText || input.textContent || "").includes(snippet);
    }

    // Third: direct paragraph or text replacement
    if (!hasInserted) {
      const p = input.querySelector("p");
      if (p) {
        p.textContent = prompt;
      } else {
        input.textContent = prompt;
      }
    }

    input.dispatchEvent(new InputEvent("beforeinput", { bubbles: true, composed: true, cancelable: true, inputType: "insertText", data: prompt }));
    input.dispatchEvent(new InputEvent("input", { bubbles: true, composed: true, inputType: "insertText", data: prompt }));
    input.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
    input.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
  }

  function clickElement(el) {
    if (!el) return;
    try {
      const opts = { bubbles: true, cancelable: true, composed: true, view: window };
      el.dispatchEvent(new PointerEvent("pointerdown", opts));
      el.dispatchEvent(new MouseEvent("mousedown", opts));
      el.dispatchEvent(new PointerEvent("pointerup", opts));
      el.dispatchEvent(new MouseEvent("mouseup", opts));
    } catch (_e) {}
    try { el.click(); } catch (_e) {}
  }

  async function submitPrompt(selectors, prompt) {
    // Ensure no stale backdrop or overlay is blocking pointer events
    const backdrops = document.querySelectorAll(".cdk-overlay-backdrop, [class*='backdrop']");
    for (const bd of backdrops) {
      try { bd.click(); } catch (_e) {}
      try { bd.remove(); } catch (_e) {}
    }
    await wait(200);

    let input = selectors?.input ? firstVisible(selectors.input) : null;
    if (!input) input = firstVisible(UNIVERSAL_INPUTS);
    if (!input) throw new Error("The AI chat box was not found on this tab. Ensure you are signed in.");

    await fillPrompt(input, prompt);
    await wait(400);

    let clicked = false;
    for (let i = 0; i < 25; i++) {
      let send = selectors?.send_btn ? firstVisible(selectors.send_btn) : null;
      if (!send) send = firstVisible(UNIVERSAL_SENDS);

      if (send && !send.disabled) {
        clickElement(send);
        clicked = true;
        break;
      }
      await wait(150);
    }

    if (!clicked) {
      input.dispatchEvent(new KeyboardEvent("keydown", {
        key: "Enter",
        code: "Enter",
        keyCode: 13,
        which: 13,
        bubbles: true,
        cancelable: true
      }));
    }
  }

  async function startNewChat(selectors) {
    if (!selectors?.new_chat) return;
    const button = firstVisible(selectors.new_chat);
    if (button) {
      button.click();
      await wait(800);
    }
  }

  async function waitForAnswer(selectors, initialText, initialCount, timeoutSeconds) {
    const deadline = Date.now() + Math.max(15, timeoutSeconds) * 1000;
    let started = false;
    let lastText = initialText;
    let stableSince = Date.now();
    let bestText = "";

    while (Date.now() < deadline) {
      const messages = findAssistantMessages(selectors);
      const isNewTurn = messages.length > initialCount;
      const latestNode = messages.length ? messages[messages.length - 1] : null;
      const currentText = extractAssistantText(latestNode);
      const generating = isGenerating(selectors);

      if (generating || isNewTurn || (currentText && currentText !== initialText)) {
        started = true;
      }

      if (isNewTurn) {
        if (currentText && currentText !== lastText) {
          lastText = currentText;
          bestText = currentText;
          stableSince = Date.now();
        } else if (currentText && (Date.now() - stableSince) >= 2000 && !generating) {
          return currentText;
        }
      } else {
        if (currentText && currentText !== lastText) {
          lastText = currentText;
          bestText = currentText;
          stableSince = Date.now();
        } else if (started && bestText && !generating) {
          if ((Date.now() - stableSince) >= 2000) {
            return bestText;
          }
        }
      }

      await wait(500);
    }

    const finalMessages = findAssistantMessages(selectors);
    if (bestText && (bestText !== initialText || finalMessages.length > initialCount)) {
      return bestText;
    }
    if (!started) throw new Error("The AI did not start a response before the timeout.");
    throw new Error("The AI did not finish generating before the timeout.");
  }

  async function run(job) {
    const selectors = job.selectors || {};

    if (job.action === "doctor") {
      let input = selectors.input ? firstVisible(selectors.input) : firstVisible(UNIVERSAL_INPUTS);
      if (!input) throw new Error("Provider page is open, but its chat input is not visible. Sign in and reload the page.");

      const articles = [...document.querySelectorAll("article")];
      const main = document.querySelector("main");
      const turns = [...document.querySelectorAll("[data-testid*='turn'], [data-testid*='conversation'], [data-testid*='message']")];
      const markdowns = [...document.querySelectorAll(".markdown, .prose")];
      const copyBtns = [...document.querySelectorAll("button[data-testid*='copy'], button[aria-label*='Copy' i]")];
      
      const messages = findAssistantMessages(selectors);
      const allMsgs = messages.map((m, idx) => {
        const text = extractAssistantText(m);
        return {
          idx,
          len: text.length,
          snippet: text.slice(0, 150)
        };
      });

      return {
        text: `Provider page diagnostic:\n${JSON.stringify(allMsgs, null, 2)}`,
        url: location.href,
        models: await listModels(selectors)
      };
    }

    if (job.action === "read_latest") {
      const messages = findAssistantMessages(selectors);
      if (!messages.length) throw new Error("No completed assistant message was found on this tab.");
      
      let chosen = "";
      if (job.match) {
        const regex = new RegExp(job.match, "i");
        for (let i = messages.length - 1; i >= 0; i--) {
          const t = extractAssistantText(messages[i]);
          if (regex.test(t)) {
            chosen = t;
            break;
          }
        }
      } else if (job.largest) {
        let maxLen = 0;
        for (const m of messages) {
          const t = extractAssistantText(m);
          if (t.length > maxLen) {
            maxLen = t.length;
            chosen = t;
          }
        }
      }
      
      if (!chosen) {
        let maxLen = 0;
        for (const m of messages) {
          const t = extractAssistantText(m);
          if (t.length > maxLen) {
            maxLen = t.length;
            chosen = t;
          }
        }
      }
      if (!chosen) {
        chosen = extractAssistantText(messages[messages.length - 1]);
      }

      if (!chosen) throw new Error("No completed assistant message was found on this tab.");
      return { text: chosen, url: location.href };
    }

    if (job.action === "list_models") {
      return { text: "Model list checked.", url: location.href, models: await listModels(selectors) };
    }

    if (job.action !== "query") throw new Error("Unsupported request type.");

    if (job.new_chat) await startNewChat(selectors);
    const modelChoice = await chooseModel(selectors, job.model, job.provider);

    // Initial assistant state before prompt
    const initialMessages = findAssistantMessages(selectors);
    const initialText = initialMessages.length ? extractAssistantText(initialMessages[initialMessages.length - 1]) : "";
    const initialCount = initialMessages.length;

    await submitPrompt(selectors, job.prompt || "");
    const text = await waitForAnswer(selectors, initialText, initialCount, job.timeout || 300);
    return {
      text,
      url: location.href,
      model: modelChoice.model,
      fallback_notice: modelChoice.fallback_notice,
    };
  }

  function boundedResult(result) {
    if (typeof result.text === "string" && result.text.length > 200000) {
      result.text = result.text.slice(0, 199960) + "\n\n[Response shortened to fit the local bridge limit.]";
    }
    return result;
  }

  // Always update runner on window
  window.__aiWebBridgeRunner = run;

  if (!window.__aiWebBridgeListenerAttached) {
    window.__aiWebBridgeListenerAttached = true;
    chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
      if (message?.type !== "bridge:job") return false;
      sendResponse({ ok: true, started: true });

      if (window.__aiWebBridgeRunner) {
        window.__aiWebBridgeRunner(message.job)
          .then((result) => chrome.runtime.sendMessage({
            type: "bridge:result",
            result: { id: message.job.id, ...boundedResult(result) }
          }))
          .catch((error) => chrome.runtime.sendMessage({
            type: "bridge:result",
            result: { id: message.job.id, error: error?.message || "Provider page interaction failed.", url: location.href }
          }));
      }
      return false;
    });
  }
})();
