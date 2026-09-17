"""Офлайн-проверки live campaign; сеть заменена test double."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from live_cases import cases
from live_eval import Campaign, CampaignStop


class FakeSender:
    def __init__(self, *, fail_at: int | None = None, forbidden_state_at: int | None = None):
        self.calls = 0
        self.fail_at = fail_at
        self.forbidden_state_at = forbidden_state_at

    def __call__(self, **request):
        self.calls += 1
        assert request["extra_body"]["reasoning"] == {"effort": "none"}
        if self.calls == self.fail_at:
            raise RuntimeError("synthetic provider failure")
        block = next(
            item["content"] for item in request["messages"]
            if item["role"] == "system" and item["content"].startswith("СОСТОЯНИЕ ТЕКУЩЕЙ ЗАДАЧИ")
        )
        state = json.loads(block.splitlines()[2])
        payload = {"answer": "Продолжаю по сохранённому состоянию."}
        if self.calls == self.forbidden_state_at:
            payload["decision"] = "terminal"
        answer = json.dumps(payload, ensure_ascii=False)
        return SimpleNamespace(
            id=f"fake-{self.calls}",
            model="deepseek/deepseek-v4-flash-0731",
            provider="OpenInference",
            choices=[SimpleNamespace(
                message=SimpleNamespace(content=answer),
                finish_reason="stop",
            )],
            usage=SimpleNamespace(
                prompt_tokens=300,
                completion_tokens=60,
                total_tokens=360,
                cost=0.00001,
            ),
        )


def campaign(directory: Path, sender: FakeSender) -> Campaign:
    return Campaign(
        directory / "out",
        Path(__file__).parent / "live_policy.json",
        directory / "campaign.db",
        sender=sender,
    )


def test_manifest() -> None:
    manifest = cases()
    assert len(manifest) == 68
    assert len({item["id"] for item in manifest}) == 68
    assert sum(not item["paused"] and not item["terminal_guard"] for item in manifest) == 60
    assert sum(item["paused"] for item in manifest) == 4
    assert sum(item["terminal_guard"] for item in manifest) == 4
    assert sum(item["restart"] and not item["paused"] and not item["terminal_guard"] for item in manifest) == 12


def test_complete_campaign(directory: Path) -> None:
    sender = FakeSender()
    run = campaign(directory, sender)
    report = run.run()
    assert report["passed"]
    assert report["sent"] == sender.calls == 60
    assert report["counts"]["pass"] == 60
    assert report["counts"]["paused_pass"] == 4
    assert report["counts"]["terminal_pass"] == 4
    assert report["restart_live_cases"] == 12
    assert report["quality_pass_rate"] == 1.0
    done = run.ledger.read()["cases"]["T401"]
    assert done["model_calls"] == 0
    assert done["answer"]["observed_stage"] == "done"
    assert done["answer"]["observed_action"] is None
    assert done["answer"]["objective"] == run.case("T401")["objective"]
    assert done["answer"]["decision"] == "terminal"
    assert done["critical"]["no_send"]
    before = run.ledger.read()
    run.dispatch("B101")
    after = run.ledger.read()
    assert before == after, "terminal case нельзя отправлять повторно"


def test_provider_failure_stops_without_retry(directory: Path) -> None:
    sender = FakeSender(fail_at=2)
    run = campaign(directory, sender)
    run.dispatch("B101")
    state = run.dispatch("B102")
    assert sender.calls == 2
    assert state["stopped"]
    assert state["cases"]["B102"]["status"] == "indeterminate"
    run.dispatch("B103")
    assert sender.calls == 2


def test_model_cannot_supply_state_or_decision(directory: Path) -> None:
    sender = FakeSender(forbidden_state_at=1)
    run = campaign(directory, sender)
    state = run.dispatch("B101")
    entry = state["cases"]["B101"]
    assert entry["status"] == "quality_fail"
    assert entry["predicates"]["json_shape"] is False
    assert entry["answer"] is None
    assert state["stopped"] is None
    assert sender.calls == 1


def test_tamper_is_detected(directory: Path) -> None:
    sender = FakeSender()
    run = campaign(directory, sender)
    run.dispatch("B101")
    raw = json.loads(run.ledger.path.read_text(encoding="utf-8"))
    raw["cases"]["B101"]["answer_text"] = "подмена"
    run.ledger.path.write_text(json.dumps(raw), encoding="utf-8")
    # answer_text не является отдельным hash-bound объектом, но cases_hash в
    # последнем checkpoint обязан заметить любую такую подмену.
    try:
        run.ledger.read()
    except CampaignStop as error:
        assert "checkpoint" in str(error)
    else:
        raise AssertionError("подмена ledger не обнаружена")


def main() -> None:
    test_manifest()
    with tempfile.TemporaryDirectory() as root:
        test_complete_campaign(Path(root))
    with tempfile.TemporaryDirectory() as root:
        test_provider_failure_stops_without_retry(Path(root))
    with tempfile.TemporaryDirectory() as root:
        test_model_cannot_supply_state_or_decision(Path(root))
    with tempfile.TemporaryDirectory() as root:
        test_tamper_is_detected(Path(root))
    print("ok  68 situations: 60 live paths, 4 paused guards, 4 done guards, 12 restarts")
    print("ok  durable ledger blocks retries after provider uncertainty")
    print("ok  model-supplied state/decision is rejected; canonical state stays app-owned")
    print("ok  checkpoint chain detects evidence tampering")


if __name__ == "__main__":
    main()
