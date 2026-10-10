# Quality runner — независимое повторное review Astra

**Overall: APPROVED — подготовка runner.** Финальное состояние: `329a11f5442cd02ac2a87f3bdaeb438c89e2c10e4f011af381895f4d191cb89c`. Открытых BLOCKER/WARNING нет. Это разрешает переход к уже порученному прогону пяти вопросов; результаты модели и весь quality эксперимент этим verdict не подтверждаются. Отдельное человеческое принятие SPEC/ответов не заявляется.

## Независимые проверки

Astra, фактическая модель gpt-6-astra, xhigh. Прочитаны актуальные project instructions, SPEC/PLAN/README/TASKS, полный runner, оба test modules, вызываемые границы baseline core/ChatEngine, Luna report и RED/GREEN evidence. Указанный worktree — day29-full-chat, branch day29-full-index-chat, base ca9058411363c1815793c80e2f3a778e52674ad3. Git status показывает additive day29; scoped implementation reviewer не менял.

Запущены **34 focused unittest, 34 PASS**, Python3.14.0/macOS arm64, failures0/errors0, exit0. В независимом запуске `unittest.defaultTestLoader.discover('day29/tests', pattern='test_quality_eval*.py')` сеть дополнительно запрещена patches socket.create_connection/urllib.request.urlopen. Проверены нормальные и аварийные пути, immutable subset, сохранение контекста, prefix только из A, ограничения стадий, source refs, бюджет всего payload, private modes, locks, counters, null metrics и recovery без replay. Дополнительно повторён собственный A1 repro после исправления. Реальных HTTP, generation и embedding reviewer: **0**.

Actual selection adapter SHA `1d0b34de7b50fdd4ec4d98be32ebf1dcb72e8cfd3994975046b54c13f2189adb`: H05/H12/H20/H06/H11, seed4766433321957233838, ровно пять holdout из пяти групп, без dependencies, new_conversation=true. Gold denominator этой выборки —12 групп. Порядок соответствует frozen matrix; остальные15 holdout и4 pilot не dispatch. Source audit APPROVED отдельно; root audit SHA `774e07bdfaa0ee166c5364660ad702143fcae4761e4ff5db1e8851579b22ca61` привязан к неизменной матрице и не объявляет human acceptance.

## Закрытые замечания

**Luna / WARNING — исправлено**, `quality_eval.py:205–211`. Фактический repair без refs больше не может пройти на recheck: применяется baseline unknown guard, invalid repair остаётся unavailable, recheck не dispatch. Синтетические negative/positive tests прошли независимо. Unknown guard проверяет допустимую форму, а смысл неизвестности всё ещё оценивает независимый assessor.

**Astra A1 / WARNING — исправлено**, `quality_eval.py:366–381,399–437`. На предыдущем SHA903bdd2e… resume после A=2s и сохранённой critic=10s ошибочно показывал B≈2.014s. Собственный private repro воспроизвёл потерю. Теперь при утрате общего orchestration времени headline B_latency/pair_observed_seconds остаются null; сохранённые stage durations образуют явно названную нижнюю границу, известные execution windows выводятся отдельно. Повтор repro: B_latency=null, added_stage_seconds=10.011589s, B_latency_observed_lower_bound=12.011589s; выполнены только две оставшиеся mock стадии. Новые тесты проверили три cached стадии с суммой22s и нижней границей24s без повторного счёта, старые continuous flags после crash и неизвестную длительность стадии. Нормальный непрерывный путь сохраняет измеренную headline latency. Missing HTTP duration также даёт null total и отдельную observed sum/count.

Старое воспроизведение сохранено в private astra-review/resume-latency-red.json; script и independent-green.json имеют права0600 внутри0700. Матрица соответствия: [implementation-validation.md](implementation-validation.md).

## Границы заключения

Семантическое превосходство, actual stage times, retrieval completeness, false acceptance/rejection и итог пяти вопросов требуют реальных receipts и независимого source-backed scoring. JSON accept не объявляется правильным ответом. Source/gold проверены отдельно; общий hallucination rate и человеческая приёмка не заявлены. Новая запись и delivery script не входят в это review.

## Проверенные SHA-256

- `quality_eval.py`: `329a11f5442cd02ac2a87f3bdaeb438c89e2c10e4f011af381895f4d191cb89c`
- `full_chat_core.py`: `6e887f0dd664d73d7eff0f267ed4dd505142efddfd51d20cbcc26957a5565bf1`
- `core.py`: `ffd03a0c5bc659e50783416c469c72d8f79f7d02a7d9a1309208c74875b2e24d`
- `metrics.py`: `a4314a70bbde27b3b1abd608439ec6895b4d4623a226727a87e68b6bff65ce3d`
- `QUALITY_EVAL_SPEC.md`: `62ea7145a6307e4eb9de47c488c14a9649197f4a2dda89145f1aa71b51a503e2`
- `QUALITY_EVAL_PLAN.md`: `2d0ffe7242248a52dacfc4ab6b641a99e302ddb807258c541acf2392f1f5f668`
- `QUALITY_EVAL_README.md`: `8a34179e9fe1028311ad9fa40b6ecb7ec56dd4e4e2f998c933e8ca722e0bba1d`
- `QUALITY_EVAL_TASKS.md`: `287b0d29e39b7d0b1559609824402bc13382914d14bfd459fb821cee9cc49808`
- `tests/test_quality_eval_protocol.py`: `751818837581c578fcbac4effcf26ce26eaf52a6b68531cc1225a7d6fc5163ce`
- `tests/test_quality_eval_failures.py`: `af6dc8074691225f3bc1b3a7e25413a740e12f05ab383dedaa74dc1318d13132`
- `tests/quality-evidence.json`: `74e35eed1856984d920675bea6f9564f5664afc99e813b24785d90042bdb2dc9`
