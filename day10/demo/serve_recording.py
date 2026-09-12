"""Панель для записи: 13 реальных ходов из прогона, 14-й вызывается вживую.

Ходы берутся из завершённого живого прогона Sticky Facts, а не выдумываются:
на видео должно быть видно настоящее состояние памяти, а не декорация. Новыми
деньгами оплачивается только последний, контрольный ход и его служебный вызов.

База записи временная, рабочие базы не трогаются.
"""

import argparse
import json
import sys
import tempfile
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

import web  # noqa: E402
from base_agent import Reply  # noqa: E402
from experiment import BudgetLedger, MeasuredClient, real_client  # noqa: E402
from store import SqliteStore  # noqa: E402

DEMO = Path(__file__).resolve().parent
SEEDED_TURNS = 13


def seed(db_path: Path, session: str, report: dict) -> None:
    store = SqliteStore(db_path, session)
    store.remember_config("deepseek-v4-flash", web.DEFAULT_SYSTEM_PROMPT)
    for row in report["rows"][:SEEDED_TURNS]:
        reply = Reply(
            text=row["answer"],
            model="deepseek-v4-flash",
            elapsed=row["elapsed"],
            finish_reason="stop",
            prompt_tokens=row["prompt_tokens"],
            completion_tokens=row["completion_tokens"],
            cost_reported=row["cost_reported"],
        )
        store.append_call(reply, kind="chat")
        store.append_turn(row["question"], reply)
        if row["facts"]:
            store.save_facts(row["facts"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument(
        "--report", type=Path, default=DEMO.parent / "results" / "project-facts.json"
    )
    parser.add_argument("--port", type=int, default=8050)
    # Репетиция хореографии записи без сети и без денег. Сцены те же, отвечает
    # заглушка: проверять порядок кликов на платных вызовах — дорогой способ
    # узнать, что кнопка называется иначе.
    parser.add_argument(
        "--offline",
        action="store_true",
        help="подставная модель: прогнать сценарий записи без трат",
    )
    args = parser.parse_args()
    if not args.offline:
        load_dotenv(args.env_file)

    report = json.loads(args.report.read_text())
    if report["turns"] < SEEDED_TURNS:
        raise SystemExit(f"в отчёте только {report['turns']} ходов")
    (DEMO / "recording-source.json").write_text(
        json.dumps(
            {
                "source_report": str(args.report),
                "seeded_turns": SEEDED_TURNS,
                "live_turn": SEEDED_TURNS + 1,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )

    ledger = None if args.offline else BudgetLedger()
    with tempfile.TemporaryDirectory(prefix="day10-video-") as directory:
        database = Path(directory) / "video.db"
        seed(database, "demo", report)
        web.build_panel(database, "demo", strategy="facts", recent_messages=6)
        if args.offline:
            from run_strategies import OfflineClient

            web.STATE["agent"].client = OfflineClient()
        else:
            web.STATE["agent"].client = MeasuredClient(
                real_client(), ledger, "video", DEMO / "live-calls.json"
            )

        server = ThreadingHTTPServer(("127.0.0.1", args.port), web.Handler)
        print(
            f"панель записи: http://127.0.0.1:{args.port}; "
            f"{SEEDED_TURNS} ходов из {args.report.name}",
            flush=True,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            # Репетиция не должна перезаписывать артефакты настоящей записи:
            # отчёт о деньгах и состояние панели после неё ничего не доказывают.
            if not args.offline:
                (DEMO / "panel-results.json").write_text(
                    json.dumps(web.state(), ensure_ascii=False, indent=2) + "\n"
                )
                (DEMO.parent / "results" / "budget-report.json").write_text(
                    json.dumps(ledger.report(), ensure_ascii=False, indent=2) + "\n"
                )


if __name__ == "__main__":
    main()
