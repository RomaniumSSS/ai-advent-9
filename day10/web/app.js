let panel = null,
	busy = false,
	pending = null,
	steps = { project: 0, personal: 0 },
	scenarios = {};
const $ = (id) => document.getElementById(id);
const num = (x) => (x == null ? "?" : x.toLocaleString("ru-RU"));

async function api(path, data) {
	const options = data
		? {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify(data),
			}
		: {};
	const response = await fetch(`/api/${path}`, options);
	const result = await response.json();
	if (!response.ok) throw Error(result.error || "Ошибка сервера");
	return result;
}

function renderStrategies(state) {
	const box = $("strategies");
	box.replaceChildren();
	for (const item of state.strategies) {
		const button = document.createElement("button");
		button.textContent = item.label;
		button.dataset.name = item.name;
		button.className = item.name === panel.strategy ? "active" : "";
		button.onclick = async () => {
			if (busy) return;
			lock(true);
			try {
				render(await api("strategy", { name: item.name }));
			} catch (error) {
				status(error.message, true);
			} finally {
				lock(false);
			}
		};
		box.append(button);
	}
}

function renderBranches() {
	const box = $("branches");
	box.replaceChildren();
	for (const row of panel.branches) {
		const button = document.createElement("button");
		button.textContent = row.session;
		button.className = row.active ? "active" : "";
		button.title = row.parent
			? `Ветка от ${row.parent}, точка ${row.checkpoint}`
			: "Исходный разговор";
		button.onclick = async () => {
			if (busy || row.active) return;
			lock(true);
			try {
				render(await api("switch", { session: row.session }));
			} catch (error) {
				status(error.message, true);
			} finally {
				lock(false);
			}
		};
		box.append(button);
	}
}

function status(text, isError = false) {
	$("status").textContent = text;
	$("status").classList.toggle("error", isError);
}

function render(state) {
	panel = state;
	const usage = state.usage;
	$("panel-title").textContent = `${state.strategy_label} · ${state.session}`;
	$("metrics").innerHTML =
		`<div class="metric">Учтено токенов<strong>${num(usage.total.tokens)}</strong></div>` +
		`<div class="metric">Из них на память<strong>${num(usage.facts.tokens)}</strong></div>` +
		`<div class="metric">Оценка входа<strong>${num(state.budget.prompt)}</strong></div>` +
		`<div class="metric">Уйдёт сообщений<strong>${state.sent_messages} / ${state.archived_messages}</strong></div>`;
	$("details").textContent =
		`Ходов: ${state.turns} · Вызовов: чат ${usage.chat.calls}, память ${usage.facts.calls} · ` +
		`Вход / выход API: ${num(usage.total.prompt_tokens)} / ${num(usage.total.completion_tokens)}`;
	$("strategy-note").textContent =
		state.strategy === "full"
			? "вся история в каждом запросе"
			: `последние ${state.recent_messages} сообщений${state.strategy === "facts" ? " + факты" : ""}`;

	const history = $("history");
	history.replaceChildren();
	if (!state.history.length) {
		const empty = document.createElement("div");
		empty.className = "empty";
		empty.textContent = "Здесь появится разговор";
		history.append(empty);
	}
	// Сообщения, которые в модель уже не уезжают, показываются бледными, но
	// показываются: архив пользователя не режется ни одной стратегией.
	const keep =
		state.strategy === "full" ? state.history.length : state.recent_messages;
	const firstSent = Math.max(0, state.history.length - keep);
	state.history.forEach((message, index) => {
		const node = document.createElement("div");
		node.className = `message ${message.role}${index < firstSent ? " dropped" : ""}`;
		const role = document.createElement("span");
		role.className = "role";
		role.textContent =
			(message.role === "user" ? "Вы" : "DeepSeek") +
			(index < firstSent ? " · вне контекста" : "");
		node.append(role, document.createTextNode(message.content));
		history.append(node);
	});
	history.scrollTop = history.scrollHeight;

	const facts = Object.entries(state.facts);
	$("facts").textContent = facts.length
		? facts.map(([key, value]) => `${key}: ${value}`).join("\n")
		: state.strategy === "facts"
			? "Память пуста. Она пополнится после следующего ответа."
			: "Память наполняется только в стратегии Sticky Facts.";

	const event = state.facts_event;
	if (event)
		status(
			event.error || `Память обновлена (revision ${event.revision})`,
			!!event.error,
		);
	renderStrategies({ strategies: window.STRATEGIES });
	renderBranches();
}

