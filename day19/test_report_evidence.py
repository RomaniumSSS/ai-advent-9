"""Кейсы из live RSS: связь применения с агентом и осторожность с цифрами."""
from __future__ import annotations

import unittest

from .report import ValidationIssue, validate

RUN = "00000000-0000-4000-8000-000000000019"
OBS = "00000000-0000-4000-8000-000000000020"


def check(title: str, excerpt: str, *, category: str = "confirmed_described_case",
          summary: str = "Агент выполнил задачу.", metrics: list | None = None) -> None:
    draft = {"run_id": RUN, "outcome": "cases_found" if category == "confirmed_described_case"
             else "no_confirmed_cases", "coverage_label": "partial", "proposed_text": "Проверка RSS.",
             "entries": [{"observation_id": OBS, "category": category,
                          "evidence_refs": ["title", "rss_excerpt"], "summary": summary,
                          "metric_claims": metrics or []}]}
    row = {"id": OBS, "title": title, "rss_excerpt": excerpt}
    validate(draft, RUN, [row], {"kind": "partial"}, 1)


class ReportEvidence(unittest.TestCase):
    def test_actual_agent_work_is_confirmed(self):
        examples = [
            ("DBA Agent: поддержка", "Собрали автономный агент, который сам обрабатывает тикеты."),
            ("ИИ-агент снимает кино", "В этом фильме код написал ИИ-агент."),
            ("ИИ-агент на боевом B2B-портале: что он нашёл", "Агент разобрал поломки заказов."),
            ("Компания пишет код", "В компании код на сто процентов пишут ИИ-агенты."),
            ("Пет-проект", "Я решил испробовать программирование с помощью ИИ-агентов."),
            ("Компания запустила агента", "Агента запустили на 800 тестовых БД."),
        ]
        for title, excerpt in examples:
            with self.subTest(title=title):
                check(title, excerpt)

    def test_tool_for_agents_does_not_prove_agent_use(self):
        examples = [
            ("ИИ-агенты в инвестициях", "Мы запустили MCP-сервер для клиентов, позволяющий AI-агентам искать бумаги."),
            ("Личный платный API для ИИ-агентов", "Собрал API, довёл до продакшена; агент получает HTTP 402."),
            ("Сервер для ИИ-агента", "Я собрал Linux MCP daemon вместо выдачи агенту SSH."),
        ]
        for title, excerpt in examples:
            with self.subTest(title=title):
                with self.assertRaisesRegex(ValidationIssue, "confirmed_lacks_usage_evidence"):
                    check(title, excerpt)
                check(title, excerpt, category="possible_case")

    def test_headline_only_number_cannot_be_reported_as_result(self):
        title = "Агент в поддержке: 99,6% автоматизации"
        excerpt = "Команда запустила агента для поддержки клиентов в тестовой среде."
        with self.assertRaisesRegex(ValidationIssue, "summary_number_not_in_excerpt"):
            check(title, excerpt, summary="Агент закрыл 99,6% заявок.")
        with self.assertRaisesRegex(ValidationIssue, "unsupported_metric"):
            check(title, excerpt, metrics=[{"text": "99,6%", "attribution": "автор"}])
        with self.assertRaisesRegex(ValidationIssue, "unsupported_metric"):
            check(title, excerpt, metrics=[{"text": "агент для поддержки клиентов", "attribution": "автор"}])

    def test_possible_case_does_not_claim_full_article_lacks_evidence(self):
        title = "Личный платный API для ИИ-агентов"
        excerpt = "Автор собрал API и довёл до продакшена."
        with self.assertRaisesRegex(ValidationIssue, "unscoped_absence_claim"):
            check(title, excerpt, category="possible_case",
                  summary="Применение самого агента не описано.")
        check(title, excerpt, category="possible_case",
              summary="Автор довёл API для агентов до продакшена.")

    def test_ordinal_equivalent_is_not_a_new_metric(self):
        check("DBA-агент в поддержке",
              "Агент обрабатывает тикеты; его перевели в режим второй линии поддержки.",
              summary="Агент обрабатывает тикеты во 2-й линии поддержки.")


if __name__ == "__main__":
    unittest.main()
