# Day30 — финальная узкая валидация Astra

**D1–D5: PASS. D6: NOT PROVEN (публикация ещё выполняется). Итог текущего маршрута сдачи: SPEC PARTIALLY SATISFIED.** Новых блокеров для перехода к разрешённой публикации не обнаружено. Пользовательская приёмка остаётся pending.

## База и границы

Проверен worktree `day30-private-service`, текущий addendum SPEC D1–D6 от12.10.2026 и уже независимо проверенный runner SHA256 `90403c939229097d1dffd78a2743549259eb9c6dc47d053756b7aa264ced0949`. Это узкая валидация нового маршрута сдачи и новых dry/record артефактов, не повторная полная сертификация всех исторических гипотез SPEC.

Самостоятельное сравнение с `results/code-baseline-12.json`: изменены PLAN, README, SPEC, video/SCENARIO и video/run_demo; остальные записанные в baseline Python-файлы runtime неизменны. Фактические параметры обоих вызовов во всех шести новых receipts совпали с profile12. Historical private semantic FAIL не переоценён; archive quality не входит в текущий gate. Второе физическое устройство не включено как дополнительное требование.

Модель возможного ложного подтверждения: готовый JSON мог бы относиться к старым запросам, новому runtime либо отличаться от полного receipt; follow-up мог бы создавать новый разговор; записанное видео могло бы быть dry/replay или не показывать оригиналы; публикация could contain private traces despite a safe filename. Поэтому проверены уникальные IDs, связанные файлы и readbacks, baseline hashes, полные метрики/бюджеты, фактические кадры/MP4 и ограниченная схема новых public summaries. Полные traces/prompts/рассуждения не выводились; из trace анализировались только budgets/options.

| SPEC | Наблюдаемое требование | Доказательства | Статус | Граница |
| --- | --- | --- | --- | --- |
| D1 | Локальная модель, LAN HTTPS API, браузерный чат | assignment-delivery-preflight; текущие runtime hashes; шесть полных receipts и кадры UI | PASS | digest/preflight и loopback проверены root; reviewer не повторял live запросы |
| D2 | Три новых ответа, follow-up в том же разговоре, третий в новом | assignment-dry.json ↔ dry-01/run, accepted, response, private-response, conversation files; независимые аналогичные record3 | PASS | Все6 done, непустые ответы и originals, уникальные IDs; по2 attempted/2 completed generation calls; содержание не получает semantic PASS |
| D3 | Проверенный LAN TLS и защита | preflight CA/hostname main+demo; authenticated state, missing/bad token401, Host403, Origin403, overlength400; dry/record401/400 | PASS | Проверка с того же Mac; другое физическое устройство NOT PROVEN |
| D4 | Limits, стабильные состояния/readback | 151 offline tests artifact; live400/409 обоих прогонов; фактические budgets всех12 стадий; conversations/readbacks; dated restart12/recovery12 | PASS | 429/Retry-After и failure/lock paths — offline; новый restart не заявлен; старые27 состояний — проверка02:52–02:55 |
| D5 | Новое настоящее видео с3 запросами, ожиданием, ответами и открытыми originals | Record IDs отличаются от dry; recorder/run receipt; MP4 hash/ffprobe; просмотр начала/конца и трёх contact sheets; root full decode | PASS | Кадры выборочные; полный FFmpeg decode выполнен root, reviewer его не повторял; видео не является доказательством точности пересказов |
| D6 | GitHub main, Drive sharing/playback, две ссылки в собственном комментарии AE132 и readback | Пока локальные артефакты; RESULT/DELIVERY честно показывают pending | NOT PROVEN | Нужны финальные remote SHA, Drive permission/playback, Sheets Saved/reload/readback |

## Фактически выполненная независимая проверка

`/usr/bin/python3 -B`, локальный macOS, offline: assertion-based сопоставление safe summary с private safe-summary и run.json; каждого accepted/public/private ответа по IDs/status/metrics; assignment scope, непустые summary/conclusion/original; всех readback conversation IDs/порядка/terminal done; вызов настоящего `observed_limits`, извлечённого из текущего runner AST, для каждого полного receipt. Все проверки завершились exit0.

- Dry времена:128.224 /124.199 /177.048с; record:133.369 /113.914 /190.046с.
- Все6 request IDs различны; каждый сценарий имеет первый и второй ход в одном conversation, третий — в новом.
- Для всех selection:8192/1024/temperature0; synthesis:8192/1024/temperature0.7/top_p0.8. Observed prompt+output reserve+template reserve не превышают8192; output не превышает1024.
- В обоих прогонах реальные401 unauthorized,400 invalid_request и409 busy; browser_errors пуст; original_opened true для всех6; readbacks done.
- Независимые `ffprobe`, размер и SHA MP4:517.000000с,1280×1000, единственный H264 stream,10183644bytes, SHA256 `38ff8dae21fc533458eeec8321c0c4c7d0166e2a7bcbde2b1e835c22d21130e5`. Аудиопотока нет.
- Просмотрены `frame-0.png`, `frame-4.png` и contact sheets `original-one/two/three-grid.png`: видны assignment banner, новые вопросы/ожидание, ответы, реальные IDs/метрики и раскрытые originals. В просмотренных кадрах ключей и private-источников не обнаружено. Root дополнительно просмотрел кадры0.5/151.8/288.9/502.4/516с и сообщил успешное полное FFmpeg декодирование.
- В246 текущих git-public candidate files Day30 нет точного текущего credential, путей private, .env, .key/.pem или видеобинарников. Новые safe summaries имеют ожидаемый ограниченный top-level schema и не содержат вложенных query/trace/prompt/text/answer/question/token. Это bounded screening текущих кандидатов; не гарантия произвольного смыслового отсутствия утечек и не замена финальной проверке staged публикационного пакета.

Широкий suite, inference, браузерную сессию и перезапуск reviewer не повторял. Доказательства151 offline и live preflight использованы как отчёты root с указанной средой, отдельно от самостоятельно выполненных сравнений. Репозиторий reviewer не изменял.

## Осталось

D6 требует фактических внешних публикационных readbacks. После финального обновления документов необходим точный staged manifest/secret privacy check; старые дни должны остаться неизменными. В просмотренных RESULT/DELIVERY проверка кадров/playback ещё помечена pending — её можно обновить на фактически выполненную, сохраняя D6 pending до readback. Human acceptance остаётся отдельной и не выводится из технических PASS.
