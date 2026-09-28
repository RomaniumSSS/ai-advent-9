"""Узкие лимиты самостоятельного Day 20."""
from __future__ import annotations

import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = Path(os.environ["DAY20_DATA_DIR"]).resolve() if os.environ.get("DAY20_DATA_DIR") else HERE / "data"
DB = DATA / "day20.db"
PROFILE = "habr_ai_agents_ru_v1"
RSS_URL = ("https://habr.com/ru/rss/search/?q=%D0%98%D0%98-%D0%B0%D0%B3%D0%B5%D0%BD%D1%82%D1%8B"
           "&order_by=date&target_type=posts&hl=ru&fl=ru&limit=100")
MODEL_ID = "qwen/qwen3.8-27b"
PROVIDER = "deepinfra"
GITHUB_RELEASE = "v1.12.2"
GITHUB_TOOLS = ("get_file_contents", "get_latest_release", "list_issues")
MAX_FEED_BYTES = 2 * 1024 * 1024
MAX_FEED_ITEMS = 100
MAX_ARTICLE_BYTES = 1024 * 1024
MAX_ARTICLE_CHARS = 36_000
ARTICLE_CHUNK_CHARS = 6_000
MAX_RESULT_BYTES = 36 * 1024
MAX_ARGS_BYTES = 12 * 1024
MAX_PROVIDER_REQUEST_BYTES = 80 * 1024
MAX_MODEL_CALLS = 10
MAX_MCP_CALLS = 8
MAX_OUTPUT_TOKENS = 2400
MAX_COST_USD = 0.25
