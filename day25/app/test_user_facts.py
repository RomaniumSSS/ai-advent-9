"""N2 literal user attribution: positive/negative full Service and saved failure."""

import copy
import json
from pathlib import Path
import unittest
import shutil
import subprocess
from common import MODEL, save
from conversation import build_context
from service import Service
from user_facts import user_fact_catalog, check_user_response, USER_FACT_BYTES
from common import packed
import test_context as fixture


class UserFactTest(unittest.TestCase):
    def test_ui_accepts_v4_and_uses_literal_text_for_user_records(self):
        if not shutil.which("node"):
            self.skipTest("Node unavailable")
        script = (Path(__file__).parent / "app.js").read_text()
        renderer = script[
            script.index("function renderStructured(") : script.index(
                "\nfunction render(item)"
            )
        ]
        prefix = """
const assert=require('node:assert/strict');
function node(tag,text,cls){return {tag,textContent:text,children:[],append(...xs){this.children.push(...xs)}};}
function details(parent,title){const n=node('details',title);parent.append(n);return n;}
function texts(n){return [n.textContent,...n.children.flatMap(texts)].filter(x=>x!==undefined)};
"""
        checks = """
let out=node('article');const statement='<img src=x onerror=alert(1)>';
renderStructured(out,{version:'day25-chat-v4',status:'verified',answer:{answer:'Факт'},structured_evidence:{user_facts:[{statement,version:2,origin:'explicit_task_state'}]}});
assert(texts(out).includes('Подтверждённые пользовательские записи'));assert(texts(out).includes(statement));
assert(!texts(out).some(x=>x.includes('предыдущего контракта')));
out=node('article');renderStructured(out,{version:'day25-chat-v3',status:'verified',answer:{answer:'Старый ответ'},structured_evidence:{}});
assert(texts(out).some(x=>x.includes('Исторический v3')));
out=node('article');renderStructured(out,{version:'day25-chat-v4',status:'unverified',structured_evidence:{user_facts:[{statement,version:2}]}});
assert(!texts(out).includes(statement));
"""
        subprocess.run(
            ["node"],
            input=prefix + renderer + checks,
            text=True,
            check=True,
            capture_output=True,
        )

    def test_catalog_never_promotes_question_assistant_or_old_version(self):
        state = {"version": 2, "goal": "RAG", "clarifications": [], "constraints": []}
        history = [
            {
                "role": "assistant",
                "content": "Мы выбрали SQLite.",
                "request_id": "assistant",
                "task_state_version": 2,
            },
            {
                "role": "user",
                "content": "Я выбрал JSON.",
                "request_id": "old",
                "task_state_version": 1,
            },
            {
                "role": "user",
                "content": "Я выбрал SQLite?",
                "request_id": "question",
                "task_state_version": 2,
            },
            {
                "role": "user",
                "content": "Если я выбрал SQLite, что дальше?",
                "request_id": "if",
                "task_state_version": 2,
            },
        ]
        facts = user_fact_catalog(state, history, "Что мы сами выбрали для показа?")
        self.assertEqual([f["fact_id"] for f in facts], ["state.goal.0"])
        facts = user_fact_catalog(state, history, "Я выбрал SQLite. Что дальше?")
        self.assertEqual(facts[-1]["statement"], "Я выбрал SQLite.")
        self.assertEqual(facts[-1]["origin"], "explicit_user_statement")
        many = dict(
            state,
            clarifications=["факт " + str(i) for i in range(50)],
            constraints=["правило " + str(i) for i in range(50)],
        )
        self.assertLessEqual(
            len(packed(user_fact_catalog(many, [], "Вопрос"))), USER_FACT_BYTES
        )

    def test_declaration_detected_mid_sentence_and_question_is_not_promoted(self):
        state = {"version": 2, "goal": "RAG", "clarifications": [], "constraints": []}
        history = [
            {
                "role": "user",
                "content": "Для напоминалки я выбираю SQLite вместо JSON.",
                "request_id": "mid",
                "task_state_version": 2,
            }
        ]
        facts = user_fact_catalog(state, history, "А что мы выбрали?")
        statements = [
            f["statement"] for f in facts if f["origin"] == "explicit_user_statement"
        ]
        self.assertEqual(statements, ["Для напоминалки я выбираю SQLite вместо JSON."])

    def test_saved_all14_rejected_without_mutating_old_archive(self):
        path = (
            Path(__file__).parents[1]
            / "private/session15-live-01/all-run/rag15-14.json"
        )
        if not path.exists():
            self.skipTest("private evidence unavailable")
        before = path.read_bytes()
        old = json.loads(before)
        ctx = build_context(old["question"], old["task_state"], [], "all")
        checked = check_user_response(
            old["raw_answer"],
            old["generation"]["transmitted_chunks"],
            old["question"],
            old["task_state"],
            ctx,
        )
        self.assertEqual(checked["outcome"], "unverified")
        self.assertIn("unsupported_user_attribution", checked["errors"])
        self.assertEqual(path.read_bytes(), before)
        shown = Service.present(old)
        self.assertEqual(shown["status"], old["status"])
        self.assertEqual(shown["answer"], old["answer"])


