// TERMINAL 404 - browser side: reads commands, sends JSON, prints the reply.
const screen = document.getElementById("screen");
const output = document.getElementById("output");
const input = document.getElementById("input");
const mirror = document.getElementById("mirror");
const promptEl = document.getElementById("prompt");
const statusEl = document.getElementById("status");

const history = [];
let historyPos = 0;
let busy = false;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function addLine(text, kind = "out") {
  const div = document.createElement("div");
  div.className = "line " + kind;
  div.textContent = text;
  output.appendChild(div);
  screen.scrollTop = screen.scrollHeight;
}

async function printLines(lines, delay = 0) {
  for (const l of lines) {
    addLine(l.text, l.kind);
    if (delay) await sleep(delay);
  }
}

async function post(url, body = {}) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

function applyMeta(data) {
  promptEl.textContent = data.prompt;
  statusEl.textContent = "clues: " + data.clues;
}

async function startGame() {
  busy = true;
  output.innerHTML = "";
  const data = await post("/api/start");
  applyMeta(data);
  await printLines(data.lines, 70);
  addLine("");
  busy = false;
  input.focus();
}

async function submit() {
  const cmd = input.value;
  input.value = "";
  mirror.textContent = "";
  addLine(promptEl.textContent + " " + cmd, "cmd");
  if (!cmd.trim()) return;
  history.push(cmd);
  historyPos = history.length;

  busy = true;
  try {
    if (cmd.trim().toLowerCase() === "reset") {
      await startGame();
      return;
    }
    const data = await post("/api/command", { command: cmd });
    if (data.clear) output.innerHTML = "";
    applyMeta(data);
    await printLines(data.lines, 12);
  } catch (err) {
    addLine("CONNECTION LOST: is the Flask server still running?", "warn");
  }
  busy = false;
}

input.addEventListener("input", () => (mirror.textContent = input.value));

input.addEventListener("keydown", (e) => {
  if (busy) return e.preventDefault();
  if (e.key === "Enter") {
    submit();
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    if (historyPos > 0) input.value = history[--historyPos];
    mirror.textContent = input.value;
  } else if (e.key === "ArrowDown") {
    e.preventDefault();
    historyPos = Math.min(historyPos + 1, history.length);
    input.value = history[historyPos] || "";
    mirror.textContent = input.value;
  } else if (e.key.toLowerCase() === "l" && e.ctrlKey) {
    e.preventDefault();
    output.innerHTML = "";
  }
});

screen.addEventListener("click", () => input.focus());
startGame();
