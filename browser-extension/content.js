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

    // 3. Modern ChatGPT: elements inside data-talvt-turn-state, data-turn-key, or parent of turn-action-controls
    const chatGptTurns = selectAll("[data-talvt-turn-state], [data-turn-key]");
    if (chatGptTurns.length) {
      const assistantBlocks = [];
      for (const turn of chatGptTurns) {
        if (!isVisible(turn)) continue;
        const allDivs = [...turn.querySelectorAll("div")];
        const gptDiv = allDivs.find(d => /^ChatGPT said:/i.test(visibleText(d))) ||
                       allDivs.find(d => isVisible(d) && visibleText(d).length > 50 && !/^You said:/i.test(visibleText(d)) && d.querySelector("pre, code, p, h1, h2, h3"));
        if (gptDiv) {
          assistantBlocks.push(gptDiv);
        } else if (turn.children && turn.children[0] && turn.children[0].children) {
          const subs = [...turn.children[0].children];
          if (subs.length >= 2) {
            assistantBlocks.push(subs[subs.length - 1]);
          } else if (subs.length === 1) {
            assistantBlocks.push(subs[0]);
          }
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
      for (const btn of clone.querySelectorAll("button, [role='button'], .copy-button, [aria-label*='Copy' i], [data-testid*='copy' i], .turn-action-controls")) {
        btn.remove();
      }
      text = visibleText(clone);
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
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    return models;
  }

  async function chooseModel(selectors, requested) {
    if (!requested) return "";
    let button = firstVisible(selectors?.model_btn);
    if (!button) {
      button = [...document.querySelectorAll("button")].find((item) => isVisible(item) && /model|mode|flash|sonnet|opus|gpt|pro/i.test(visibleText(item)));
    }
    if (!button) return "";
    button.click();
    await wait(400);
    const candidates = selectAll(selectors?.menu_item || "[role='menuitem'], [role='option'], [role='menuitemradio']")
      .filter(isVisible)
      .map((node) => ({ node, label: visibleText(node) }))
      .filter((item) => item.label);
    const key = requested.toLocaleLowerCase().trim();
    const exact = candidates.filter((item) => item.label.toLocaleLowerCase() === key);
    const matches = exact.length ? exact : candidates.filter((item) => item.label.toLocaleLowerCase().includes(key));
    if (matches.length !== 1) {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      return "";
    }
    matches[0].node.click();
    await wait(500);
    return matches[0].label;
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

    try {
      input.dispatchEvent(new InputEvent("beforeinput", {
        bubbles: true,
        cancelable: true,
        inputType: "insertText",
        data: prompt
      }));
    } catch (_e) {}

    const inserted = document.execCommand("insertText", false, prompt);
    if (!inserted || !visibleText(input)) {
      input.textContent = prompt;
    }

    input.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: prompt }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }

  async function submitPrompt(selectors, prompt) {
    let input = selectors?.input ? firstVisible(selectors.input) : null;
    if (!input) input = firstVisible(UNIVERSAL_INPUTS);
    if (!input) throw new Error("The AI chat box was not found on this tab. Ensure you are signed in.");

    await fillPrompt(input, prompt);

    let clicked = false;
    for (let i = 0; i < 20; i++) {
      let send = selectors?.send_btn ? firstVisible(selectors.send_btn) : null;
      if (!send) send = firstVisible(UNIVERSAL_SENDS);

      if (send && !send.disabled) {
        send.click();
        clicked = true;
        break;
      }
      await wait(100);
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

  async function waitForAnswer(selectors, initialText, timeoutSeconds) {
    const deadline = Date.now() + Math.max(15, timeoutSeconds) * 1000;
    let started = false;
    let lastText = initialText;
    let stableSince = Date.now();
    let bestText = "";

    while (Date.now() < deadline) {
      const messages = findAssistantMessages(selectors);
      const latestNode = messages.length ? messages[messages.length - 1] : null;
      const currentText = extractAssistantText(latestNode);
      const generating = isGenerating(selectors);

      if (generating || (currentText && currentText !== initialText)) {
        started = true;
      }

      if (currentText && currentText !== lastText) {
        lastText = currentText;
        bestText = currentText;
        stableSince = Date.now();
      } else if (started && bestText && !generating) {
        if ((Date.now() - stableSince) >= 2000) {
          return bestText;
        }
      }

      await wait(500);
    }

    if (bestText && bestText !== initialText) {
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
          snippet: text.slice(0, 100)
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
    const selected = await chooseModel(selectors, job.model);

    // Initial assistant state before prompt
    const initialMessages = findAssistantMessages(selectors);
    const initialText = initialMessages.length ? extractAssistantText(initialMessages[initialMessages.length - 1]) : "";

    await submitPrompt(selectors, job.prompt || "");
    const text = await waitForAnswer(selectors, initialText, job.timeout || 300);
    return { text, url: location.href, model: selected };
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