class UserFactServiceTest(unittest.TestCase):
    setUp = fixture.ContextTest.setUp
    tearDown = fixture.ContextTest.tearDown

    def generate(self, data):
        def run(body, key):
            self.generate_calls.append(copy.deepcopy(body))
            return {
                "model": MODEL,
                "provider": "DeepInfra",
                "usage": {"cost": 0.00001},
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps(data, ensure_ascii=False)},
                    }
                ],
            }

        self.service.generate_fn = run

    def data(self, answer="Факт о RAG."):
        return {
            "answer": answer,
            "sources": [{"source": "assignment", "chunk_id": "c1"}],
            "quotes": [{"chunk_id": "c1", "text": fixture.CHUNK["text"]}],
        }

    def test_unconfirmed_choice_cannot_be_success_even_with_corpus_and_assistant(self):
        self.generate(self.data("Мы сами выбрали беглую демонстрацию."))
        item = self.service.ask(
            self.a, "false-choice", "Что мы сами выбрали для показа?", "public"
        )
        self.assertEqual(item["status"], "unverified")
        self.assertIn("unsupported_user_attribution", item["validation"]["errors"])
        self.assertNotIn("answer", item)
        item.update(
            stage="validating",
            status="verified",
            answer=item["validation"]["answer"],
            structured_evidence={},
        )
        with self.assertRaisesRegex(ValueError, "verified_invariant_failed"):
            self.service.advance(item, self.service.path("false-choice"), "terminal")
        self.generate(self.data("Если вы уже выбрали SQLite, можно проверить поиск."))
        conditional = self.service.ask(self.a, "conditional", "Что делать?", "public")
        self.assertEqual(conditional["status"], "verified")
        self.generate(self.data("Вы хотите полностью отказаться от RAG."))
        self.assertEqual(
            self.service.ask(self.a, "invented-goal", "Что делать?", "public")[
                "status"
            ],
            "unverified",
        )
        refusal = {
            "answer": "Не знаю: уточни, какой вариант вы выбрали.",
            "sources": [],
            "quotes": [],
        }
        self.generate(refusal)
        self.assertEqual(
            self.service.ask(self.a, "ask-choice", "Что дальше?", "public")["status"],
            "model_refusal",
        )
        refusal["answer"] = "Не знаю: мы сами выбрали SQLite."
        self.generate(refusal)
        self.assertEqual(
            self.service.ask(self.a, "false-refusal", "Что дальше?", "public")[
                "status"
            ],
            "unverified",
        )

    def test_clause_guard_does_not_accept_uncertain_consequence_or_extended_choice(
        self,
    ):
        self.generate(
            self.data("Вы выбрали PostgreSQL, поэтому может понадобиться настройка.")
        )
        item = self.service.ask(self.a, "uncertain-consequence", "Подробнее", "public")
        self.assertEqual(item["status"], "unverified")
        self.assertIn("unsupported_user_attribution", item["validation"]["errors"])
        self.generate(self.data("Если вы выбрали SQLite, мы выбрали PostgreSQL."))
        self.assertEqual(
            self.service.ask(self.a, "second-clause", "Подробнее", "public")["status"],
            "unverified",
        )
        self.service.update_task_state(
            self.a,
            {"goal": "RAG", "clarifications": ["Мы выбрали SQLite"], "constraints": []},
            0,
        )
        # Изменение 3 (вариант A): токены предложения покрывают linked-факт лишь частично
        # (добавленный PostgreSQL), а linked непуст, поэтому атрибуция теперь мягкая —
        # ответ показывается, но помечен, а не прячется как unverified.
        data = self.data("Мы выбрали SQLite и PostgreSQL.")
        data["user_fact_refs"] = [{"fact_id": "state.clarifications.0", "version": 1}]
        self.generate(data)
        item = self.service.ask(self.a, "extended-choice", "Подробнее", "public")
        self.assertEqual(item["status"], "verified")
        self.assertIn(
            "unsupported_user_attribution",
            item["validation"]["user_facts_validation"]["soft_errors"],
        )
        self.assertEqual(
            item["structured_evidence"]["attribution_notice"],
            "ссылка на выбор пользователя не доказана",
        )
        data["answer"] = "Мы выбрали SQLite."
        self.generate(data)
        self.assertEqual(
            self.service.ask(self.a, "whole-choice", "Подробнее", "public")["status"],
            "verified",
        )

    def test_confirmed_choice_typed_reference_prompt_restart_and_tamper(self):
        self.service.update_task_state(
            self.a,
            {
                "goal": "RAG",
                "clarifications": ["Для примера выбрано SQLite"],
                "constraints": [],
            },
            0,
        )
        data = self.data("Для примера выбрано SQLite. Проверим поиск.")
        data["user_fact_refs"] = [{"fact_id": "state.clarifications.0", "version": 1}]
        self.generate(data)
        item = self.service.ask(
            self.a, "choice", "Подробнее для нашей текущей цели", "public"
        )
        self.assertEqual(item["status"], "verified")
        self.assertEqual(item["version"], "day25-chat-v4")
        self.assertEqual(
            item["structured_evidence"]["user_facts"][0]["statement"],
            "Для примера выбрано SQLite",
        )
        envelope = json.loads(self.generate_calls[-1]["messages"][1]["content"])
        self.assertIn("user_fact_contract", envelope)
        self.assertIn(
            "user_fact_refs", envelope["evidence_contract"]["response_fields"]
        )
        self.assertIn(
            "user_fact_contract", self.generate_calls[-1]["messages"][0]["content"]
        )
        self.assertEqual(
            envelope["user_fact_contract"]["allowed_facts"],
            item["conversation"]["user_facts"],
        )
        restarted = Service(
            self.root,
            search_fn=lambda *_: self.fail("search repeated"),
            generate_fn=lambda *_: self.fail("provider repeated"),
        )
        self.assertEqual(restarted.get(self.a, "choice")["status"], "verified")
        changed = copy.deepcopy(item)
        changed["raw_answer"] = json.dumps(
            dict(
                data,
                user_fact_refs=[{"fact_id": "state.clarifications.0", "version": True}],
            )
        )
        save(self.service.path("choice"), changed)
        self.assertEqual(restarted.get(self.a, "choice")["status"], "unverified")

    def test_ordinary_answer_needs_no_choice_and_bounded_state_is_supported(self):
        self.service.update_task_state(
            self.a,
            {"goal": "RAG " + ("x" * 2000), "clarifications": [], "constraints": []},
            0,
        )
        self.generate(self.data())
        item = self.service.ask(self.a, "ordinary", "Что такое RAG?", "public")
        self.assertEqual(item["status"], "verified")
        self.assertTrue(item["conversation"]["task_state_truncated"])
        self.assertEqual(item["structured_evidence"]["user_facts"], [])
        self.assertEqual(item["validation"]["user_facts_validation"]["errors"], [])

    def test_wrong_reference_no_corpus_and_cancelled_choice_are_blocked(self):
        self.service.update_task_state(
            self.a, {"goal": "RAG", "clarifications": ["SQLite"], "constraints": []}, 0
        )
        for index, ref in enumerate(
            (
                {"fact_id": "document.choice", "version": 1},
                {"fact_id": "state.clarifications.0", "version": 0},
                {"fact_id": "state.clarifications.0", "version": "1"},
            )
        ):
            data = self.data()
            data["user_fact_refs"] = [ref]
            self.generate(data)
            item = self.service.ask(self.a, "wrong" + str(index), "Подробнее", "public")
            self.assertEqual(item["status"], "unverified")
        data = self.data()
        data.update(
            sources=[],
            quotes=[],
            user_fact_refs=[{"fact_id": "state.clarifications.0", "version": 1}],
        )
        self.generate(data)
        self.assertEqual(
            self.service.ask(self.a, "no-corpus", "Подробнее", "public")["status"],
            "unverified",
        )
        self.service.clear_task_state(self.a, 1)
        data = self.data()
        data["user_fact_refs"] = [{"fact_id": "state.clarifications.0", "version": 1}]
        self.generate(data)
        item = self.service.ask(self.a, "cancelled", "Подробнее", "public")
        self.assertEqual(item["status"], "unverified")
        self.assertNotIn("SQLite", json.dumps(item["conversation"]["user_facts"]))

    def test_natural_paraphrase_with_correct_linked_ref_passes(self):
        self.service.update_task_state(
            self.a,
            {
                "goal": "RAG",
                "clarifications": ["Я выбрал SQLite для хранения заметок."],
                "constraints": [],
            },
            0,
        )
        data = self.data("Это выбранный тобой вариант хранения заметок — SQLite.")
        data["user_fact_refs"] = [{"fact_id": "state.clarifications.0", "version": 1}]
        self.generate(data)
        item = self.service.ask(self.a, "paraphrase-linked", "Подробнее", "public")
        self.assertEqual(item["status"], "verified")

    def test_attribution_without_linked_ref_fails(self):
        self.service.update_task_state(
            self.a,
            {
                "goal": "RAG",
                "clarifications": ["Я выбрал SQLite для хранения заметок."],
                "constraints": [],
            },
            0,
        )
        self.generate(
            self.data("Это выбранный тобой вариант хранения заметок — SQLite.")
        )
        item = self.service.ask(self.a, "paraphrase-unlinked", "Подробнее", "public")
        self.assertEqual(item["status"], "unverified")
        self.assertIn("user_fact_not_linked", item["validation"]["errors"])

    def test_attribution_with_ref_to_unrelated_fact_is_soft_and_survives_recheck(self):
        # Изменение 3 (вариант A): linked непуст (ссылка валидна, хоть и не про это
        # предложение) — unsupported_user_attribution мягчает, ответ не прячется.
        # Проверяем и инвариант пересчёта: Service.present должен воспроизвести ту же
        # пометку детерминированно, а не уронить ответ в verified_invariant_failed.
        self.service.update_task_state(
            self.a,
            {
                "goal": "RAG",
                "clarifications": ["Не добавляй рекламу."],
                "constraints": [],
            },
            0,
        )
        data = self.data("Это выбранный тобой вариант хранения заметок — SQLite.")
        data["user_fact_refs"] = [{"fact_id": "state.clarifications.0", "version": 1}]
        self.generate(data)
        item = self.service.ask(
            self.a, "paraphrase-unrelated-ref", "Подробнее", "public"
        )
        self.assertEqual(item["status"], "verified")
        self.assertIn(
            "unsupported_user_attribution",
            item["validation"]["user_facts_validation"]["soft_errors"],
        )
        self.assertEqual(
            item["structured_evidence"]["attribution_notice"],
            "ссылка на выбор пользователя не доказана",
        )
        shown = Service.present(item)
        self.assertEqual(shown["status"], "verified")
        self.assertEqual(
            shown["structured_evidence"]["attribution_notice"],
            "ссылка на выбор пользователя не доказана",
        )
        # item уже прошёл advance(...,'terminal') внутри ask() — там же срабатывает
        # verified_invariant_failed при несовпадении пересчёта; status='verified' значит,
        # что пометка воспроизвелась детерминированно уже на этом шаге.
        restarted = Service(
            self.root,
            search_fn=lambda *_: self.fail("search repeated"),
            generate_fn=lambda *_: self.fail("provider repeated"),
        )
        reread = restarted.get(self.a, "paraphrase-unrelated-ref")
        self.assertEqual(reread["status"], "verified")
        self.assertEqual(
            reread["structured_evidence"]["attribution_notice"],
            "ссылка на выбор пользователя не доказана",
        )

    def test_refusal_with_user_fact_refs_is_model_refusal_not_unverified(self):
        self.service.update_task_state(
            self.a,
            {
                "goal": "RAG",
                "clarifications": ["Я выбрал SQLite для хранения заметок."],
                "constraints": [],
            },
            0,
        )
        refusal = {
            "answer": "Не знаю: уточни, какой вариант вы выбрали.",
            "sources": [],
            "quotes": [],
            "user_fact_refs": [{"fact_id": "state.clarifications.0", "version": 1}],
        }
        self.generate(refusal)
        item = self.service.ask(self.a, "refusal-with-ref", "Что дальше?", "public")
        self.assertEqual(item["status"], "model_refusal")


if __name__ == "__main__":
    unittest.main()
