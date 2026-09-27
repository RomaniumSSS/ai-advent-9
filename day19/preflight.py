"""Текущая цена и возможности закреплённого endpoint до платного вызова."""
from __future__ import annotations
import json
import urllib.request
from .config import MAX_MODEL_CALLS, MAX_PROVIDER_REQUEST_BYTES, ModelProfile
from .store import now

ENDPOINT_URL = "https://openrouter.ai/api/v1/models/deepseek/deepseek-v4.1-flash/endpoints"
REQUIRED = {"tools","tool_choice","reasoning","max_tokens"}

def check(profile: ModelProfile) -> dict:
    if profile.name != "deepseek" or profile.provider != "deepinfra":
        raise ValueError("unsupported_live_profile")
    with urllib.request.urlopen(ENDPOINT_URL,timeout=15) as response:
        endpoints = json.load(response)["data"]["endpoints"]
    choices = [e for e in endpoints if e.get("provider_name") == "DeepInfra"]
    if len(choices) != 1:
        raise ValueError("deepinfra_endpoint_unavailable")
    endpoint = choices[0]
    if not REQUIRED.issubset(endpoint.get("supported_parameters",[])):
        raise ValueError("deepinfra_parameters_missing")
    input_price = float(endpoint["pricing"]["prompt"])
    output_price = float(endpoint["pricing"]["completion"])
    if not (0 < input_price <= 0.000001 and 0 < output_price <= 0.000003):
        raise ValueError("price_outside_guardrail")
    # AICODE-NOTE: один UTF-8 byte на token завышает оценку prompt; берём
    # максимум текущей цены и недисконтированного тарифа DeepInfra.
    conservative_input = max(input_price,0.20/1_000_000)
    conservative_output = max(output_price,0.60/1_000_000)
    estimate = MAX_MODEL_CALLS * (MAX_PROVIDER_REQUEST_BYTES * conservative_input
                                  + profile.max_tokens * conservative_output) * 1.10
    if estimate > profile.max_cost_usd:
        raise ValueError("cost_preflight_exceeds_cap")
    return {"checked_utc":now(),"endpoint_url":ENDPOINT_URL,"endpoint":endpoint["name"],
            "input_usd_per_token":input_price,"output_usd_per_token":output_price,
            "max_model_calls":MAX_MODEL_CALLS,"max_request_bytes":MAX_PROVIDER_REQUEST_BYTES,
            "max_completion_tokens_per_call":profile.max_tokens,
            "conservative_upper_usd":round(estimate,6),"hard_cap_usd":profile.max_cost_usd,
            "source_parameters":sorted(REQUIRED)}
