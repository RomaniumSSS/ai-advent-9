"""Быстрые проверки самостоятельной и узкой архитектуры."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from jsonschema import Draft202012Validator

from day18.agent import OpenRouterProvider
from day18.config import MODEL_ID, PROFILE, RSS_URL, Settings, TOOL_NAME
from day18.report import DRAFT_SCHEMA, PROVIDER_DRAFT_SCHEMA


class ArchitectureTests(unittest.TestCase):
    def test_day18_isolation(self) -> None:
        root = Path(__file__).parent
        for path in root.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertTrue(all(not alias.name.startswith("day17") for alias in node.names))
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse((node.module or "").startswith("day17"))

    def test_fixed_config(self) -> None:
        self.assertEqual(TOOL_NAME, "collect_habr_agent_cases")
        self.assertEqual(MODEL_ID, "deepseek/deepseek-v4.1-flash")
        with self.assertRaises(ValueError):
            OpenRouterProvider("unpriced/model")
        self.assertEqual(PROFILE, "habr_ai_agents_ru_v1")
        self.assertTrue(RSS_URL.startswith("https://habr.com/ru/rss/search/?"))
        settings = Settings(Path(":memory:"), "python3", ("-m", "day18.rss_mcp_server"), "fixed-model")
        self.assertEqual(settings.provider, "deepinfra")

    def test_v41_provider_route_and_non_thinking(self) -> None:
        provider = object.__new__(OpenRouterProvider)
        provider.model = MODEL_ID
        message = {"content": "{}"}
        create = Mock(return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=message, finish_reason="stop")], usage=None))
        provider.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        provider.complete([{"role": "user", "content": "test"}], tools=[], max_tokens=8192,
                          tool_choice="none")
        request = create.call_args.kwargs
        self.assertEqual(request["model"], MODEL_ID)
        self.assertEqual(request["extra_body"]["reasoning"], {"effort": "none"})
        self.assertEqual(request["extra_body"]["provider"],
                         {"only": ["deepinfra"], "allow_fallbacks": False, "require_parameters": True})
        response_format = request["response_format"]
        self.assertEqual(response_format["type"], "json_schema")
        self.assertTrue(response_format["json_schema"]["strict"])
        self.assertEqual(request["temperature"], 0)
        self.assertEqual(response_format["json_schema"]["schema"], PROVIDER_DRAFT_SCHEMA)
        Draft202012Validator.check_schema(PROVIDER_DRAFT_SCHEMA)
        self.assertNotIn("$schema", PROVIDER_DRAFT_SCHEMA)
        self.assertIn("format", DRAFT_SCHEMA["properties"]["run_id"])
        self.assertNotIn("format", PROVIDER_DRAFT_SCHEMA["properties"]["run_id"])
        self.assertEqual(PROVIDER_DRAFT_SCHEMA["properties"]["entries"]["items"]
                         ["properties"]["summary"]["maxLength"], 90)
        metric = PROVIDER_DRAFT_SCHEMA["properties"]["entries"]["items"]["properties"]
        self.assertEqual(metric["metric_claims"]["items"]["properties"]["text"]["maxLength"], 65)
        self.assertEqual(metric["metric_claims"]["items"]["properties"]["attribution"]["maxLength"], 45)

        create.reset_mock()
        provider.complete([{"role": "user", "content": "test"}], tools=[{"type": "function"}],
                          max_tokens=1000, tool_choice="auto")
        self.assertNotIn("response_format", create.call_args.kwargs)
        self.assertNotIn("temperature", create.call_args.kwargs)
        self.assertEqual(create.call_args.kwargs["tool_choice"], "auto")
