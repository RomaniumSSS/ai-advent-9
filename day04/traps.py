"""День 4: капканы для модели — эталоны и проверки. Без API вообще.

Капкан на буквы: классические ловушки (9.11 vs 9.9, strawberry) больше не
работают на deepseek-chat — проверено вживую при подготовке спеки. Подсчёт
букв в реальных словах с двойными буквами всё ещё воспроизводимо ловит
модель: она завышает счёт на единицу.

Открытый запрос: точность у творческой задачи не может быть «совпадением
с текстом», поэтому она заменена на выполнение четырёх явных требований,
зашитых в промпт. Их проверяет код, не человек и не вторая модель.
"""

import re

LETTER_WORD = "рассредоточенность"
LETTER = "с"
LETTER_QUESTION = (
    f"Сколько букв «{LETTER}» в слове «{LETTER_WORD}»? Ответь только числом."
)

GADGET_PROMPT = (
    "Придумай название для нового гаджета, который ещё не существует. "
    "Ответь ровно 3 предложениями. Обязательно укажи цену (целым числом, любая "
    "валюта) и одно конкретное преимущество. Не используй слово «революционный» "
    "и его однокоренные формы."
)

# Написан руками, соблюдает все 4 требования. Служит и визуальным якорем
# на панели, и проверкой честности судьи: если судья не оценит человеческий
# текст высоко, это повод не доверять судье.
HUMAN_EXAMPLE = (
    "Деловой чемодан. Цена 19₽. Он силен своей кожей, крокодильей, не поверишь."
)

# Два семейства: глаголы действия и прилагательные качества. Первая версия
# (только глаголы) не прошла HUMAN_EXAMPLE — «силён своей кожей» не совпадало
# ни с одним словом. Список расширен после этой проверки.
BENEFIT_WORDS = [
    "позвол",
    "помога",
    "экономит",
    "увеличива",
    "снижа",
    "преимуществ",
    "благодаря",
    "прочн",
    "надёжн",
    "надежн",
    "качеств",
    "долговечн",
    "силён",
    "силен",
    "сильн",
    "мощн",
    "быстр",
    "лёгк",
    "легк",
    "удобн",
    "эконом",
]
BANNED_ROOT = "революцион"
PRICE_PATTERN = re.compile(
    r"\d[\d\s]*(?:₽|руб|долл|евро|крон|\$|USD|EUR|€)", re.IGNORECASE
)
SENTENCE_SPLIT = re.compile(r"[.!?]+(?:\s+|$)")


def letter_truth() -> int:
    return LETTER_WORD.count(LETTER)


def parse_letter_answer(text: str) -> int | None:
    """Последнее число в тексте — модель может порассуждать перед ответом."""
    matches = re.findall(r"\d+", text)
    return int(matches[-1]) if matches else None


def score_letter(answer: str) -> dict:
    value = parse_letter_answer(answer)
    return {
        "parsed": value is not None,
        "value": value,
        "correct": value == letter_truth() if value is not None else False,
    }


def count_sentences(text: str) -> int:
    return len([s for s in SENTENCE_SPLIT.split(text) if s.strip()])


def check_gadget(text: str) -> dict:
    """Четыре требования из GADGET_PROMPT, каждое проверяется независимо."""
    sentences_ok = count_sentences(text) == 3
    price_ok = bool(PRICE_PATTERN.search(text))
    benefit_ok = any(word in text.lower() for word in BENEFIT_WORDS)
    banned_ok = BANNED_ROOT not in text.lower()
    return {
        "sentences": sentences_ok,
        "price": price_ok,
        "benefit": benefit_ok,
        "no_banned": banned_ok,
        "score": sum([sentences_ok, price_ok, benefit_ok, banned_ok]),
    }


def normalize(text: str) -> str:
    """Для подсчёта уникальных ответов: регистр и пробелы не считаются различием."""
    return re.sub(r"\s+", " ", text.strip().lower())
