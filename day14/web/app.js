let busy = false;
let readOnly = true;
let currentState = null;
const $ = (id) => document.getElementById(id);
const stages = ["planning", "execution", "validation", "done"];

async function api(path, body) {
  if (body && readOnly) throw new Error("Панель доступна только для чтения");
  const response = await fetch(`/api/${path}`, body ? {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body),
  } : undefined);
  const data = await response.json();
  if (!response.ok) throw Object.assign(new Error(data.error || "Ошибка запроса"), {serverState: data.state});
  return data;
}

function status(message, error = false) {
  $("status").textContent = message;
  $("status").classList.toggle("error", error);
}

function lock(value) {
  busy = value;
  document.querySelectorAll("button,input,textarea").forEach((element) => {
    // Pause remains available while a model turn is in flight. The backend
    // handles this route outside the per-runtime lock and version binding
    // prevents the late model reply from advancing the FSM.
    element.disabled = readOnly || (value && element.id !== "pause");
  });
}

async function run(work) {
  if (busy || readOnly) return;
  lock(true);
  try { await work(); }
  catch (error) {
    if (error.serverState) render(error.serverState);
    status(error.message, true);
  } finally { lock(false); }
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
      const result = await api("forget", {layer, key});
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

function renderPipeline(task) {
  const activeIndex = task ? stages.indexOf(task.stage) : -1;
  const boxes = stages.map((name, index) => {
    const box = document.createElement("div");
    box.className = "stage";
    if (index === activeIndex) box.classList.add("active");
    if (index < activeIndex) box.classList.add("done");
    const number = document.createElement("strong");
    number.textContent = `0${index + 1}`;
    const label = document.createElement("span");
    label.textContent = name;
    box.append(number, label);
    return box;
  });
  $("pipeline").replaceChildren(...boxes);
}

function renderTask(task, events, workflow) {
  renderPipeline(task);
  $("task-empty").hidden = Boolean(task);
  $("task-state").hidden = !task;
  if (task) {
    $("objective").textContent = task.objective;
    $("current_step").textContent = task.current_step;
    $("expected").textContent = task.expected_action || "нет";
    $("task-status").textContent = task.status;
    $("version").textContent = task.version;
    $("workflow-actor").textContent = workflow?.actor || "none";
    $("workflow-proposal").textContent = workflow?.proposal?.result || "нет";
    const paused = task.status === "paused";
    $("pause").hidden = paused;
    $("resume").hidden = !paused;
    $("advance").hidden = paused || task.stage === "done";
    $("changes").hidden = paused || task.stage !== "validation";
    $("workflow-run").hidden = paused || task.stage === "done" || workflow?.actor !== "model";
    $("workflow-approve").hidden = paused || workflow?.actor !== "user";
    $("workflow-revise").hidden = paused || workflow?.actor !== "user";
    const labels = {
      submit_plan: "Согласовать план",
      submit_result: "Передать результат на проверку",
      approve: "Принять результат",
    };
    $("advance").textContent = labels[task.expected_action] || "Завершить этап";
  }
  const rows = events.length ? events.slice().reverse().map((event) => {
    const row = document.createElement("div");
    row.className = "event";
    const title = document.createElement("strong");
    title.textContent = `v${event.version} · ${event.event}`;
    row.append(title, document.createElement("br"), document.createTextNode(`${event.from_stage || "∅"} → ${event.to_stage}`));
    return row;
  }) : [Object.assign(document.createElement("div"), {className: "empty", textContent: "Событий пока нет"})];
  $("events").replaceChildren(...rows);
}

function render(state) {
  if (!state) return;
  currentState = state;
  $("context-box").hidden = true;
  $("context").textContent = "";
  $("active-user").textContent = state.scope.user;
  $("agent-generation").textContent = `Экземпляр агента №${state.generation}`;
  $("mode").textContent = state.offline
    ? "ОФЛАЙН · полный агент без сети"
    : `ОНЛАЙН · ${state.model} через OpenRouter`;
  for (const field of ["style", "format", "constraints"])
    $(`profile-${field}`).value = state.profile[field];
  $("user").value = state.scope.user;
  $("task").value = state.scope.task;
  $("session").value = state.scope.session;
  $("archive-metric").textContent = `${state.turns} ходов · ${state.short_history.length} последних сообщений в запросе`;
  for (const layer of ["short", "working", "long"])
    renderNotes(layer, state.notes[layer]);
  renderTask(state.task_state, state.task_events || [], state.workflow || {});
  renderHistory(state.history);
  const invariantRows = (state.invariants || []).map((item) => {
    const row = document.createElement("div");
    row.className = "event";
    const title = document.createElement("strong");
    title.textContent = `${item.invariant_id} · ${item.category}`;
    row.append(title, document.createElement("br"), document.createTextNode(item.rule));
    return row;
  });
  $("invariants").replaceChildren(...invariantRows);
  $("invariant-metric").textContent = `${invariantRows.length} правил · ${(state.invariant_checks || []).length} проверок`;
  const checkRows = (state.invariant_checks || []).slice(0, 5).map((item) => {
    const row = document.createElement("div");
    row.className = "event";
    row.textContent = `${item.phase}: ${item.decision} · ${item.invariant_ids.join(", ") || "конфликтов нет"}`;
    return row;
  });
  $("invariant-checks").replaceChildren(...checkRows);
  lock(busy);
}

function showContext(result) {
  if (!result.context) return;
  $("context-box").hidden = false;
  $("context").textContent = JSON.stringify(result.context, null, 2);
}

for (const button of document.querySelectorAll("[data-save]")) {
  button.onclick = () => run(async () => {
    const result = await api("save", {layer: button.dataset.save, key: $("key").value, value: $("value").value});
    render(result.state);
    $("key").value = "";
    $("value").value = "";
    status(result.message);
  });
}

$("open-scope").onclick = () => run(async () => {
  try {
    const result = await api("scope", {user: $("user").value, task: $("task").value, session: $("session").value});
    render(result.state);
    status(result.message);
  } catch (error) {
    const current = await api("state");
    render(current.state);
    throw error;
  }
});

$("reset").onclick = () => run(async () => {
  if (!window.confirm("Очистить текущий разговор и краткосрочные заметки? FSM сохранится.")) return;
  const result = await api("reset", {});
  render(result.state);
  status(result.message);
});

$("chat-form").onsubmit = (event) => {
  event.preventDefault();
  run(async () => {
    const result = await api("chat", {text: $("question").value});
    render(result.state);
    showContext(result);
    if (result.ok) $("question").value = "";
    const warnings = [result.store_error ? `НЕ СОХРАНЁН: ${result.store_error}` : "", result.state_error || ""].filter(Boolean);
    status([result.message, ...warnings].join("\n"), !result.ok || !result.saved || Boolean(result.state_error));
  });
};

$("test-conflict").onclick = () => run(async () => {
  const result = await api("chat", {text: $("conflict-request").value});
  render(result.state);
  showContext(result);
  status(`${result.decision === "refuse" ? "ОТКАЗ" : "РАЗРЕШЕНО"}: ${result.message}`, result.decision === "refuse");
});

$("save-profile").onclick = () => run(async () => {
  const body = Object.fromEntries(["style", "format", "constraints"].map((field) => [field, $(`profile-${field}`).value]));
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

$("start-task").onclick = () => run(async () => {
  const result = await api("task/start", {objective: $("task-objective").value});
  render(result.state);
  status(result.message);
});

$("advance").onclick = () => run(async () => {
  const result = await api("task/action", {result: $("task-result").value});
  render(result.state);
  $("task-result").value = "";
  status(result.message);
});

$("changes").onclick = () => run(async () => {
  const result = await api("task/action", {action: "request_changes", result: $("task-result").value});
  render(result.state);
  $("task-result").value = "";
  status(result.message);
});

$("pause").onclick = async () => {
  if (readOnly) return;
  try {
    const result = await api("task/pause", {});
    render(result.state);
    status(result.message);
  } catch (error) {
    if (error.serverState) render(error.serverState);
    status(error.message, true);
  }
};

$("resume").onclick = () => run(async () => {
  const result = await api("task/resume", {});
  render(result.state);
  status(result.message);
});

$("restart").onclick = () => run(async () => {
  const result = await api("task/restart", {});
  render(result.state);
  status(result.message);
});

$("continue").onclick = () => run(async () => {
  const result = await api("continue", {});
  render(result.state);
  showContext(result);
  status(`${result.message}\n${result.reply}`);
});

$("workflow-run").onclick = () => run(async () => {
  const result = await api("workflow/run", {max_model_turns: 4});
  render(result.state);
  status(`${result.message} · model turns: ${result.loop.model_turns}`);
});

$("workflow-approve").onclick = () => run(async () => {
  const result = await api("workflow/approve", {max_model_turns: 4});
  render(result.state);
  status(`${result.message} · model turns: ${result.loop.model_turns}`);
});

$("workflow-revise").onclick = () => run(async () => {
  const result = await api("workflow/revise", {feedback: $("task-result").value, max_model_turns: 4});
  render(result.state);
  $("task-result").value = "";
  status(`${result.message} · model turns: ${result.loop.model_turns}`);
});

async function refresh() {
  try {
    const result = await api("state");
    readOnly = result.read_only !== false;
    render(result.state);
  } catch (error) { status(error.message, true); }
}

lock(false);
refresh();
