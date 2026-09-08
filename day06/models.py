"""День 6: каталог моделей и арифметика расхода. Без API вообще.

Копия нужной части дня 5, а не импорт из него: дни между собой кодом не связаны,
каждый должен читаться отдельно, как сданная работа. Взято только то, что нужно
агенту, — оценок расхода до вызова и судьи здесь нет.

Цены сверены 06.09.2026 с эндпоинтом deepinfra в OpenRouter, а не взяты с витрины.
"""

# Провайдер НЕ закреплён, в отличие от дня 5. Там пин обязателен: сравниваются модели,
# и тихая подмена железа испортила бы колонки времени и цены. Здесь сравнивать нечего —
# это разговор, и отказ общего пула DeepInfra (429, engine_overloaded) означал бы просто
# неработающий чат. Пусть роутер уводит запрос к живому провайдеру.
#
# Цена этого решения: price_of() считает по прайсу deepinfra и становится оценкой,
# а не фактом. Настоящая сумма приходит в usage.cost — на неё и смотреть, если
# разойдутся. Для дня 6 это приемлемо: замеров, которые нужно сопоставлять, здесь нет.
PROVIDER = {"allow_fallbacks": True}

MAX_TOKENS = 4000

MODELS = {
    "gpt-oss-120b": {
        "id": "openai/gpt-oss-120b",
        "params": "117B",
        "price_in": 0.037,
        "price_out": 0.17,
    },
    "deepseek-v4-flash": {
        "id": "deepseek/deepseek-v4-flash-0731",
        "params": "304B",
        "price_in": 0.06,
        "price_out": 0.18,
    },
    "glm-5.3-flash": {
        "id": "z-ai/glm-5.3-flash",
        "params": "321B",
        "price_in": 0.075,
        "price_out": 0.25,
    },
    "gpt-oss-20b": {
        "id": "openai/gpt-oss-20b",
        "params": "21B",
        "price_in": 0.03,
        "price_out": 0.14,
    },
    "kimi-k3": {
        "id": "moonshotai/kimi-k3",
        "params": "2.8T",
        "price_in": 2.85,
        "price_out": 14.25,
    },
}

# Умолчание дня 6 — дешёвая и быстрая. В дне 5 замерено, что Kimi даёт 98.6% счёта
# при тройном прогоне, а разговорному агенту нужны десятки ходов, не три.
DEFAULT_MODEL = "deepseek-v4-flash"


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


def sampling_args(temperature: float | None) -> dict:
    """Что подмешать в тело запроса. Пустой словарь — параметра там не будет вовсе.

    Разница между «не передали» и «передали ноль» невидима глазом и меняет поведение
    модели. Ноль — это конкретная настройка, а не умолчание.
    """
    return {} if temperature is None else {"temperature": temperature}
