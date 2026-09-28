"""Закреплённый профиль Qwen/DeepInfra и консервативный preflight."""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass

from .config import (MAX_COST_USD, MAX_MODEL_CALLS, MAX_OUTPUT_TOKENS,
                     MAX_PROVIDER_REQUEST_BYTES, MODEL_ID, PROVIDER)
from .store import now

ENDPOINT_URL = f"https://openrouter.ai/api/v1/models/{MODEL_ID}/endpoints"
REQUIRED = {"tools", "tool_choice", "max_tokens"}


def preflight() -> dict:
    request = urllib.request.Request(ENDPOINT_URL, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=15) as response:
        endpoints = json.load(response)["data"]["endpoints"]
    matching = [item for item in endpoints if item.get("provider_name", "").lower() == PROVIDER
                and item.get("status") == 0]
    if len(matching) != 1:
        raise ValueError("qwen_deepinfra_endpoint_unavailable")
    endpoint = matching[0]
    if (not REQUIRED.issubset(endpoint.get("supported_parameters", []))
            or endpoint.get("supports_tool_choice", {}).get("auto") is not True
            or (endpoint.get("max_completion_tokens") or 0) < MAX_OUTPUT_TOKENS):
        raise ValueError("qwen_deepinfra_parameters_missing")
    pricing = endpoint["pricing"]
    input_price = float(pricing["prompt"])
    output_price = float(pricing["completion"])
    discount = float(pricing.get("discount") or 0)
    if not (0 < input_price < 0.00001 and 0 < output_price < 0.00005 and 0 <= discount < 1):
        raise ValueError("qwen_price_invalid")
    # AICODE-NOTE: скидка может исчезнуть между preflight и вызовом;
    # резерв считаем по большей из текущей и недисконтированной цены.
    safe_input = max(input_price, input_price / (1 - discount))
    safe_output = max(output_price, output_price / (1 - discount))
    upper = MAX_MODEL_CALLS * (MAX_PROVIDER_REQUEST_BYTES * safe_input
                               + MAX_OUTPUT_TOKENS * safe_output) * 1.10
    if upper > MAX_COST_USD:
        raise ValueError("qwen_cost_preflight_exceeds_cap")
    return {"checked_utc": now(), "endpoint_url": ENDPOINT_URL,
            "endpoint": endpoint["name"], "model_id": MODEL_ID,
            "provider": PROVIDER, "input_usd_per_token": input_price,
            "output_usd_per_token": output_price,
            "safe_input_usd_per_token": safe_input,
            "safe_output_usd_per_token": safe_output,
            "max_model_calls": MAX_MODEL_CALLS,
            "max_provider_request_bytes": MAX_PROVIDER_REQUEST_BYTES,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "upper_usd": round(upper, 6), "cap_usd": MAX_COST_USD}


@dataclass(frozen=True)
class ModelResponse:
    message: object
    usage: dict | None
    finish_reason: str | None


class OpenRouterProvider:
    def __init__(self):
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise ValueError("missing_OPENROUTER_API_KEY")
        from openai import OpenAI
        self.client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key,
                             max_retries=0, timeout=180)

    def complete(self, messages: list[dict], *, tools: list[dict]) -> ModelResponse:
        result = self.client.chat.completions.create(
            model=MODEL_ID, messages=messages, tools=tools, tool_choice="auto",
            max_tokens=MAX_OUTPUT_TOKENS,
            extra_body={"provider": {"only": [PROVIDER], "allow_fallbacks": False,
                                     "require_parameters": True}})
        choice = result.choices[0]
        usage = result.usage.model_dump() if result.usage else None
        if usage is not None:
            usage = {key: usage.get(key) for key in
                     ("prompt_tokens", "completion_tokens", "total_tokens", "cost")}
        return ModelResponse(choice.message, usage, choice.finish_reason)


def get(value: object, key: str, default=None):
    return value.get(key, default) if isinstance(value, dict) else getattr(value, key, default)
