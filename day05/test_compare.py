"""Офлайн-проверки движка дня 5. Без API.

Проверяются чистые части compare.py: имя файла сессии и подсчёт агрегатов.
Сами вызовы к моделям здесь не проверяются — для этого есть живой прогон.

Запуск:
    uv run day05/test_compare.py
"""

import sys
import tempfile
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import compare as compare_module  # noqa: E402
from compare import (  # noqa: E402
    REQUEST_TIMEOUT_SECONDS,
    ask,
    get_client,
    judge_answer,
    load_sessions,
    save_session,
    session_name,
    summarize,
)
from models import JUDGE_OUTPUT_TOKENS  # noqa: E402


def record(
    elapsed,
    prompt_tokens,
    completion_tokens,
    money,
    error=None,
    judge=None,
    chars=42,
    answer="текст",
    finish_reason="stop",
    judge_cost=None,
    judge_attempted=False,
):
    return {
        "model": "glm-5.3",
        "answer": answer,
        "answer_chars": chars,
        "finish_reason": finish_reason,
        "elapsed": elapsed,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "reasoning_tokens": None,
        "cost": money,
        "temperature": None,
        "error": error,
        "judge": judge,
        "judge_cost": judge_cost,
        "judge_attempted": judge_attempted,
    }


def check_session_name() -> list[str]:
    problems = []
    cases = [
        ("Объясни рекурсию простыми словами", "obyasni-rekursiyu"),
        ("Hello world", "hello-world"),
    ]
    for question, expected_part in cases:
        name = session_name(question)
        if expected_part not in name:
            problems.append(
                f"имя сессии для {question!r} не содержит {expected_part!r}: {name}"
            )
        if not name.endswith(".json"):
            problems.append(f"имя сессии не заканчивается на .json: {name}")

    for bad in ("???", "   ", "!!!---"):
        name = session_name(bad)
        if "-question-" not in name or not name.endswith(".json"):
            problems.append(
                f"вопрос без букв обязан содержать хвост -question-, получили {name}"
            )

    for dangerous in ("../../etc/passwd", "a/b/c", "..\\win"):
        name = session_name(dangerous)
        if "/" in name or "\\" in name or ".." in name.replace(".json", ""):
            problems.append(f"имя сессии выходит за папку results: {name}")

    if len(session_name("я" * 300)) > 80:
        problems.append(
            "имя сессии не обрезается: длинный вопрос дал слишком длинное имя"
        )
    if session_name("один вопрос") == session_name("один вопрос"):
        problems.append("два запуска в одну секунду получили одинаковое имя файла")
    return problems


def check_summarize() -> list[str]:
    problems = []

    got = summarize([record(1.0, 100, 200, 0.001), record(3.0, 100, 200, 0.001)])
    if got["ok"] != 2:
        problems.append(f"два успешных вызова: ждали ok=2, получили {got['ok']}")
    if got["api_ok"] != 2:
        problems.append(f"два API-вызова: ждали api_ok=2, получили {got['api_ok']}")
    if got["time_avg"] != 2.0 or got["time_min"] != 1.0 or got["time_max"] != 3.0:
        problems.append(f"время: ждали среднее 2.0 при 1.0 и 3.0, получили {got}")
    if abs(got["cost_total"] - 0.002) > 1e-12:
        problems.append(f"стоимость обязана складываться: {got['cost_total']}")

    mixed = summarize(
        [record(1.0, 100, 200, 0.001), record(9.0, None, None, None, error="сбой")]
    )
    if mixed["ok"] != 1 or mixed["runs"] != 2:
        problems.append(f"сбойный вызов обязан считаться в runs, но не в ok: {mixed}")
    if mixed["time_avg"] != 1.0:
        problems.append(f"агрегаты обязаны считаться только по успешным: {mixed}")

    empty = summarize([record(1.0, None, None, None, error="сбой")])
    if empty["ok"] != 0:
        problems.append(f"все вызовы упали: ждали ok=0, получили {empty}")

    no_usage = summarize([record(1.0, None, None, None)])
    if no_usage["cost_total"] is not None or no_usage["prompt_avg"] is not None:
        problems.append(
            f"без usage стоимость и токены обязаны быть None, а не нулём: {no_usage}"
        )

    partial_usage = summarize(
        [record(1.0, 100, 200, 0.001), record(1.0, None, None, None)]
    )
    if partial_usage["cost_total"] is not None:
        problems.append(
            "частично отсутствующий usage не позволяет показывать известную часть как total"
        )

    truncated = summarize(
        [
            record(
                2.0,
                20,
                4000,
                0.016,
                chars=0,
                answer="",
                finish_reason="length",
            )
        ]
    )
    if truncated["api_ok"] != 1 or truncated["ok"] != 0:
        problems.append(
            f"обрезанный пустой ответ: ждали api_ok=1 и ok=0, получили {truncated}"
        )
    if truncated["cost_total"] != 0.016:
        problems.append("стоимость обрезанного ответа всё равно должна учитываться")

    judged = summarize(
        [record(1.0, 100, 200, 0.001, judge=8), record(1.0, 100, 200, 0.001, judge=6)]
    )
    if judged["judge_avg"] != 7.0:
        problems.append(
            f"средняя оценка судьи: ждали 7.0, получили {judged['judge_avg']}"
        )

    judged_with_cost = summarize(
        [
            record(
                1.0,
                100,
                200,
                0.001,
                judge=8,
                judge_cost=0.0002,
                judge_attempted=True,
            )
        ]
    )
    if judged_with_cost["cost_total"] != 0.0012:
        problems.append(f"стоимость судьи не прибавилась к общей: {judged_with_cost}")

    chars = summarize(
        [record(1.0, 100, 200, 0.001, chars=10), record(1.0, 100, 200, 0.001, chars=20)]
    )
    if chars["chars_avg"] != 15.0:
        problems.append(
            f"средняя длина ответа: ждали 15.0, получили {chars['chars_avg']}"
        )
    return problems


