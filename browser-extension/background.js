const NATIVE_HOST = "com.ai_web_bridge.native";
const DEFAULT_PORT = 8765;

let isProcessing = false;
let isPolling = false;
let processingStartTime = 0;

async function configuredPort() {
  const state = await chrome.storage.local.get(["port"]);
  const port = Number(state.port || DEFAULT_PORT);
  if (!Number.isInteger(port) || port < 1 || port > 65535) return DEFAULT_PORT;
  return port;
}

async function isAutoRunEnabled() {
  const state = await chrome.storage.local.get(["autoRun"]);
  return state.autoRun !== false; // enabled by default
}

function sendNativeMessage(message) {
  return new Promise((resolve) => {
    chrome.runtime.sendNativeMessage(NATIVE_HOST, message, (response) => {
      if (chrome.runtime.lastError) {
        resolve({ ok: false, error: showNativeHostError().message });
        return;
      }
      resolve(response || { ok: false, error: "The local helper returned no response." });
    });
  });
}

function showNativeHostError(error) {
  const message = chrome.runtime.lastError?.message || error?.message || "Native host disconnected.";
  if (/not found|specified native messaging host/i.test(message)) {
    return new Error(`Native helper is not registered. Run --extension-setup --extension-id ${chrome.runtime.id}.`);
  }
  return new Error(message);
}

function getStatus() {
  return new Promise(async (resolve) => {
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      resolve(value);
    };
    try {
      const port = await configuredPort();
      const message = await sendNativeMessage({ action: "status", port });
      finish(message?.ok
        ? { ok: true, status: message.status }
        : { ok: false, error: message?.error || "Local helper returned an error." });
      setTimeout(() => finish({ ok: false, error: "The local helper did not respond." }), 10000);
    } catch (error) {
      finish({ ok: false, error: showNativeHostError(error).message });
    }
  });
}

function hostsMatch(tabUrl, targetUrl) {
  if (!tabUrl || !targetUrl) return false;
  try {
    const tabHost = new URL(tabUrl).hostname.toLowerCase();
    const targetHost = new URL(targetUrl).hostname.toLowerCase();
    if (tabHost === targetHost || tabHost.endsWith("." + targetHost) || targetHost.endsWith("." + tabHost)) {
      return true;
    }
    const aliases = {
      "chatgpt.com": ["chat.openai.com", "openai.com"],
      "chat.openai.com": ["chatgpt.com", "openai.com"],
      "x.com": ["twitter.com", "grok.com"],
      "grok.com": ["x.com", "twitter.com"],
      "blackbox.ai": ["www.blackbox.ai"],
      "www.blackbox.ai": ["blackbox.ai"],
    };
    const list = aliases[targetHost] || [];
    return list.some((a) => tabHost === a || tabHost.endsWith("." + a));
  } catch {
    return false;
  }
}

function waitForTabLoaded(tabId, timeoutMs = 20000) {
  return new Promise((resolve) => {
    let done = false;
    const timer = setTimeout(() => {
      if (!done) {
        done = true;
        chrome.tabs.onUpdated.removeListener(listener);
        resolve(false);
      }
    }, timeoutMs);

    function listener(updatedId, info) {
      if (updatedId === tabId && info.status === "complete") {
        if (!done) {
          done = true;
          clearTimeout(timer);
          chrome.tabs.onUpdated.removeListener(listener);
          resolve(true);
        }
      }
    }
    chrome.tabs.onUpdated.addListener(listener);
  });
}

async function activateTab(tab) {
  if (!tab || !tab.id) return;
  try {
    await chrome.tabs.update(tab.id, { active: true });
    if (chrome.windows && tab.windowId) {
      await chrome.windows.update(tab.windowId, { focused: true });
    }
  } catch (_e) {}
}

async function findOrCreateProviderTab(targetUrl, chatUrl, isNewChat) {
  const tabs = await chrome.tabs.query({});

  // 1. If we have a registered chat URL for this project and we are not starting a fresh chat:
  if (chatUrl && !isNewChat) {
    const chatNorm = chatUrl.split("?")[0].replace(/\/+$/, "").toLowerCase();
    const exactTab = tabs.find((t) => t.url && t.url.split("?")[0].replace(/\/+$/, "").toLowerCase() === chatNorm);
    if (exactTab && exactTab.id) {
      await activateTab(exactTab);
      return exactTab;
    }
  }

  // 2. Look for open provider tab by host
  const existingTab = tabs.find((t) => t.url && hostsMatch(t.url, targetUrl));
  if (existingTab && existingTab.id) {
    await activateTab(existingTab);

    // If we have a project chat URL and the tab is currently on a different URL, navigate it there
    if (chatUrl && !isNewChat) {
      const curNorm = (existingTab.url || "").split("?")[0].replace(/\/+$/, "").toLowerCase();
      const chatNorm = chatUrl.split("?")[0].replace(/\/+$/, "").toLowerCase();
      if (curNorm !== chatNorm) {
        try {
          await chrome.tabs.update(existingTab.id, { url: chatUrl });
          await waitForTabLoaded(existingTab.id, 10000);
          await new Promise((r) => setTimeout(r, 1200));
          const refreshed = await chrome.tabs.get(existingTab.id);
          if (refreshed?.url) return refreshed;
        } catch (_e) {}
      }
    }

    try {
      const fresh = await chrome.tabs.get(existingTab.id);
      if (fresh?.url) return fresh;
    } catch (_e) {}
    return existingTab;
  }

  // 3. If no matching provider tab exists anywhere in the browser, create one
  const destinationUrl = (!isNewChat && chatUrl) ? chatUrl : targetUrl;
  const newTab = await chrome.tabs.create({ url: destinationUrl, active: true });
  await waitForTabLoaded(newTab.id);
  await new Promise((resolve) => setTimeout(resolve, 2000));
  try {
    const fresh = await chrome.tabs.get(newTab.id);
    if (fresh?.url) return fresh;
  } catch (_e) {}
  if (!newTab.url) newTab.url = destinationUrl;
  return newTab;
}

