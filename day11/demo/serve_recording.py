"""Временная панель для видео дня 11 на данных живого прогона.

Ответы переносятся из results/live-memory.json в новую SQLite-базу. Сети и
новых расходов нет; рабочая база day11/history.db не читается и не меняется.
"""

import argparse
import json
import sys
import tempfile
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import web  # noqa: E402
from base_agent import AgentConfig, Reply  # noqa: E402
from store import SqliteStore  # noqa: E402

DEMO = Path(__file__).resolve().parent
DEFAULT_REPORT = DEMO.parent / "results" / "live-memory.json"
MODEL = "deepseek-v4-flash"
VISIBLE_CASES = {
    "deadline_before",
    "deadline_after",
    "city_new_task",
    "city_other_user",
    "short_new_session",
}


class PlaybackClient:
    """Один ранее полученный ответ с проверкой фактического нового запроса."""

    def __init__(self, row: dict):
        self.row = row
        self.used = False
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        if self.used:
            raise RuntimeError("сохранённый ответ уже воспроизведён")
        messages = kwargs["messages"]
        joined = "\n".join(message["content"] for message in messages)
        if messages[-1]["content"] != self.row["question"]:
            raise RuntimeError("вопрос записи не совпал с живым прогоном")
        for expected in ("27 октября 2031", "Новосибирск", "маркированным списком"):
            if expected not in joined:
                raise RuntimeError(f"в запрос не попала рабочая память: {expected}")
        self.used = True
        return SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content=self.row["answer"]),
                finish_reason=self.row["finish_reason"],
            )],
            usage=SimpleNamespace(
                prompt_tokens=self.row["prompt_tokens"],
                completion_tokens=self.row["completion_tokens"],
                cost=self.row["cost_reported"],
            ),
            provider=self.row["provider"],
        )


def seed(database: Path, report: dict) -> None:
    for row in report["calls"]:
        if row["case"] not in VISIBLE_CASES:
            continue
        store = SqliteStore(database, row["session"], row["task"], row["user"])
        store.remember_config(MODEL, web.AgentConfig().system_prompt)
        reply = Reply(
            text=row["answer"],
            model=MODEL,
            elapsed=0.0,
            finish_reason=row["finish_reason"],
            prompt_tokens=row["prompt_tokens"],
            completion_tokens=row["completion_tokens"],
            cost_reported=row["cost_reported"],
            served_by=row["provider"],
        )
        store.append_call(reply)
        store.append_turn(row["question"], reply)

    landing = SqliteStore(database, "landing-1", "landing", "roman")
    landing.save_note("short", "кодовое слово", "янтарный маяк")
    landing.save_note("working", "срок", "27 октября 2031 года")
    landing.save_note("long", "город", "Новосибирск")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--port", type=int, default=8042)
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    if not all(report["checks"].values()):
        raise SystemExit("живой прогон содержит невыполненные проверки")

    source_report = (
        "day11/results/live-memory.json"
        if args.report.resolve() == DEFAULT_REPORT.resolve()
        else str(args.report)
    )
    format_call = next(row for row in report["calls"] if row["case"] == "format_after")
    (DEMO / "recording-source.json").write_text(
        json.dumps(
            {
                "source_report": source_report,
                "source_calls": sorted(VISIBLE_CASES),
                "playback_call": "format_after",
                "network_calls_during_recording": 0,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )

    with tempfile.TemporaryDirectory(prefix="day11-video-") as directory:
        database = Path(directory) / "video.db"
        seed(database, report)
        web.STATE.update(
            {
                "db": database,
                "config": AgentConfig(),
                "recent_turns": 6,
            }
        )
        web.STATE["agent"] = web.make_agent("landing-1", "landing", "roman")
        web.STATE["agent"].client = PlaybackClient(format_call)
        server = ThreadingHTTPServer(("127.0.0.1", args.port), web.Handler)
        print(
            f"панель записи: http://127.0.0.1:{args.port}; "
            "ответы из live-memory.json, сеть не используется",
            flush=True,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
