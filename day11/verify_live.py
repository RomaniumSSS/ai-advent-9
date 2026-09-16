"""Малый живой прогон: один вопрос до/после записи и в чужой области."""

import argparse
import json
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))

from agent import Agent, AgentConfig  # noqa: E402
from store import SqliteStore  # noqa: E402

DEADLINE = "27 октября 2031 года"
CITY = "Новосибирск"
CODE = "янтарный маяк"
FORMAT = "Показывать итог маркированным списком."
ASK_DEADLINE = "Какой срок у моей текущей задачи? Если он не задан, скажи «не знаю»."
ASK_CITY = "В каком городе я живу? Если данных нет, скажи «не знаю»."
ASK_FORMAT = "Назови срок текущей задачи и город проживания."
ASK_CODE = (
    "Какое кодовое слово сохранено в текущем разговоре? "
    "Если данных нет, скажи «не знаю»."
)


def says_unknown(answer: str) -> bool:
    return "не знаю" in " ".join(answer.lower().replace("ё", "е").split())


def checks_of(evidence: list[dict]) -> dict[str, bool]:
    by_case = {item["case"]: item for item in evidence}
    return {
        "working_absent_before_save": (
            says_unknown(by_case["deadline_before"]["answer"])
            and DEADLINE.lower() not in by_case["deadline_before"]["answer"].lower()
        ),
        "working_changes_answer": "2031" in by_case["deadline_after"]["answer"],
        "working_is_not_other_task": (
            says_unknown(by_case["deadline_other_task"]["answer"])
            and DEADLINE.lower() not in by_case["deadline_other_task"]["answer"].lower()
        ),
        "working_format_changes_answer": (
            "2031" in by_case["format_after"]["answer"]
            and CITY.lower() in by_case["format_after"]["answer"].lower()
            and sum(
                line.lstrip().startswith(("-", "•", "*"))
                for line in by_case["format_after"]["answer"].splitlines()
            ) >= 2
        ),
        "long_survives_new_task": CITY.lower() in by_case["city_new_task"]["answer"].lower(),
        "long_is_not_other_user": (
            says_unknown(by_case["city_other_user"]["answer"])
            and CITY.lower() not in by_case["city_other_user"]["answer"].lower()
        ),
        "short_absent_before_save": (
            says_unknown(by_case["short_before"]["answer"])
            and CODE not in by_case["short_before"]["answer"].lower()
        ),
        "short_changes_answer": CODE in by_case["short_after"]["answer"].lower(),
        "short_is_not_new_session": (
            says_unknown(by_case["short_new_session"]["answer"])
            and CODE not in by_case["short_new_session"]["answer"].lower()
        ),
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--env-file", type=Path, required=True)
    result.add_argument("--out", type=Path)
    return result


def run() -> None:
    args = parser().parse_args()
    if not args.env_file.is_file():
        raise FileNotFoundError(f"нет env-файла {args.env_file}")
    load_dotenv(args.env_file)
    config = AgentConfig(max_tokens=1000, temperature=0)
    evidence = []
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "memory.db"

        def make(session, task, user="roman"):
            return Agent(
                config=config,
                store=SqliteStore(db, session, task, user),
                recent_turns=2,
            )

        landing = make("landing-1", "landing")

        def ask(label, agent, question):
            reply = agent.ask(question)
            evidence.append({
                "case": label,
                "session": agent.store.session,
                "task": agent.store.task_id,
                "user": agent.store.user_id,
                "question": question,
                "answer": reply.text,
                "error": reply.error,
                "finish_reason": reply.finish_reason,
                "empty": reply.empty,
                "saved": reply.saved,
                "provider": reply.served_by,
                "prompt_tokens": reply.prompt_tokens,
                "completion_tokens": reply.completion_tokens,
                "cost_reported": reply.cost_reported,
            })
            print(f"{label}: {reply.text or reply.error or 'пустой ответ'}")
            if not reply.ok or reply.empty or not reply.saved:
                print(reply.debug_line())
                if args.out:
                    args.out.parent.mkdir(parents=True, exist_ok=True)
                    args.out.write_text(
                        json.dumps({"incomplete": True, "calls": evidence},
                                   ensure_ascii=False, indent=2) + "\n"
                    )
                raise RuntimeError(f"живой вызов {label} не завершён и не сохранён")

        ask("deadline_before", landing, ASK_DEADLINE)
        landing.save("working", "срок", DEADLINE)
        ask("deadline_after", landing, ASK_DEADLINE)
        ask("deadline_other_task", make("shop-1", "shop"), ASK_DEADLINE)
        landing.save("long", "город проживания", CITY)
        landing.save("working", "формат ответа", FORMAT)
        ask("format_after", landing, ASK_FORMAT)
        ask("city_new_task", make("shop-2", "shop"), ASK_CITY)
        ask("city_other_user", make("anna-1", "shop", "anna"), ASK_CITY)
        ask("short_before", landing, ASK_CODE)
        landing.save("short", "кодовое слово", CODE)
        ask("short_after", landing, ASK_CODE)
        ask("short_new_session", make("landing-2", "landing"), ASK_CODE)

    checks = checks_of(evidence)
    report = {"checks": checks, "calls": evidence}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(f"Доказательство сохранено: {args.out}")
    print("Проверки:", checks)
    if not all(checks.values()):
        raise SystemExit("живой прогон не подтвердил влияние памяти на все ответы")


if __name__ == "__main__":
    run()
