let busy = false;
let readOnly = true;
const $ = (id) => document.getElementById(id);

async function api(path, body) {
  if (body && readOnly) throw new Error("Панель доступна только для чтения");
  const response = await fetch(`/api/${path}`, body ? {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  } : undefined);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Ошибка запроса");
  return data;
}

function status(message, error = false) {
  const box = $("status");
  box.textContent = message;
  box.classList.toggle("error", error);
}

function lock(value) {
  busy = value;
  document.querySelectorAll("button,input,textarea").forEach((element) => { element.disabled = value || readOnly; });
}

async function run(work) {
  if (busy || readOnly) return;
  lock(true);
  try { await work(); }
  catch (error) { status(error.message, true); }
  finally { lock(false); }
}

function renderNotes(layer, notes) {
  const box = $(`${layer}-notes`);
  box.replaceChildren();
  if (!Object.keys(notes).length) {
    const empty = document.createElement("span");
    empty.className = "empty";
    empty.textContent = "Пока нет записей";
    box.append(empty);
    return;
  }
  for (const [key, value] of Object.entries(notes)) {
    const item = document.createElement("div");
    item.className = "note";
    const text = document.createElement("span");
    const title = document.createElement("strong");
    title.textContent = `${key}: `;
    text.append(title, document.createTextNode(value));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "×";
    remove.title = `Удалить ${key} из ${layer}`;
    remove.setAttribute("aria-label", remove.title);
    remove.onclick = () => run(async () => {
      const result = await api("forget", { layer, key });
      render(result.state);
      status(result.message);
    });
    item.append(text, remove);
    box.append(item);
  }
}

function renderHistory(rows) {
  const box = $("history");
  box.replaceChildren();
  if (!rows.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "Здесь появятся вопросы и ответы";
    box.append(empty);
    return;
  }
  for (const row of rows) {
    const message = document.createElement("div");
    message.className = `message ${row.role === "user" ? "user" : "assistant"}`;
    message.textContent = row.content;
    box.append(message);
  }
  box.scrollTop = box.scrollHeight;
}

function render(state) {
  if (!state) return;
  $("context-box").hidden = true;
  $("context").textContent = "";
  $("active-user").textContent = state.scope.user;
  $("mode").textContent = state.offline ? "ОФЛАЙН · без модели и сети" : "Реальный API";
  for (const field of ["style", "format", "constraints"])
    $(`profile-${field}`).value = state.profile[field];
  $("user").value = state.scope.user;
  $("task").value = state.scope.task;
  $("session").value = state.scope.session;
  $("archive-metric").textContent =
    `${state.turns} ходов · ${state.short_history.length} последних сообщений в запросе`;
  for (const layer of ["short", "working", "long"])
    renderNotes(layer, state.notes[layer]);
  renderHistory(state.history);
  lock(busy);
}

for (const button of document.querySelectorAll("[data-save]")) {
  button.onclick = () => run(async () => {
    const result = await api("save", {
      layer: button.dataset.save,
      key: $("key").value,
      value: $("value").value,
    });
    render(result.state);
    $("key").value = "";
    $("value").value = "";
    status(result.message);
  });
}

$("open-scope").onclick = () => run(async () => {
  try {
    const result = await api("scope", {
      user: $("user").value,
      task: $("task").value,
      session: $("session").value,
    });
    render(result.state);
    status(result.message);
  } catch (error) {
    // Запрос мог не сменить активного агента. Возвращаем поля к фактической
    // области до следующей записи, иначе она визуально уйдёт не в ту задачу.
    const current = await api("state");
    render(current.state);
    throw error;
  }
});

$("reset").onclick = () => run(async () => {
  if (!window.confirm("Очистить текущий разговор и его короткие заметки?")) return;
  const result = await api("reset", {});
  render(result.state);
  status(result.message);
});

$("chat-form").onsubmit = (event) => {
  event.preventDefault();
  run(async () => {
    const result = await api("chat", { text: $("question").value });
    render(result.state);
    if (result.context) {
      $("context-box").hidden = false;
      $("context").textContent = JSON.stringify(result.context, null, 2);
    }
    if (result.ok) $("question").value = "";
    const usage = result.usage;
    const tokens = usage.prompt_tokens == null ? "?" : usage.prompt_tokens;
    const warnings = [result.store_error ? `НЕ СОХРАНЁН: ${result.store_error}` : "", result.state_error || ""].filter(Boolean);
    status([result.message, ...warnings].join("\n"), !result.ok || !result.saved || !!result.state_error);
  });
};

async function refresh() {
  try {
    const result = await api("state");
    readOnly = result.read_only !== false;
    render(result.state);
    if (readOnly) status("Только чтение. Для управления откройте SSH-туннель на 127.0.0.1:8036 (см. инструкцию установки).");
  } catch (error) { status(error.message, true); }
}
lock(false);
refresh();
setInterval(() => { if (readOnly && !busy) refresh(); }, 5000);

$("save-profile").onclick = () => run(async () => {
  const body = Object.fromEntries(["style", "format", "constraints"].map(field => [field, $(`profile-${field}`).value]));
  const result = await api("profile", body);
  render(result.state);
  status(result.message);
});
for (const button of document.querySelectorAll("[data-demo]")) {
  button.onclick = () => run(async () => {
    const result = await api("demo-user", {user: button.dataset.demo});
    render(result.state);
    status(result.message);
  });
}
