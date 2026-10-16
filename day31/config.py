"""Только доверенная стартовая конфигурация, общая для CLI и браузера."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
from dotenv import dotenv_values
from day31.assistant import Assistant
from day31.mcp_client import GitMcpClient
from day31.provider import BudgetLedger, OfflineProvider, OpenRouterProvider, ProviderError, check_endpoint
from day31.retrieval import RetrievalIndex

ROOT = Path(__file__).resolve().parent


def add_arguments(parser: argparse.ArgumentParser):
    parser.add_argument('--repo',type=Path,default=ROOT.parent,help='Git-root фиксируется на старте')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'.runtime',help='Отдельный индекс и ledger этого дня')
    parser.add_argument('--live',action='store_true',help='Один реальный платный вызов на вопрос')
    parser.add_argument('--env-file',type=Path,help='Безопасный файл с OPENROUTER_API_KEY')
    parser.add_argument('--budget-usd',type=float,help='Явно разрешённый общий лимит в USD, обязателен для --live')


def build_assistant(args) -> Assistant:
    if args.live and args.budget_usd is None:
        raise ValueError('Для --live нужен явно разрешённый --budget-usd')
    if not args.live and (args.budget_usd is not None or args.env_file is not None):
        raise ValueError('--budget-usd и --env-file используются только с --live')
    mcp = GitMcpClient(args.repo)
    data_dir = args.data_dir.expanduser().resolve()
    data_dir.mkdir(parents=True,exist_ok=True)
    if args.live:
        key = os.environ.get('OPENROUTER_API_KEY','')
        if args.env_file is not None:
            try:
                key = dotenv_values(args.env_file).get('OPENROUTER_API_KEY') or ''
            except OSError as error:
                raise ValueError('Не удалось прочитать файл окружения') from error
        if not key:
            raise ValueError('OPENROUTER_API_KEY не настроен')
        try:
            preflight = check_endpoint()
        except ProviderError as error:
            raise ValueError(str(error)) from None
        ledger = BudgetLedger(data_dir/'budget.sqlite3',args.budget_usd)
        provider = OpenRouterProvider(key,ledger)
        provider.preflight = preflight
    else:
        provider = OfflineProvider()
    return Assistant(RetrievalIndex(ROOT,data_dir/'index.sqlite3'),mcp,provider)
