"""Общий бюджет эксперимента: резерв до сети, фактическое списание после ответа.

Все процессы проверки и записи используют один ledger. Даже сбой процесса
не освобождает резерв: неизвестное списание не становится нулём.
"""
import json
import math
import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace
from openai import OpenAI

MODEL_ID = 'deepseek/deepseek-v4-flash-0731'
CONTEXT_LIMIT = 1_048_576
PRICE_CAP = {'prompt': 0.05, 'completion': 0.16}
PROVIDER = {'only': ['open-inference/fp8'], 'allow_fallbacks': False,
            'require_parameters': True, 'max_price': PRICE_CAP}
DEFAULT_LEDGER = Path(__file__).parent / 'results' / 'budget.db'

class BudgetBusy(RuntimeError):
    pass


class BudgetLedger:
    def __init__(self, path=DEFAULT_LEDGER, limit=0.50):
        if not math.isfinite(limit) or limit <= 0:
            raise ValueError('бюджет должен быть положительным конечным числом')
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, ceiling REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS reservations (
                    id INTEGER PRIMARY KEY, label TEXT NOT NULL, reserved REAL NOT NULL,
                    actual REAL, state TEXT NOT NULL, response_id TEXT);
            ''')
            db.execute('INSERT OR IGNORE INTO settings VALUES (1, ?)', (limit,))
            if db.execute('SELECT ceiling FROM settings').fetchone()[0] != limit:
                raise ValueError('нельзя незаметно изменить бюджет существующего эксперимента')
        self.limit = limit

    def connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def reserve(self, amount, label):
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError('некорректный резерв')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            rows = db.execute('SELECT reserved, actual, state FROM reservations').fetchall()
            if any(state == 'overrun' for _, _, state in rows):
                raise RuntimeError('провайдер превысил резерв; эксперимент остановлен')
            spent = sum(actual if actual is not None else reserved for reserved, actual, _ in rows)
            if spent + amount > self.limit:
                settled_or_unknown = sum(actual if actual is not None else reserved for reserved, actual, state in rows if state != 'pending')
                if any(state == 'pending' for _, _, state in rows) and settled_or_unknown + amount <= self.limit:
                    raise BudgetBusy('деньги зарезервированы другими выполняющимися вызовами')
                raise RuntimeError(f'бюджет: осталось ${self.limit-spent:.4f}, требуется резерв ${amount:.4f}')
            return db.execute('INSERT INTO reservations(label,reserved,state) VALUES (?, ?, ?)',
                              (label, amount, 'pending')).lastrowid

    def settle(self, ticket, actual, response_id=None):
        if actual is not None and (not math.isfinite(actual) or actual < 0):
            actual = None
        with self.connect() as db:
            reserved = db.execute('SELECT reserved FROM reservations WHERE id=?', (ticket,)).fetchone()[0]
            state = 'unknown' if actual is None else 'overrun' if actual > reserved else 'settled'
            db.execute('UPDATE reservations SET actual=?,state=?,response_id=? WHERE id=?',
                       (actual, state, response_id, ticket))

    def report(self):
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            rows = [dict(r) for r in db.execute('SELECT * FROM reservations ORDER BY id')]
        known = sum(r['actual'] for r in rows if r['actual'] is not None)
        held = sum(r['reserved'] for r in rows if r['actual'] is None)
        return {'limit': self.limit, 'known_cost': known, 'held_for_unknown': held,
                'available': self.limit-known-held, 'reservations': rows}

class MeasuredClient:
    def __init__(self, client, ledger, label, record_path=None):
        self.client, self.ledger, self.label = client, ledger, label
        self.record_path = Path(record_path) if record_path else None
        self.records = json.loads(self.record_path.read_text()) if self.record_path and self.record_path.exists() else []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        if kwargs['model'] != MODEL_ID or not 1 <= kwargs['max_tokens'] <= 4000:
            raise RuntimeError('этот бюджет рассчитан только для DeepSeek V4 Flash и выхода до 4000')
        if any(not isinstance(m.get('content'), str) for m in kwargs['messages']):
            raise RuntimeError('расчёт поддерживает только текстовые сообщения')
        # AICODE-NOTE: у этой версии DeepSeek ByteLevel BPE без нормализации:
        # текст не длиннее числа UTF-8 байтов в токенах. Добавляем 1024 на каждую
        # роль и 1024 на весь шаблон, гораздо больше опубликованной разметки.
        # Это резерв, а не измерение prompt_tokens; при нарушении прекращаем вызовы.
        # Поддерживаются только plain text system/user/assistant, без tools.
        if any(set(m) - {"role", "content"} or m["role"] not in {"system", "user", "assistant"}
               for m in kwargs['messages']):
            raise RuntimeError('резерв рассчитан только для обычного текстового чата')
        input_bound = sum(len(m['content'].encode('utf-8')) for m in kwargs['messages']) + 1024 * (len(kwargs['messages']) + 1)
        if input_bound + kwargs['max_tokens'] > CONTEXT_LIMIT:
            raise RuntimeError('консервативная граница запроса превышает окно')
        reserve = (input_bound * PRICE_CAP['prompt'] + kwargs['max_tokens'] * PRICE_CAP['completion']) / 1_000_000
        kind = 'summary' if kwargs['messages'][0]['content'].startswith('Сожми историю') else 'chat'
        deadline = time.monotonic() + 180
        while True:
            try:
                ticket = self.ledger.reserve(reserve, self.label + ':' + kind)
                break
            except BudgetBusy:
                if time.monotonic() >= deadline:
                    raise RuntimeError('не дождались освобождения резерва; запрос не отправлен')
                time.sleep(1)
        kwargs['extra_body'] = {'provider': PROVIDER, 'reasoning': {'enabled': False}, 'usage': {'include': True}}
        row = {'kind': kind, 'ticket': ticket, 'input_upper_bound': input_bound, 'request': kwargs}
        try:
            response = self.client.chat.completions.create(**kwargs)
        except Exception as error:
            self.ledger.settle(ticket, None)
            row['error'] = type(error).__name__ + ': ' + str(error)
            self._record(row)
            raise
        usage = getattr(response, 'usage', None)
        actual = getattr(usage, 'cost', None)
        self.ledger.settle(ticket, actual, getattr(response, 'id', None))
        if usage and ((getattr(usage, 'prompt_tokens', None) or 0) > input_bound
                      or (getattr(usage, 'completion_tokens', None) or 0) > kwargs['max_tokens']):
            with self.ledger.connect() as db:
                db.execute("UPDATE reservations SET state='overrun' WHERE id=?", (ticket,))
            row['bound_violation'] = True
        row['response'] = response.model_dump(mode='json') if hasattr(response, 'model_dump') else {}
        self._record(row)
        return response

    def _record(self, row):
        self.records.append(row)
        if self.record_path:
            self.record_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.record_path.with_suffix('.tmp')
            temporary.write_text(json.dumps(self.records, ensure_ascii=False, indent=2)+'\n')
            temporary.replace(self.record_path)


def real_client():
    import os
    return OpenAI(api_key=os.environ['OPENROUTER_API_KEY'], base_url='https://openrouter.ai/api/v1',
                  max_retries=0, timeout=180)
