"""Фиксированные границы Day 19 и сменный профиль модели."""
from __future__ import annotations
from dataclasses import dataclass

PROFILE = "habr_ai_agents_ru_v1"
RSS_URL = ("https://habr.com/ru/rss/search/?q=%D0%98%D0%98-%D0%B0%D0%B3%D0%B5%D0%BD%D1%82%D1%8B"
           "&order_by=date&target_type=posts&hl=ru&fl=ru&limit=100")
TOOL_NAMES = ("collect_habr_agent_cases", "prepare_report_preview", "save_report")
MAX_FEED_BYTES = 2 * 1024 * 1024
MAX_FEED_ITEMS = 100
MAX_MODEL_SEEN = 20
MAX_DRAFT_BYTES = 18 * 1024
MAX_ARGS_BYTES = 20 * 1024
MAX_RESULT_BYTES = 32 * 1024
MAX_PROVIDER_REQUEST_BYTES = 80 * 1024
MAX_MODEL_CALLS = 6
MAX_MCP_CALLS = 5

@dataclass(frozen=True)
class ModelProfile:
    name: str
    model_id: str
    provider: str
    reasoning_effort: str
    max_tokens: int
    max_cost_usd: float

PROFILES = {"deepseek": ModelProfile("deepseek", "deepseek/deepseek-v4.1-flash",
                                      "deepinfra", "none", 12_000, 0.25)}

def select_profile(name: str) -> ModelProfile:
    if name not in PROFILES:
        raise ValueError("unknown_model_profile")
    return PROFILES[name]