async function executeJobOnTab(tab, portNumber) {
  let tabUrl = tab.url;
  if (!tabUrl && tab.id) {
    try {
      const fresh = await chrome.tabs.get(tab.id);
      tabUrl = fresh?.url;
    } catch (_e) {}
  }
  if (!tabUrl) {
    throw new Error("Could not determine tab URL for provider matching.");
  }

  const started = await sendNativeMessage({ action: "start", port: portNumber, tab_url: tabUrl });
  if (!started?.ok || !started.job) {
    if (started?.error && started.error.includes("already being handled")) {
      console.log("[AI Web Bridge] Request already claimed by another tick.");
      return false;
    }
    throw new Error(started?.error || "Could not claim the waiting request from local helper.");
  }

  try {
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["content.js"] });
    await chrome.tabs.sendMessage(tab.id, { type: "bridge:job", job: started.job });
    return true;
  } catch (error) {
    const result = {
      id: started.job.id,
      error: error?.message || "Could not start the provider tab adapter.",
      url: tabUrl,
    };
    await sendNativeMessage({ action: "result", port: portNumber, result });
    throw error;
  }
}

async function pollForJobs() {
  if (isProcessing) {
    if (Date.now() - processingStartTime > 90000) {
      console.warn("[AI Web Bridge] Watchdog: resetting stuck isProcessing state.");
      isProcessing = false;
      chrome.action.setBadgeText({ text: "" });
    } else {
      return;
    }
  }
  if (isPolling) return;
  isPolling = true;

  try {
    const auto = await isAutoRunEnabled();
    if (!auto) return;

    const res = await getStatus();
    if (!res.ok || !res.status?.ready || res.status.claimed) {
      return;
    }

    isProcessing = true;
    processingStartTime = Date.now();
    chrome.action.setBadgeText({ text: "RUN" });
    chrome.action.setBadgeBackgroundColor({ color: "#155eef" });

    const portNumber = await configuredPort();
    const waitingUrl = res.status.url;
    const chatUrl = res.status.chat_url;
    const isNewChat = Boolean(res.status.new_chat);
    const provider = res.status.provider || "AI";

    const tab = await findOrCreateProviderTab(waitingUrl, chatUrl, isNewChat);
    if (!tab || !tab.id) {
      throw new Error(`Could not find or open tab for ${provider} (${waitingUrl}).`);
    }

    await executeJobOnTab(tab, portNumber);
  } catch (error) {
    console.error("[AI Web Bridge] Auto-run error:", error);
    isProcessing = false;
    chrome.action.setBadgeText({ text: "ERR" });
    chrome.action.setBadgeBackgroundColor({ color: "#d92d20" });
    setTimeout(() => chrome.action.setBadgeText({ text: "" }), 5000);
  } finally {
    isPolling = false;
  }
}

// Check every 1.5 seconds for pending CLI jobs
setInterval(pollForJobs, 1500);

// Alarm keepalive for Manifest V3 Service Worker
chrome.alarms.create("bridge_auto_watcher", { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener(() => {
  pollForJobs();
});

chrome.runtime.onStartup.addListener(pollForJobs);
chrome.runtime.onInstalled.addListener(pollForJobs);

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "bridge:status") {
    getStatus().then(sendResponse);
    return true;
  }

  if (message?.type === "bridge:run-active-tab") {
    (async () => {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab?.id || !tab.url) throw new Error("Could not read active tab.");
      const portNumber = await configuredPort();
      isProcessing = true;
      chrome.action.setBadgeText({ text: "RUN" });
      chrome.action.setBadgeBackgroundColor({ color: "#155eef" });
      await executeJobOnTab(tab, portNumber);
      sendResponse({ ok: true });
    })().catch((error) => {
      isProcessing = false;
      chrome.action.setBadgeText({ text: "" });
      sendResponse({ ok: false, error: error?.message || "Execution failed." });
    });
    return true;
  }

  if (message?.type === "bridge:result") {
    (async () => {
      isProcessing = false;
      chrome.action.setBadgeText({ text: "" });
      const port = await configuredPort();
      return sendNativeMessage({ action: "result", port, result: message.result });
    })()
      .then(sendResponse)
      .catch((error) => {
        isProcessing = false;
        chrome.action.setBadgeText({ text: "" });
        sendResponse({ ok: false, error: error?.message || "Could not return result." });
      });
    return true;
  }
});
