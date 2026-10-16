"""Десять разных вопросов Qwen: бесплатный frozen plan, отдельный явный execute."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile

from dotenv import dotenv_values
from jsonschema import Draft202012Validator

from day31.assistant import Assistant
from day31.contracts import SourceChunk
from day31.eval.compare_models import ContextSnapshot, corpus_manifest, fingerprint
from day31.mcp_client import GitMcpClient
from day31.provider import (ANSWER_SCHEMA, SYSTEM, BudgetLedger, OpenRouterProvider,
                           ProviderProfile, build_request, check_endpoint, request_reserve)
from day31.retrieval import RetrievalIndex

ROOT = Path(__file__).resolve().parents[1]
SHARED_LEDGER = Path('/Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day31-dev-assistant/day31/.runtime/live-20261016/budget.sqlite3')
CASES = ROOT/'eval/qwen-quality-cases-20261016.json'
PROFILE = ProviderProfile('qwen/qwen3.8-max-0902', 'alibaba/us-east-1', 2.0, 6.0,
                          4096, {'effort': 'low', 'exclude': True})
RUNTIME_FILES = ('assistant.py', 'provider.py', 'retrieval.py', 'contracts.py',
                 'mcp_client.py', 'git_mcp_server.py', 'config.py', 'eval/compare_models.py')


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def load_cases(path=CASES):
    value = json.loads(Path(path).read_text())
    rows = value['cases']
    if len(rows) != 10 or len({c['id'] for c in rows}) != 10 or len({c['question'] for c in rows}) != 10:
        raise ValueError('Нужны ровно 10 различных case ID и вопросов')
    if any(not isinstance(c['question'], str) or not c['question'].strip() for c in rows):
        raise ValueError('Пустой вопрос')
    if any(not re.fullmatch(r'[A-Z][A-Z0-9]{0,15}', c['id']) for c in rows):
        raise ValueError('Case ID должен быть коротким идентификатором без путей')
    return rows


def read_budget(path=SHARED_LEDGER):
    """План никогда не вызывает конструктор ledger и не создаёт базу/резервы."""
    path = Path(path).resolve(strict=True)
    with sqlite3.connect(path.as_uri()+'?mode=ro', uri=True) as db:
        limit, charged = db.execute('SELECT limit_usd,(SELECT coalesce(sum(charged_usd),0) FROM calls) FROM budget WHERE id=1').fetchone()
        count, known, holds = db.execute('SELECT count(*),coalesce(sum(cost_usd),0),coalesce(sum(CASE WHEN cost_usd IS NULL THEN charged_usd ELSE 0 END),0) FROM calls').fetchone()
    return {'ledger_path': str(path), 'limit_usd': limit, 'charged_usd': charged,
            'remaining_usd': limit-charged, 'known_cost_usd': known,
            'unknown_holds_usd': holds, 'entries': count}


def budget_projection(total, budget):
    return {'series_reserve_ceiling_usd': total, 'fits_current_budget': total <= budget['remaining_usd'],
            'additional_limit_needed_usd': max(0.0, total-budget['remaining_usd']),
            'minimum_total_limit_usd': budget['charged_usd']+total}


def runtime_manifest():
    return {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in RUNTIME_FILES}


def runner_fingerprint():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def independent_git(repo):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()
    branch = git('branch', '--show-current')
    return {'root': git('rev-parse', '--show-toplevel'), 'branch': branch or None,
            'detached': not bool(branch), 'head': git('rev-parse', 'HEAD')}


def assemble(cases, index, mcp):
    """Передаём build_request только вопрос/обычный top5/Git, без rubric/gold."""
    records = []
    for case in cases:
        chunks = index.search(case['question'], limit=5)
        git = mcp.read()
        context = {'question': case['question'], 'sources': [c.to_dict() for c in chunks], 'git_context': git}
        request = build_request(PROFILE, SYSTEM, **context) if chunks else None
        records.append({'case_id': case['id'], 'context': context, 'discovery': copy.deepcopy(mcp.last_discovery),
                        'context_sha256': fingerprint(context), 'actual_input': request,
                        'input_sha256': fingerprint(request) if request else None,
                        'request_reserve_usd': request_reserve(PROFILE, request) if request else None,
                        'model_eligible': bool(chunks)})
    return records


def prepare(output, cases):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='day31-qwen-index-') as tmp:
        index = RetrievalIndex(ROOT, Path(tmp)/'index.sqlite3')
        corpus = corpus_manifest(index)
        runtime = runtime_manifest()
        git = independent_git(ROOT.parent)
        records = assemble(cases, index, GitMcpClient(ROOT.parent))
        if corpus_manifest(index) != corpus or runtime_manifest() != runtime or independent_git(ROOT.parent) != git:
            raise ValueError('Корпус/runtime/Git изменились при подготовке')
    for row in records:
        actual_git = row['context']['git_context']
        if any(actual_git[key] != git[key] for key in ('branch', 'detached', 'head')):
            raise ValueError('MCP не совпал с независимой командой Git')
        write(output/(row['case_id']+'-input.json'), row)
    budget = read_budget()
    total = sum(row['request_reserve_usd'] or 0 for row in records)
    projection = budget_projection(total, budget)
    missing = [r['case_id'] for r in records if not r['model_eligible']]
    # AICODE-NOTE: пустой RAG означает пропуск модели в неизменном приложении.
    # Такой кейс нельзя засчитать как один из десяти ответов Qwen или подложить ему источники.
    preflight = check_endpoint(profile=PROFILE)
    summary = {'status': 'blocked_empty_retrieval' if missing else 'plan_ready' if projection['fits_current_budget'] else 'blocked_budget',
               'created_at_utc': datetime.now(timezone.utc).isoformat(), 'execute': False,
               'model_calls_sent': 0, 'case_count': len(cases), 'model_eligible_count': len(cases)-len(missing),
               'empty_retrieval_cases': missing, 'profile': PROFILE.to_dict(), 'preflight': preflight,
               'budget_before': budget, **projection, 'git': git, 'runtime_sha256': runtime,
               'runner_sha256': runner_fingerprint(),
               'corpus_sha256': fingerprint(corpus), 'system_sha256': hashlib.sha256(SYSTEM.encode()).hexdigest(),
               'schema_sha256': fingerprint(ANSWER_SCHEMA), 'cases_sha256': fingerprint(cases),
               'request_inputs_sha256': fingerprint(records),
               'requests': [{'case_id': r['case_id'], 'input_sha256': r['input_sha256'],
                             'request_reserve_usd': r['request_reserve_usd'], 'source_count': len(r['context']['sources'])} for r in records],
               'quality_status': 'NOT_PROVEN: план не является проверкой генерации',
               'semantic_grading': 'Отдельный reviewer читает rubric и ответы; rubric не входит в actual_input.'}
    write(output/'corpus-manifest.json', corpus)
    write(output/'plan.json', summary)
    return summary


def inner_json_check(text):
    """Проверка синтаксиса примера отдельно от внешнего JSON и его смысла."""
    blocks = re.findall(r'```(?:json)?\s*\n(.*?)```', text, re.DOTALL | re.IGNORECASE)
    candidate = blocks[0].strip() if len(blocks) == 1 else None
    if not blocks:
        start = text.find('{')
        if start >= 0:
            try:
                _, end = json.JSONDecoder().raw_decode(text[start:])
                candidate = text[start:start+end]
            except json.JSONDecodeError:
                pass
    if candidate is None:
        return {'status': 'FAIL', 'reason': 'Нет одного распознаваемого JSON-примера'}
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as error:
        return {'status': 'FAIL', 'reason': error.msg, 'position': error.pos}
    shape = isinstance(value, dict) and value.get('type') == 'function' and isinstance(value.get('function'), dict)
    return {'status': 'PASS' if shape else 'FAIL', 'json_loads': 'PASS', 'type_function_shape': shape,
            'semantic_correctness': 'PENDING_REVIEW'}


def checks(case_id, final_json, answer):
    raw_valid = final_json is not None and not list(Draft202012Validator(ANSWER_SCHEMA).iter_errors(final_json))
    result = {'raw_outer_json_schema': 'PASS' if raw_valid else 'FAIL',
              'assistant_schema_and_citation_guards': 'PASS' if answer.status != 'error' else 'FAIL',
              'semantic': 'PENDING_REVIEW'}
    if case_id == 'T3':
        result['inner_json_example'] = inner_json_check(answer.text)
    if case_id == 'Q2':
        result['exact_stdio_call_mentioned'] = bool(re.search(r'\.run\([\"\u0027]stdio[\"\u0027]\)', answer.text))
    if case_id == 'Q5':
        result['unknown_status'] = answer.status == 'unknown'
    return result


def execute(plan_dir, output, cases, *, key, budget_usd):
    """Новые вызовы только по проверенному frozen plan, с прежним per-call reserve."""
    plan_dir = Path(plan_dir).resolve()
    plan = json.loads((plan_dir/'plan.json').read_text())
    if plan['runner_sha256'] != runner_fingerprint():
        raise ValueError('Eval runner изменился после plan')
    if plan['cases_sha256'] != fingerprint(cases) or plan['profile'] != PROFILE.to_dict():
        raise ValueError('Профиль/вопросы изменились после plan')
    if plan['system_sha256'] != hashlib.sha256(SYSTEM.encode()).hexdigest() or plan['schema_sha256'] != fingerprint(ANSWER_SCHEMA) or plan['runtime_sha256'] != runtime_manifest():
        raise ValueError('Runtime/SYSTEM/schema изменились после plan')
    with tempfile.TemporaryDirectory(prefix='day31-qwen-verify-') as tmp:
        index = RetrievalIndex(ROOT, Path(tmp)/'index.sqlite3')
        if plan['corpus_sha256'] != fingerprint(corpus_manifest(index)):
            raise ValueError('Корпус изменился после plan')
        fresh = assemble(cases, index, GitMcpClient(ROOT.parent))
    if fingerprint(fresh) != plan['request_inputs_sha256'] or independent_git(ROOT.parent) != plan['git']:
        raise ValueError('Реальный top5/Git изменились после plan')
    if any(not row['model_eligible'] for row in fresh):
        raise ValueError('Не все 10 вопросов вызывают модель: execute остановлен')
    budget = read_budget()
    if budget_usd != budget['limit_usd']:
        raise ValueError('Явный бюджет должен совпасть с существующим ledger; runner лимит не меняет')
    total = sum(r['request_reserve_usd'] for r in fresh)
    if not budget_projection(total, budget)['fits_current_budget']:
        raise ValueError('Полный резерв 10 запросов не помещается; ни одного вызова не отправлено')
    preflight = check_endpoint(profile=PROFILE)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    ledger = BudgetLedger(SHARED_LEDGER, budget_usd)
    provider = OpenRouterProvider(key, ledger, profile=PROFILE, system=SYSTEM)
    summary = {'status': 'running', 'execute': True, 'profile': PROFILE.to_dict(),
               'preflight': preflight, 'budget_before': budget, 'calls': [],
               'plan_dir': str(plan_dir), 'plan_sha256': fingerprint(plan), 'semantic': 'PENDING_REVIEW'}
    try:
        for row in fresh:
            context = row['context']
            snapshot = ContextSnapshot([SourceChunk(**c) for c in context['sources']], context['git_context'], row['discovery'])
            answer = Assistant(snapshot, snapshot, provider).answer(context['question'])
            call = copy.deepcopy(provider.last_call or {})
            content = call.get('content')
            try:
                final_json = json.loads(content) if isinstance(content, str) else None
            except json.JSONDecodeError:
                final_json = None
            record = {**row, 'answer': answer.to_dict(), 'provider_final': call,
                      'final_json': final_json, 'checks': checks(row['case_id'], final_json, answer)}
            write(output/(row['case_id']+'.json'), record)
            summary['calls'].append({'case_id': row['case_id'], 'trace_id': answer.trace_id,
                                     'status': answer.status, 'sent': call.get('sent', False),
                                     'usage': answer.usage, 'checks': record['checks']})
            write(output/'summary.json', summary)
            if (call.get('error') or {}).get('code') == 'budget_exceeded':
                summary['status'] = 'partial_budget'
                break
        else:
            summary['status'] = 'complete_with_errors' if any(c['status'] == 'error' for c in summary['calls']) else 'complete'
    except Exception:
        summary['status'] = 'interrupted'
        raise
    finally:
        summary['budget_after'] = read_budget()
        write(output/'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Новый каталог результатов')
    parser.add_argument('--execute', action='store_true', help='10 платных запросов; только после отдельного разрешения')
    parser.add_argument('--plan-dir', type=Path, help='Проверенный frozen plan, обязателен для execute')
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--budget-usd', type=float)
    args = parser.parse_args()
    cases = load_cases()
    if args.execute:
        if args.plan_dir is None or args.budget_usd is None:
            parser.error('Для execute нужны --plan-dir и явный --budget-usd существующего ledger')
        key = dotenv_values(args.env_file).get('OPENROUTER_API_KEY') if args.env_file else os.environ.get('OPENROUTER_API_KEY')
        if not key:
            parser.error('OPENROUTER_API_KEY не настроен')
        summary = execute(args.plan_dir, args.output, cases, key=key, budget_usd=args.budget_usd)
    else:
        if args.plan_dir or args.env_file or args.budget_usd is not None:
            parser.error('Plan-only не читает ключ; execute-параметры без --execute запрещены')
        summary = prepare(args.output, cases)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary['status'] in ('plan_ready', 'complete') else 1


if __name__ == '__main__':
    raise SystemExit(main())
