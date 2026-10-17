"""Явный сценарный mock только для офлайн-проверок интерфейса и инструментов."""
import json

UPDATED = '''# Invite demo

API: `send_invite(email, *, role="member", dry_run=False)`.
Email должен содержать @. Роли: member и admin; иначе ValueError.
Результат: email, role, sent. При dry_run=True письмо не отправляется (sent=False).
service.onboard вызывает API с role="member", dry_run=False.

CLI: `python -m src.cli alice@example.com --role admin --dry-run`.
Email — обязательный позиционный аргумент; --role по умолчанию member;
--dry-run отключён по умолчанию. CLI печатает словарь результата.
'''


class MockModel:
    name = "SCRIPTED-MOCK (не модель)"
    provider = "offline"

    def __init__(self):
        self.step = 0

    def complete(self, messages, tools, **kwargs):
        self.step += 1
        update = "README" in messages[1]["content"]
        if self.step == 1:
            actions = [("list_files", {}), ("search_text", {"query": "send_invite"})]
        elif self.step == 2:
            actions = [("read_file", {"path": p}) for p in ["src/api.py", "src/service.py", "src/cli.py", "README.md"]]
        elif self.step == 3 and update:
            actions = [("write_file", {"path": "README.md", "content": UPDATED})]
        elif self.step == 4 and update:
            actions = [("show_diff", {})]
        else:
            return {"message": {"content": "ОФЛАЙН MOCK. " + ("README обновлён; фактический diff показан ниже." if update else "Определение: src/api.py:1; service: src/service.py:5 вызывает send_invite при onboard; CLI: src/cli.py:11 передаёт email, role и dry_run из argparse. Импорты: src/service.py:1, src/cli.py:2.")}}
        return {"message": {"tool_calls": [{"id": f"mock-{self.step}-{i}", "type": "function", "function": {"name": n, "arguments": json.dumps(a)}} for i, (n, a) in enumerate(actions)]}}
