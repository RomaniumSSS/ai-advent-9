"""Фиксированные границы Day 18; импорт модуля не открывает сеть."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

PROFILE = "habr_ai_agents_ru_v1"
ZONE = "Europe/Warsaw"
RSS_URL = (
    "https://habr.com/ru/rss/search/?q=%D0%98%D0%98-%D0%B0%D0%B3%D0%B5%D0%BD%D1%82%D1%8B"
    "&order_by=date&target_type=posts&hl=ru&fl=ru&limit=100"
)
TOOL_NAME = "collect_habr_agent_cases"
MODEL_ID = "deepseek/deepseek-v4.1-flash"
MAX_FEED_BYTES = 2 * 1024 * 1024
MAX_FEED_ITEMS = 100
MAX_RESULT_BYTES = 32 * 1024
MAX_CANDIDATE_BYTES = 16 * 1024
MAX_DRAFT_BYTES = 18 * 1024
MAX_MODEL_SEEN = 20
MAX_DRAFT_TOKENS = 20_000
MAX_PROVIDER_REQUEST_BYTES = 80_000
MAX_PAYLOAD_CHARS = 3500
MAX_DISPLAYED = 2


@dataclass(frozen=True)
class Settings:
    db_path: Path
    mcp_command: str
    mcp_args: tuple[str, ...]
    model: str
    provider: str = "deepinfra"
    api_key_env: str = "OPENROUTER_API_KEY"
    telegram_token_env: str = "DAY18_TELEGRAM_BOT_TOKEN"
    telegram_chat_env: str = "DAY18_TELEGRAM_CHAT_ID"

    def __post_init__(self) -> None:
        if self.provider != "deepinfra" or not self.model.strip():
            raise ValueError("Не закреплена модель/provider Day 18")
        if not self.mcp_command or not self.mcp_args:
            raise ValueError("Нужен локальный stdio MCP server")

    def recipient(self) -> tuple[str, str, str]:
        """Секреты читаются лишь непосредственно на границе отправки."""
        token = os.environ.get(self.telegram_token_env, "")
        chat_id = os.environ.get(self.telegram_chat_env, "")
        if not token or not chat_id:
            raise ValueError("Не настроен Telegram recipient")
        fingerprint = hashlib.sha256(chat_id.encode()).hexdigest()
        return token, chat_id, fingerprint