def check_judge() -> list[str]:
    problems = []
    original = compare_module.ask
    answers = iter(("8", "11"))
    prompts = []
    limits = []

    def fake_ask(prompt, key, temperature=None, max_tokens=None):
        prompts.append(prompt)
        limits.append(max_tokens)
        return {"answer": next(answers), "error": None, "cost": 0.0002}

    compare_module.ask = fake_ask
    try:
        valid = judge_answer("Сколько будет 2+2?", "4")
        invalid = judge_answer("Сколько будет 2+2?", "4")
    finally:
        compare_module.ask = original

    if valid != {"score": 8, "cost": 0.0002, "error": None}:
        problems.append(f"валидная оценка судьи разобрана неверно: {valid}")
    if invalid["score"] is not None or not invalid["error"]:
        problems.append(f"оценка вне 1..10 обязана быть отклонена: {invalid}")
    if (
        not prompts
        or "Сколько будет 2+2?" not in prompts[0]
        or "<answer>\n4" not in prompts[0]
    ):
        problems.append("судья не получил исходный вопрос вместе с ответом")
    if limits != [JUDGE_OUTPUT_TOKENS, JUDGE_OUTPUT_TOKENS]:
        problems.append(f"судья получил неверный лимит токенов: {limits}")
    return problems


def check_missing_token() -> list[str]:
    problems = []
    original_token = os.environ.pop("OPENROUTER_API_KEY", None)
    original_client = compare_module._client
    compare_module._client = None
    try:
        result = ask("вопрос", "gpt-oss-120b")
    finally:
        compare_module._client = original_client
        if original_token is not None:
            os.environ["OPENROUTER_API_KEY"] = original_token
    if not result["error"] or "OPENROUTER_API_KEY" not in result["error"]:
        problems.append(f"отсутствующий OPENROUTER_API_KEY обработан неверно: {result}")
    return problems


def check_client_limits() -> list[str]:
    problems = []
    original_token = os.environ.get("OPENROUTER_API_KEY")
    original_client = compare_module._client
    original_openai = compare_module.OpenAI
    captured = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    os.environ["OPENROUTER_API_KEY"] = "test-token"
    compare_module._client = None
    compare_module.OpenAI = FakeOpenAI
    try:
        get_client()
    finally:
        compare_module.OpenAI = original_openai
        compare_module._client = original_client
        if original_token is None:
            os.environ.pop("OPENROUTER_API_KEY", None)
        else:
            os.environ["OPENROUTER_API_KEY"] = original_token

    if captured.get("timeout") != REQUEST_TIMEOUT_SECONDS:
        problems.append(f"таймаут клиента не закреплён: {captured.get('timeout')!r}")
    # Самый долгий ответ, который мы наблюдали живьём (Kimi K3, 06.09). Таймаут ниже
    # двойного запаса начал бы обрывать законные ответы, и обрыв попал бы в выводы
    # как отказ модели.
    slowest_observed = 244.0
    if REQUEST_TIMEOUT_SECONDS < 2 * slowest_observed:
        problems.append(
            f"таймаут {REQUEST_TIMEOUT_SECONDS} с не даёт двойного запаса "
            f"к наблюдавшимся {slowest_observed} с"
        )
    if captured.get("max_retries") != 0:
        problems.append(
            f"SDK может скрыто повторять измеряемый вызов: {captured.get('max_retries')!r}"
        )
    return problems


def check_save_session() -> list[str]:
    problems = []
    original = compare_module.RESULTS
    with tempfile.TemporaryDirectory() as folder:
        compare_module.RESULTS = Path(folder)
        try:
            result = {"question": "один вопрос"}
            first = save_session(result)
            second = save_session(result)
            (Path(folder) / "broken.json").write_text(
                '{"models":["glm-5.3"],"by_model":{"glm-5.3":{"records":[{}]}}}',
                encoding="utf-8",
            )
            loaded = load_sessions()
        finally:
            compare_module.RESULTS = original
        if first == second or not first.exists() or not second.exists():
            problems.append("повторный запуск перезаписал предыдущую сессию")
        if len(loaded) != 2:
            problems.append("структурно битая сессия не была безопасно пропущена")
    return problems


def main() -> None:
    problems = (
        check_session_name()
        + check_summarize()
        + check_judge()
        + check_missing_token()
        + check_client_limits()
        + check_save_session()
    )
    if problems:
        print("FAIL")
        for problem in problems:
            print(f"        {problem}")
        sys.exit(1)

    print(
        "ok    имя сессии: транслитерация, хвост -question, без выхода за папку, обрезка"
    )
    print(
        "ok    агрегаты: сбойные вызовы не портят средние, без usage — None, а не ноль"
    )
    print("ok    обрезанные ответы не считаются завершёнными, их стоимость сохраняется")
    print("ok    судья видит вопрос, принимает только 1..10 и учитывается в стоимости")
    print(
        "ok    отсутствие OPENROUTER_API_KEY превращается в запись ошибки, а не падение"
    )
    print(
        f"ok    один прогон — один вызов, ожидание ограничено "
        f"{REQUEST_TIMEOUT_SECONDS:.0f} секундами"
    )
    print("ok    параллельные сессии получают разные имена и не перезаписываются")


if __name__ == "__main__":
    main()
