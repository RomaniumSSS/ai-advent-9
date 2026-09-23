"""День 11: каталог моделей и арифметика расхода. Без API вообще.

Самостоятельная копия нужной части проверенного каталога прошлых дней.
Дни между собой кодом не связаны; фактически списанное берётся из usage.cost.

Оценочные цены сверялись 06.09.2026 для deepinfra и могут устареть.
"""

# AICODE-NOTE: живые прогоны сравниваются на одном провайдере; fallback
# сделал бы расхождение тарифа и поведения невоспроизводимым.
PROVIDER = {"only": ["deepinfra"], "allow_fallbacks": False}

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

# DeepSeek V4 Flash выбрана Романом для обоих режимов дня 9.
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
