"""Проверяемые границы синтетической CRM и небольшого поискового корпуса."""
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import TypedDict

ROOT = Path(__file__).resolve().parent
class Event(TypedDict):
    code: str
    detail: str
class Ticket(TypedDict):
    id: str
    user_id: str
    subject: str
    events: list[Event]
class User(TypedDict):
    id: str
    name: str
    email: str
class Context(TypedDict):
    user: User
    ticket: Ticket
class Source(TypedDict):
    id: str
    title: str
    keywords: list[str]
    text: str

def string(value: object, name: str, limit: int = 4000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"Некорректное поле {name}")
    return value

def load_crm() -> dict:
    data = json.loads((ROOT / 'data/crm.json').read_text())
    for user in data['users']:
        for key in ('id', 'name', 'email'): string(user[key], key)
    for ticket in data['tickets']: validate_ticket(ticket)
    return data

def validate_ticket(ticket: object) -> Ticket:
    if not isinstance(ticket, dict) or set(ticket) != {'id', 'user_id', 'subject', 'events'}: raise ValueError('Некорректный тикет')
    for key in ('id', 'user_id', 'subject'): string(ticket.get(key), key)
    if not isinstance(ticket.get('events'), list): raise ValueError('Некорректные события')
    for event in ticket['events']:
        if not isinstance(event, dict) or set(event) != {'code', 'detail'}: raise ValueError('Некорректное событие')
        string(event.get('code'), 'code'); string(event.get('detail'), 'detail')
    return ticket

def retrieve(question: str, ticket: Ticket, corpus: list | None = None) -> list[Source]:
    corpus = json.loads((ROOT / 'data/knowledge.json').read_text()) if corpus is None else corpus
    if not isinstance(corpus, list): raise ValueError('Некорректный корпус')
    codes = {event['code'] for event in ticket['events']}
    scored = []
    for source in corpus:
        if not isinstance(source, dict): raise ValueError('Некорректный источник')
        for key in ('id', 'title', 'text'): string(source.get(key), key)
        if not isinstance(source.get('keywords'), list): raise ValueError('Некорректные keywords')
        score = 0
        for keyword in source['keywords']:
            string(keyword, 'keyword')
            score += 20 if keyword in codes else int(keyword.casefold() in question.casefold())
        if score: scored.append((score, source))
    return [source for _, source in sorted(scored, key=lambda x: (-x[0], x[1]['id']))[:2]]


DIAGNOSTIC_CODES = {'email_unverified', 'invitation_expired'}
AUTH_WORDS = ('авторизация', 'авторизоваться', 'войти', 'вход', 'логин', 'залогиниться',
              'залогинится', 'зайти', 'пускает', 'доступ', 'пароль', 'почта', 'приглашение', 'login', 'signin')

def clarification(question: str, ticket: Ticket) -> tuple[str, str] | None:
    """Консервативная граница небольшой базы, а не универсальный классификатор намерений."""
    words = re.findall(r'[а-яёa-z]+', question.casefold())
    auth = any(SequenceMatcher(None, word, term).ratio() >= .78
               for word in words for term in AUTH_WORDS)
    other_symptom = re.search(r'экран|страниц[а-я]* бел|оплат|экспорт|загрузк|ошибк[а-я]* (?:404|500)', question.casefold())
    if not auth or other_symptom:
        return ('bounded_support', 'Я помогаю с TeamDesk. В базе есть сведения о входе и приглашениях; для этого вопроса данных недостаточно. Уточните, что происходит в TeamDesk и какой текст ошибки виден.')
    codes = {event['code'] for event in ticket['events']}
    if not codes:
        return ('rule_based_clarification', 'Уточните точный текст ошибки и этап входа. Причина пока неизвестна. Не передавайте пароль.')
    if len(codes) != 1 or not codes.issubset(DIAGNOSTIC_CODES):
        return ('ambiguous_diagnostics', 'События тикета не позволяют однозначно определить причину. Уточните текущий текст ошибки и этап входа. Без времени событий нельзя выбрать последнее. Не передавайте пароль.')
    # AICODE-NOTE: свободный текст не доказывает изменение состояния CRM;
    # при отрицании/изменении статуса безопаснее уточнить, чем переопределить событие.
    if re.search(r'подтвердил|подтвержден|подтверждён|подтверждена|действител|не ист[её]к|нов[а-я]* приглаш|verified|valid', question.casefold()):
        return ('contradictory_context', 'Вопрос может описывать состояние, отличное от события тикета. Уточните текущую ошибку и когда изменилось состояние; пока причина не подтверждена.')
    # AICODE-NOTE: сообщение о текущем тексте ошибки не интерпретируем
    # по словарю диагнозов: старое событие не доказывает причину нового симптома.
    if re.search(r'пиш[а-я]*|сообщ[а-я]*|выда[а-я]*|показыв[а-я]*|ошиб[а-я]*|[«"“]', question.casefold()):
        return ('reported_error', 'Вы сообщили о текущей ошибке. Событие тикета само по себе не подтверждает её причину. Уточните точный текст и этап входа; не передавайте пароль.')
    return None


def validate_context(value: object, user_id: str, ticket_id: str) -> Context:
    if not isinstance(value, dict) or set(value) != {'user', 'ticket'}:
        raise ValueError('Некорректный контекст MCP')
    user = value['user']
    if not isinstance(user, dict) or set(user) != {'id', 'name', 'email'}: raise ValueError('Некорректный пользователь MCP')
    for key in ('id', 'name', 'email'): string(user.get(key), key)
    ticket = validate_ticket(value['ticket'])
    if ticket['user_id'] != user_id or user['id'] != user_id or ticket['id'] != ticket_id:
        raise PermissionError('MCP нарушил scope')
    return value
