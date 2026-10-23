const statusNode = document.getElementById("status");
const runSection = document.getElementById("run");
const targetNode = document.getElementById("target");
const runButton = document.getElementById("runButton");
const portInput = document.getElementById("port");
const autoRunCheckbox = document.getElementById("autoRun");

async function refresh() {
  const state = await chrome.storage.local.get(["port", "autoRun"]);
  portInput.value = state.port || 8765;
  autoRunCheckbox.checked = state.autoRun !== false;
  document.getElementById("extensionId").value = chrome.runtime.id;

  const response = await chrome.runtime.sendMessage({ type: "bridge:status" });
  if (!response?.ok) {
    const error = response?.error || "Native helper is not available.";
    statusNode.textContent = /10061|actively refused|ECONNREFUSED/i.test(error)
      ? "Local bridge idle. Start a CLI command with --browser-mode extension to send a request."
      : error;
    runSection.hidden = true;
    return;
  }

  if (!response.status.ready) {
    statusNode.textContent = autoRunCheckbox.checked
      ? "⚡ Ready & Listening in background. Any CLI prompt will run automatically."
      : "Connected. No CLI request is waiting.";
    runSection.hidden = true;
    return;
  }

  const hostname = new URL(response.status.url).hostname;
  statusNode.textContent = autoRunCheckbox.checked
    ? `⚡ Processing: Provider ${response.status.provider} (${hostname})`
    : "A CLI request is waiting.";
  targetNode.textContent = `Provider: ${response.status.provider} · Target: ${hostname}`;
  runSection.hidden = false;
}

autoRunCheckbox.addEventListener("change", async () => {
  await chrome.storage.local.set({ autoRun: autoRunCheckbox.checked });
  await refresh();
});

document.getElementById("savePort").addEventListener("click", async () => {
  const port = Number(portInput.value);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    statusNode.textContent = "Choose a valid local bridge port.";
    return;
  }
  await chrome.storage.local.set({ port });
  statusNode.textContent = "Port saved.";
  await refresh();
});

runButton.addEventListener("click", async () => {
  runButton.disabled = true;
  statusNode.textContent = "Starting manual request in this tab…";
  const response = await chrome.runtime.sendMessage({ type: "bridge:run-active-tab" });
  statusNode.textContent = response?.ok
    ? "Request sent to this tab."
    : (response?.error || "Could not start request.");
  runButton.disabled = false;
});

refresh();
