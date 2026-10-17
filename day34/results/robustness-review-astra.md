# Day34 robustness — независимое повторное ревью Astra

**Overall: NEEDS CHANGES.** 17.10.2026. Reviewer: gpt-6-astra. Прочитаны SPEC (включая расширенные критерии), core/model/budget/runner, тесты, fixtures, manifest, offline evidence и первое ревью Luna. Использованы review и agents-best-practices. Вывод Luna о полной готовности офлайн-реализации не подтверждён двумя дополнительными probes.

## Требуемые исправления

1. **[WARNING] `day34/core.py:99–104` — новый пустой файл невидим в авторитетном diff.** В свежем Sandbox выполнить `write_file({"path":"reports/empty.txt","content":""})`, затем `show_diff({})`: запись успешна, файл существует, но результат diff — `{"ok":true,"data":"","truncated":false}`. Отсутствующий baseline и существующий пустой файл приравнены через `b""`. Хранить/сравнивать существование отдельно от байтов и отражать создание пустого файла в evidence. Regression: создание пустого report видимо, повторная запись тех же байтов — no-op.

2. **[WARNING] `day34/core.py:100,184–187` — сохранённая symlink ломает итоговый diff, но run остаётся успешным.** В trusted fixture добавить неизменённую symlink на временный внешний файл; scripted model выполняет только запись README и возвращает final answer. Наблюдение: README реально изменён, `status="completed"`, `reason="final_answer"`, `diff="Diff недоступен: нарушение sandbox"`. Причина: baseline исключает symlink, files включает её, diff вызывает запрещающий path; финальный catch не отражает ошибку в статусе. Учитывать symlink безопасно без чтения цели (например, отдельные метаданные и сравнение link target); итоговую невозможность получить diff в любом случае обозначать ошибкой run. Regression: неизменённая symlink не скрывает изменения README; ошибка финального diff исключает completed. Чтение/запись через symlink должны остаться запрещены.

## Свежие проверки и границы вывода

macOS, uv Python 3.12.12: `uv run --offline python day34/test_day34.py` — 13 PASS; `day34/test_robustness.py` — 7 PASS; `day34/video/test_run_demo.py` — 3 PASS. Два дополнительных probes выше выполнены на настоящих временных файлах со scripted model и воспроизвели описанные результаты. Реальные API и общий ledger не использованы; application suite использует локальный loopback HTTP.

Подтверждены fail-closed missing/mismatched identity, числовой finite/nonnegative cost с сохранением unknown holds, неполный/обрезанный поиск, byte baseline для binary/nonUTF8, запрет symlink traversal и копирование без dereference. SessionCap считает actual + неизвестные резервы; конкурентное применение локального cap явно вне контракта, общий ledger остаётся атомарным. В manifest ожидания отделены от runtime; исходники подтверждают alias/qualified callsites и локальные I/O, семантического oracle в runtime не обнаружено.

**Live semantic behavior: NOT PROVEN.** Существующие тесты не доказывают выполнение смысловых требований настоящей моделью; это остаётся отдельной проверкой назначенного оператора. Пользовательское принятие не заявляется. Изменён только этот отчёт; код и evidence исходных прогонов сохранены.

## Повторная проверка исправлений — 17.10.2026

**Актуальный итог: APPROVED (offline implementation).** Оба замечания выше закрыты; первоначальные findings сохранены как история. Самостоятельно повторно прочитаны core.py/test_robustness.py и evidence `robustness-astra-fixes.json`.

Создание пустого файла теперь отражается отдельной записью `diff --git` и фактическим `new file mode`; повтор той же записи не добавляет изменений относительно исходного baseline. Ссылки учитываются через `readlink` без чтения цели; неизменённые ссылки не скрывают diff README, изменённые отклоняются. Ошибка финального diff устанавливает `status=error`, `reason=diff_error` и помечает ответ неподтверждённым.

Свежий независимый запуск: `uv run --offline python day34/test_robustness.py` — **10 PASS**, Python 3.12.12. Дополнительные независимые probes на временных файлах: пустой файл с проверкой фактического mode и повторной записи; одновременные dangling symlink и вложенная directory symlink вместе с правкой README; финальный diff с OSError — **PASS**. Общие 13 application + 3 recorder PASS зафиксированы исполнителем в fixes evidence; в этом targeted recheck повторно не запускались, ранее reviewer запускал их до исправлений.

Проверенные SHA256 совпали с fixes evidence: core.py `1bd82a66cb7375115b6f63553e84c2fd58d2472a4710de1908b1fbc814e40e6e`; test_robustness.py `9aea6c547f8a35d441b08a82e79d0f0b20f80b30b9b79ccc1083155c742bd1a7`. Live/API и общий ledger не использованы. Семантическая live-проверка и пользовательское принятие остаются отдельными.
