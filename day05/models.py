"""День 5: каталог моделей и арифметика расхода. Без API вообще.

Все модели закреплены за deepinfra — единственным провайдером, который держит все три
основные, и у всех трёх он самый дешёвый. Закрепление принципиально: одни и те же веса
у разных провайдеров идут по разной цене и скорости (gpt-oss-120b — 970 токенов в секунду
на cerebras против 41 на deepinfra), и без явного провайдера колонка стоимости стала бы
выдумкой, а колонка времени мерила бы чужое железо.

Идентификаторы здесь — слаги OpenRouter, а сам провайдер задаётся отдельным полем
запроса (PROVIDER ниже). У роутера HuggingFace, с которого начинался день, провайдер
писался прямо в идентификатор суффиксом ':deepinfra'; на OpenRouter это отдельный
механизм, потому что он умеет ещё и запрещать подмену провайдера при сбое.

Цены сверены 06.09.2026 с эндпоинтом deepinfra в OpenRouter, а не взяты с витрины:
на витрине HuggingFace три записи из семи оказались округлены вверх, у glm-5.3-flash —
вдвое. Пропускная способность по-прежнему с huggingface.co/inference/models и остаётся
заявленной величиной, а не измеренной.
Заявленные температуры — из generation_config.json репозитория модели. Это справка
от авторов, а не наблюдение: API не сообщает, с какой температурой он ответил,
и провайдер вправе переопределить значение у себя.
"""

# Кого просить обслужить запрос. Пустой список запасных вариантов означает, что при
# недоступности deepinfra вызов упадёт с ошибкой, а не уедет к другому провайдеру.
# Тихая подмена железа испортила бы замер времени, никак себя не обозначив.
PROVIDER = {"only": ["deepinfra"], "allow_fallbacks": False}

MAX_TOKENS = 4000

# Консервативная оценка до вызова: Unicode-символ занимает до четырёх UTF-8 байт,
# а byte fallback токенизатора — до одного токена на байт. Надбавка покрывает
# служебный chat-шаблон; на разведке 05.09 он вместе с коротким вопросом занимал
# до 108 токенов.
TOKENS_PER_CHAR = 4
WRAPPER_TOKENS = 256

# Верхняя оценка ответа судьи: он просит одно число, но потолок берём с запасом.
JUDGE_OUTPUT_TOKENS = 20

MODELS = {
    "gpt-oss-120b": {
        "id": "openai/gpt-oss-120b",
        "params": "117B",
        "params_num": 117,
        "price_in": 0.037,
        "price_out": 0.17,
        "default_temp": None,  # в generation_config.json поля нет
        "hf": "https://huggingface.co/openai/gpt-oss-120b",
    },
    "deepseek-v4-flash": {
        "id": "deepseek/deepseek-v4-flash-0731",
        "params": "304B",
        "params_num": 304,
        "price_in": 0.06,
        "price_out": 0.18,
        "default_temp": 1.0,
        "hf": "https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash-0731",
    },
    "glm-5.3": {
        "id": "z-ai/glm-5.3",
        "params": "753B",
        "params_num": 753,
        "price_in": 1.20,
        "price_out": 4.00,
        "default_temp": 1.0,
        "hf": "https://huggingface.co/zai-org/GLM-5.3",
    },
    "kimi-k3": {
        "id": "moonshotai/kimi-k3",
        "params": "2.8T",
        "params_num": 2800,
        "price_in": 2.85,
        "price_out": 14.25,
        "default_temp": None,  # в generation_config.json поля нет
        "hf": "https://huggingface.co/moonshotai/Kimi-K3",
    },
    "gpt-oss-20b": {
        "id": "openai/gpt-oss-20b",
        "params": "21B",
        "params_num": 21,
        "price_in": 0.03,
        "price_out": 0.14,
        "default_temp": None,  # в generation_config.json поля нет
        "hf": "https://huggingface.co/openai/gpt-oss-20b",
    },
    "qwen3.6-27b": {
        "id": "qwen/qwen3.6-27b",
        "params": "27B",
        "params_num": 27,
        "price_in": 0.32,
        "price_out": 3.20,
        "default_temp": 1.0,
        "hf": "https://huggingface.co/Qwen/Qwen3.6-27B",
    },
    "glm-5.3-flash": {
        "id": "z-ai/glm-5.3-flash",
        "params": "321B",
        "params_num": 321,
        "price_in": 0.075,
        "price_out": 0.25,
        "default_temp": 1.0,
        "hf": "https://huggingface.co/zai-org/GLM-5.3-Flash",
    },
}

# Младшая, средняя, старшая — по числу параметров. Разброс 24 раза.
DEFAULT_TRIO = ("gpt-oss-120b", "deepseek-v4-flash", "kimi-k3")


def price_of(prompt_tokens: int, completion_tokens: int, key: str) -> float:
    """Чистая арифметика по прайсу. Числа обязательны, результат всегда число."""
    entry = MODELS[key]
    return (
        prompt_tokens / 1_000_000 * entry["price_in"]
        + completion_tokens / 1_000_000 * entry["price_out"]
    )


def cost(
    prompt_tokens: int | None, completion_tokens: int | None, key: str
) -> float | None:
    """Доллары за один вызов по факту. None, если провайдер не вернул usage.

    Ноль здесь соврал бы, что вызов был бесплатным.
    """
    if prompt_tokens is None or completion_tokens is None:
        return None
    return price_of(prompt_tokens, completion_tokens, key)


def estimate_prompt_tokens(question: str) -> int:
    return int(len(question) * TOKENS_PER_CHAR) + WRAPPER_TOKENS


def estimate_calls(model_keys: list[str], runs: int, judge: bool) -> int:
    calls = len(model_keys) * runs
    return calls * 2 if judge else calls


def cheapest_key() -> str:
    """Самая дешёвая на выходе. Ей работает судья: выход и есть его основная статья."""
    return min(MODELS, key=lambda key: MODELS[key]["price_out"])


def estimate_worst_cost(
    model_keys: list[str], runs: int, judge: bool, question: str
) -> float:
    """Верхняя граница расхода, а не ожидаемый. Считается по MAX_TOKENS.

    Панель обязана показывать границу, за которую точно не выйдет: среднее ничего
    не гарантирует, а при MAX_TOKENS=4000 один вызов старшей модели стоит в пределе
    заметную долю месячных кредитов.
    """
    prompt_tokens = estimate_prompt_tokens(question)
    total = sum(price_of(prompt_tokens, MAX_TOKENS, key) * runs for key in model_keys)
    if judge:
        answers = len(model_keys) * runs
        total += (
            price_of(
                MAX_TOKENS + prompt_tokens + WRAPPER_TOKENS,
                JUDGE_OUTPUT_TOKENS,
                cheapest_key(),
            )
            * answers
        )
    return total


def sampling_args(temperature: float | None) -> dict:
    """Что подмешать в тело запроса. Пустой словарь — параметра там не будет вовсе.

    Отдельная функция ровно затем, чтобы это можно было проверить тестом без сети:
    разница между «не передали» и «передали ноль» невидима глазом и меняет поведение
    модели. Ноль — это конкретная настройка, а не умолчание.
    """
    return {} if temperature is None else {"temperature": temperature}
