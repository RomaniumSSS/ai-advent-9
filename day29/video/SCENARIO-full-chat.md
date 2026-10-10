# Новый Day29 live delivery: три запроса за дубль

Отдельный сценарий и `run_full_demo.py`; прежние Day29-live.mp4, SCENARIO.md,
run_demo.py и verification artifacts сохраняются неизменными. Новый дубль показывает
готовые приложения `/8069` и `/8070`; публикацией/доставкой занимается root.

## Что показываем

1. В 1280×1000 открыть настоящий `/8069`: public scope, frozen index SHA, Q4_K_M,
   B/F cards и разницу generic prompt. Переключить declarative temperature 0.2,
   max output384 и context6144; никакой генерации при переключении нет.
2. **Новый** вопрос E02 «Чем отличаются требования заданий дней 19 и 20?»:
   baseline, затем candidate. Один новый `/api/ask` каждый, ожидание именно его
   request ID, сверка profile/question/status/visible answer/receipt и original sources.
   Не подписывать свежий ответ автоматически полным; semantics root проверяет отдельно.
3. Показать сохранённые historical blocks и таблицу: полнота E02 2/5→5/5 по двум
   повторам, median B43.51/F100.06s, ускорение и RSS10% не доказаны; warm/cold отдельно.
   Численный swap, observed daemon+runner RSS и placement показываются из настоящего
   сохранённого summary с runIDs/date, не выдаются за новый замер этого дубля.
   Q8 — одна неудачная warmup проба: incomplete JSON, length384, ~140.81s/~8.57GiB;
   два scored warm не выполнялись, полного quality/Q8 benchmark нет. Q4 осталась,
   Q8 weights на SSD, в RAM выгружены. Все числа сверить с текущим historical API.
4. Открыть настоящий `/8070`: scope all724/663, Qwen3:8b, temperature0/ctx8192/output1024,
   собственный новый пустой разговор. **Новый** публичный вопрос Day11
   «Что нужно сделать в задании дня 11?». Только assignment materialized sources
   разрешены в кадр; показать exact original с request-scoped refs, параметры и времена.
   Полный поиск не ограничивается public: hidden private selected могут существовать,
   это не повод утверждать public-only generation. Каждый видимый claim root проверяет
   по original public источникам; технический refs check не заменяет смысловую оценку.
5. Reload собственного разговора — новая запись сохранилась, без новой generation.
   Reset только собственного заполненного разговора, затем new conversation — пусто.
   Чужая история не сбрасывается и не появляется в меню или кадре.

Итого **3 новых ask submissions на dry** и **3 новых на record**, не один replay.
Quality experiment выбранных пяти private вопросов проводится root отдельно и в
это публичное видео не включается. Голды/заметки/обсуждения/участники не показываются.
6. Если передан --quality-summary, открыть root-owned standalone public HTML
«Сохранённый тест пяти новых вопросов»: IDs/types/counts/quality/times, без
questions/private evidence. Это сохранённый отдельный эксперимент, не replay
живых ответов. Recorder не создаёт и не подставляет результаты; root создаёт HTML
после настоящих пяти и blind source grading. SHA отчёта фиксируется между dry/record.

## Capture privacy filter

Recorder на уровне своего изолированного browser context фильтрует только меню чужих
conversations. До любого ответа `/8070`, который UI мог бы render, проверяет own CID/RID,
question, saved private receipt, original text и materialized sources=assignment.
Private cited source или wrong original/request scope → abort до DOM, сохранить failedtake.
POST reset/ask чужого разговора блокируется **до** отправки. Собственные CID/request,
status/metrics/answers остаются реальными; они не заменяются фикстурами/старыми ответами.

Это защитный фильтр записи, **не поведение runtime приложения**. Hidden selected
private corpus остаётся hidden и учитывается только числом в private journal.
Dry run служит qualification public question; root читает все visible claims/sources
и кадры до record. Если cited evidence private, автоматической замены вопроса/retry нет.
Можно явно начать новый take для public Day16/17 (`--full-day`), сохранив предыдущую
ошибку и все расходы; это решение root, не скрытая автоматическая коррекция.