function lock(value) {
	busy = value;
	for (const id of [
		"send",
		"reset",
		"next",
		"scenario",
		"branch",
		"branch-name",
		"question",
	])
		$(id).disabled = value;
	for (const button of document.querySelectorAll(
		"#strategies button, #branches button",
	))
		button.disabled = value;
	$("send").textContent = pending ? "Повторить" : "Отправить";
}

$("chat").onsubmit = async (event) => {
	event.preventDefault();
	if (busy) return;
	const text = pending?.text || $("question").value.trim();
	if (!text) return;
	const requestId = pending?.id || crypto.randomUUID();
	lock(true);
	status("Ожидаем ответ…");
	try {
		const result = await api("chat", { text, request_id: requestId });
		render(result.state);
		if (result.error || result.empty) {
			// Ответ получен: повтор модели — это новый запрос, новый id.
			pending = { text, id: crypto.randomUUID() };
			status(result.error || "Пустой ответ. Можно повторить.", true);
		} else if (result.store_error) {
			pending = null;
			status(`Ответ получен, но не сохранён: ${result.store_error}`, true);
		} else {
			pending = null;
			if (!result.state.facts_event) status(`Ответ за ${result.elapsed} с`);
			$("question").value = "";
		}
	} catch (error) {
		// При обрыве HTTP тот же id возвращает записанный результат без нового вызова.
		pending = { text, id: requestId };
		status(error.message, true);
	} finally {
		lock(false);
	}
};

$("branch").onclick = async () => {
	if (busy) return;
	const name = $("branch-name").value.trim();
	if (!name) {
		status("Нужно имя ветки", true);
		return;
	}
	lock(true);
	try {
		const result = await api("branch", { name });
		render(result);
		$("branch-name").value = "";
		status(
			`Создана ветка ${result.created}. Переключитесь, чтобы продолжить в ней.`,
		);
	} catch (error) {
		status(error.message, true);
	} finally {
		lock(false);
	}
};

$("reset").onclick = async () => {
	if (!confirm("Удалить историю, память и все ветки этого эксперимента?"))
		return;
	lock(true);
	try {
		render(await api("reset", {}));
		pending = null;
		steps = { project: 0, personal: 0 };
		$("step").textContent = "";
		status("");
	} catch (error) {
		status(error.message, true);
	} finally {
		lock(false);
	}
};

$("next").onclick = () => {
	const key = $("scenario").value;
	const items = scenarios[key]?.questions || [];
	if (steps[key] >= items.length) {
		$("step").textContent = "Все вопросы подставлены";
		return;
	}
	$("question").value = items[steps[key]++];
	$("step").textContent = `Вопрос ${steps[key]} / ${items.length}`;
};

async function refresh() {
	const state = await api("state");
	window.STRATEGIES = state.strategies;
	$("hint").textContent =
		`${state.panel.model} · потолок ответа ${num(state.max_tokens)} токенов`;
	render(state.panel);
}

fetch("/api/scenarios")
	.then((r) => r.json())
	.then((s) => (scenarios = s))
	.catch(() => {});
refresh().catch((error) => status(error.message, true));

api("results")
	.then((rows) => {
		const box = $("saved-results");
		box.replaceChildren();
		if (!rows.length) {
			box.textContent = "Завершённых прогонов пока нет.";
			return;
		}
		const table = document.createElement("table");
		const addRow = (values, header = false) => {
			const tr = document.createElement("tr");
			for (const value of values) {
				const cell = document.createElement(header ? "th" : "td");
				cell.textContent = value;
				tr.append(cell);
			}
			table.append(tr);
		};
		addRow(
			[
				"Стратегия",
				"Ходов",
				"Вызовов",
				"Вход",
				"Выход",
				"Всего токенов",
				"Фактов найдено",
			],
			true,
		);
		for (const row of rows)
			addRow([
				row.strategy_label,
				row.turns,
				row.calls,
				num(row.prompt_tokens),
				num(row.completion_tokens),
				num(row.tokens),
				row.facts_found == null
					? "—"
					: `${row.facts_found} / ${row.facts_total}`,
			]);
		box.append(table);
		const note = document.createElement("p");
		note.className = "table-note";
		note.textContent =
			"Токены успешных ответов вместе со служебными вызовами памяти. Ошибки без usage в сумму не входят.";
		box.append(note);
	})
	.catch((error) => ($("saved-results").textContent = error.message));
