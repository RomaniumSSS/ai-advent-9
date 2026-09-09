"""Платная проверка дня 8: короткий/длинный диалог, пустой ответ, реальный отказ.

Запуск явный: uv run day08/test_live.py --env-file /путь/к/.env
Каждый результат сохраняется сразу; повтор запуска создаёт отдельный отчёт.
"""

import argparse
import hashlib
import json
import re
import tempfile
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from agent import Agent, AgentConfig, get_client
from store import SqliteStore


class MeasuredClient:
    """Настоящий SDK с журналом usage и верхней границей цены маршрутизации."""

    def __init__(self, budget, provider):
        self.sdk = get_client()
        self.chat = self
        self.completions = self
        self.calls = []
        self.reserved = 0.0
        self.budget = budget
        self.provider = provider

    def create(self, **kwargs):
        # Для потолка расхода берём байты, не приближённый токенизатор.
        # Ограничение цены — USD за миллион токенов, как в API OpenRouter.
        input_ceiling = sum(len(m['content'].encode('utf-8')) + 256 for m in kwargs['messages'])
        ceiling = input_ceiling * 0.10 / 1_000_000 + kwargs['max_tokens'] * 0.50 / 1_000_000
        if self.reserved + ceiling > self.budget:
            raise RuntimeError('исчерпан верхний бюджет прогона')
        self.reserved += ceiling
        kwargs['extra_body'] = {
            'provider': {'only': [self.provider], 'allow_fallbacks': False,
                         'max_price': {'prompt': 0.10, 'completion': 0.50}},
            'transforms': [],
        }
        record = {'request_messages': len(kwargs['messages']), 'request_max_tokens': kwargs['max_tokens'],
                  'ceiling_usd': ceiling}
        self.calls.append(record)
        try:
            response = self.sdk.chat.completions.create(**kwargs)
        except Exception as error:
            record.update(error_type=type(error).__name__, status_code=getattr(error, 'status_code', None),
                          error=str(error))
            raise
        record.update(id=response.id, usage=response.usage.model_dump() if response.usage else None,
                      provider=getattr(response, 'provider', None))
        return response


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--budget-usd', type=float, default=0.10)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--provider', default='coreweave')
    parser.add_argument('--overflow-only', action='store_true',
                        help='повторить только отказ и восстановление после двух коротких ходов')
    args = parser.parse_args()
    if args.env_file:
        load_dotenv(args.env_file)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = args.output or Path(__file__).parent / 'results' / f'live-{stamp}.json'
    if output.exists():
        parser.error('отчёт уже существует: выберите новый --output')
    output.parent.mkdir(parents=True, exist_ok=True)
    model_id = 'openai/gpt-oss-20b'
    with urllib.request.urlopen(f'https://openrouter.ai/api/v1/models/{model_id}/endpoints', timeout=30) as response:
        metadata = json.load(response)['data']
    endpoint = next(row for row in metadata['endpoints'] if row['tag'].split('/')[0] == args.provider)
    limit = endpoint['context_length']
    client = MeasuredClient(args.budget_usd, args.provider)
    report = {'timestamp_utc': stamp, 'model': model_id, 'endpoint': endpoint,
              'budget_usd': args.budget_usd, 'rows': [], 'checks': {}, 'transport': client.calls}

    def save():
        report['reserved_ceiling_usd'] = client.reserved
        report['reported_cost_usd'] = sum((row.get('usage') or {}).get('cost') or 0 for row in client.calls)
        serialized = json.dumps(report, ensure_ascii=False, indent=2)
        serialized = re.sub(r'user_(?!id\b)[A-Za-z0-9]+', 'user_redacted', serialized)
        output.write_text(serialized + '\n')

    def ask(agent, question, scenario):
        reply = agent.ask(question)
        row = {'scenario': scenario, 'reply': asdict(reply), 'stats': agent.store.stats(),
               'turns': agent.turns, 'question_chars': len(question),
               'question_sha256': hashlib.sha256(question.encode()).hexdigest()}
        report['rows'].append(row)
        save()
        print(f"{scenario}: ok={reply.ok} empty={reply.empty} "
              f"tokens={reply.prompt_tokens}→{reply.completion_tokens} "
              f"total={row['stats']['prompt_tokens']} cost_api={reply.cost_reported}", flush=True)
        return reply

    with tempfile.TemporaryDirectory(prefix='day08-live-') as tmp:
        path = Path(tmp) / 'test.db'
        config = AgentConfig(model='gpt-oss-20b', max_tokens=1500,
                             system_prompt='Отвечай кратко по-русски. Сохраняй факты из переписки.')
        store = SqliteStore(path, 'dialogue')
        agent = Agent(config=config, client=client, store=store)
        replies = []
        replies.append(ask(agent, 'Код проекта СЕВЕР-824. Запомни его. Ответь одним предложением.', 'short-1'))
        replies.append(ask(agent, 'Какой код проекта я назвал?', 'short-2'))
        # Перезапуск после короткого диалога: расход обязан пережить создание агента заново.
        agent = Agent(config=config, client=client, store=SqliteStore(path, 'dialogue'))
        report['checks']['restart_restores_two_turns'] = agent.restored_turns == 2
        paragraph = ('Учебный проект хранит историю диалога. Каждый новый запрос отправляет '
                     'системную роль, предыдущие сообщения и новый вопрос. Статистика API '
                     'показывает входные и выходные токены. Расход учитывается отдельно от текста. ')
        for turn in range(3, 3 if args.overflow_only else 13):
            question = f'Порция заметок {turn}:\n' + paragraph * 16 + '\nПодтверди получение одним предложением.'
            replies.append(ask(agent, question, f'long-{turn}'))
            if not replies[-1].ok:
                break
        stats = store.stats()
        expected_turns = 2 if args.overflow_only else 12
        report['checks']['dialogue_answers_present'] = len(replies) == expected_turns and all(r.ok and not r.empty for r in replies)
        report['checks']['api_usage_present'] = all(r.prompt_tokens is not None and r.completion_tokens is not None for r in replies)
        if report['checks']['api_usage_present']:
            report['checks']['dialogue_sum_matches_api'] = stats['prompt_tokens'] == sum(r.prompt_tokens for r in replies)
            if not args.overflow_only:
                report['checks']['long_input_larger_than_short'] = replies[-1].prompt_tokens > replies[1].prompt_tokens * 10

        empty_agent = Agent(config=AgentConfig(model='gpt-oss-20b', max_tokens=1), client=client,
                            store=SqliteStore(path, 'empty'))
        empty = ask(empty_agent, 'Вычисли 173 * 249 и объясни решение.', 'paid-empty')
        revived = SqliteStore(path, 'empty')
        report['checks']['empty_response_observed'] = empty.ok and empty.empty
        report['checks']['empty_usage_survives_restart'] = (
            empty.prompt_tokens is not None and revived.stats()['prompt_tokens'] == empty.prompt_tokens
            and revived.stats()['completion_tokens'] == empty.completion_tokens
            and revived.stats()['cost_reported'] == empty.cost_reported and revived.load() == [])

        # Простой повторяемый текст больше реального окна. История прежних ходов
        # также остаётся в запросе; transforms=[] запрещает автоматическое сжатие.
        oversized = 'Продолжение разговора. Данные:\n' + ' x' * (limit + 4096)
        before = agent.history
        before_calls = len(client.calls)
        overflow = ask(agent, oversized, 'real-overflow')
        error = (overflow.error or '').lower()
        report['checks']['real_overflow_reached_api'] = len(client.calls) == before_calls + 1
        # CoreWeave в реальном прогоне возвращает отрицательный max_tokens после
        # превышения окна, хотя мы передаём +1500. Это отдельный наблюдённый исход,
        # не универсальное толкование любого HTTP 400 как переполнения.
        context_error = 'context_length_exceeded' in error or 'input too long' in error
        negative_reserve = bool(re.search(r'max_tokens must be at least 1, got -\d+', error))
        report['overflow_kind'] = ('context_length_exceeded' if context_error else
                                   'negative_output_reserve' if negative_reserve else 'other')
        report['checks']['real_overflow_rejected'] = (
            not overflow.ok and client.calls[-1].get('status_code') == 400
            and overflow.budget.prompt > limit and client.calls[-1]['request_max_tokens'] > 0
            and (context_error or negative_reserve))
        report['checks']['overflow_preserves_history'] = agent.history == before and store.load() == before

        guarded = Agent(config=AgentConfig(model='gpt-oss-20b', max_tokens=1500, context_limit=limit,
                                          system_prompt=config.system_prompt), client=client, store=store)
        before_calls = len(client.calls)
        local = ask(guarded, oversized, 'local-guard')
        report['checks']['guard_prevents_network_call'] = local.overflow and len(client.calls) == before_calls
        recovery = ask(agent, 'Какой код проекта был в самом начале? Ответь только кодом.', 'recovery')
        report['checks']['recovery_after_overflow'] = recovery.ok and 'СЕВЕР-824' in recovery.text
        save()
    print(json.dumps(report['checks'], ensure_ascii=False, indent=2))
    print(f'Отчёт: {output}; списано API: ${report["reported_cost_usd"]:.8f}')
    raise SystemExit(0 if all(report['checks'].values()) else 1)


if __name__ == '__main__':
    main()