## Команды root после reviews и пяти новых тестов

При уже работающих приложениях и безопасном idle Ollama:

```sh
uv run --offline --no-project --with playwright python day29/video/run_full_demo.py \
  --dry-run --output day29/video/runs/full-dry-NEW \
  --quality-summary day29/quality-results/five-run-summary.html
# После public-only claim/source и frame qualification этого dry:
uv run --offline --no-project --with playwright python day29/video/run_full_demo.py \
  --record --qualified-dry day29/video/runs/full-dry-NEW/results.json \
  --output day29/video/runs/full-record-NEW \
  --quality-summary day29/quality-results/five-run-summary.html
```

Новый каталог обязателен; old artifacts не перезаписываются. Record требует завершённый
matching dry с тем же script SHA и action list. Gate также перепроверяет три
уникальных request IDs, done/visible-match, точные model/digest/profile/options/index,
pre/post app state, private full receipt SHA и source qualification, общий B/F context,
времена receipts внутри take, privacy/page errors и hashes обязательных PNG кадров.
Три пустые записи или старые replay receipts не квалифицируют record. В каждом режиме одинаковые действия,
новые request IDs и собственный новый разговор. HTTP transport timeout приложения300s;
recorder ожидает terminal330s без retry. При неизвестном исходе остановиться, не
отправлять следующий запрос; root подтверждает безопасный idle перед новым take.

Recorder закрывает только свои Chromium/context в finally. MP4 H.264/1280×1000,
без звука/ускорения/монтажа, ffmpeg `-n`; ffprobe/SHA записываются в новый journal.
Каждый frame связан со временем raw capture. Все журналы/raw/screenshots private0700/0600
в ignored video/runs; public MP4 копируется root лишь после privacy/decode/frame audit.
После записи проверить полное decode, начало/параметры/B/F/sources/historical table/
Q4-Q8/RSS-swap/full public answer/persistence-reset; visible answer и metadata сверить
с receipt именно нового take. Замечания/failed takes сохранить, не подменять успехом.

## Что уже проверено без реальной модели

`python3 -m unittest discover -s day29/tests -p 'test_full_demo.py' -v`: пятнадцать synthetic
checks, public action list/receipt scope/originals/private evidence gate/own history/
qualified dry/no retry. RED→GREEN: чужой reset теперь не отправляется даже один раз.
Synthetic Chromium helper поднимает два ephemeral local mock приложения, проходит
те же три действия и проверяет чужую историю без изменений; Ollama/embedding calls0.
Это проверка recorder/selectors/CSP, не live qualification, не новое measured video.
Mock results с fixture_only=true не принимаются за prerequisite живого record.
Optional quality HTML проверен по path/hash контракту offline; настоящий HTML и
его навигацию root проверит в final dry после source grading.

## Recorder review fixes — 11.10.2026

Luna wrongmodel/digest/options/index и empty-dry findings воспроизведены
[behavioral RED](../tests/full-demo-identity-red.txt), затем исправлены.
15 focused synthetic checks GREEN. Неверная identity/profile/API state, incomplete
dry, duplicate/replayed IDs, changed screenshot и inconsistent context отвергаются.
Full wire payload проверяет исходный SYSTEM/thinkfalse/schema/options; A/B core не
менялись. Synthetic browser helper metadata обновлены; повтор Chromium на новой
версии отложен root до завершения активного quality run. Прежний Chromium PASS
проверял selector/privacy/action flow предыдущего draft, не финальную identity gate.

### Canonical metadata gate — 11.10.2026

Оба приложения используют canonical `assignment:NN`: full-chat в document_id, benchmark в materialized source. Реальный benchmark receipt подтвердил формат; прежняя no-colon fixture не соответствовала API.
Recorder принимает canonical full shape и точный выбранный день, не ослабляя model/
profile/index/source guards. [RED](../tests/full-demo-canonical-red.txt) воспроизвёл
ошибочный отказ валидному metadata-shaped receipt; 16 focused checks GREEN.
