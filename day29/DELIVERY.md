# Day29 — текущая локальная поставка

11.10.2026. Полный чат работает локально. Первый эксперимент пяти новых вопросов
сохранён с отрицательным результатом для critic-протокола; диагностический повтор
двух исходных вопросов и новая живая запись пока **PENDING**. Внешняя публикация
новой поставки ещё не подтверждена; ссылки появятся после проверки root.

| Режим | Запуск / экран | Что делает |
| --- | --- | --- |
| Полный чат | `full_chat.py` · [127.0.0.1:8070](http://127.0.0.1:8070) | Вопросы по всему снимку, follow-up, новая/сброшенная и сохранённая история |
| Benchmark оптимизации | `app.py` · [127.0.0.1:8069](http://127.0.0.1:8069) | Public задания, декларативные B/F и однофакторные параметры, исходные измерения |
| Отдельный quality experiment | `quality_eval.py` · CLI | Общий первый A, локальный critic, не более одного repair, recheck; к UI не подключён |

Все model/embedding calls локальные, через Ollama `127.0.0.1:11434`, с общими locks.
Генератор Qwen3 8B Q4_K_M, эмбеддер qwen3-embedding:0.6b. Полный чат использует
temperature0 / context8192 / output1024 / thinkfalse; critic/recheck output512.
Профили benchmark имеют свои параметры и результаты; выбор F не означает,
что этот профиль автоматически применён к полному чату или critic.

Запуск полного чата при доступном immutable индексе:

```sh
python3 day29/full_chat.py --index-root /Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day28/day28/private/index-release-v1
```

[Полный README/API/границы](FULL_CHAT_README.md), [full-chat результат](FULL_CHAT_RESULT.md),
[benchmark README](README.md), [benchmark RESULT](RESULT.md),
[quality CLI и recovery](QUALITY_EVAL_README.md). Не запускать новые inference
параллельно с выполняющимся экспериментом или записью.

## Источники и история

Используется прежний read-only снимок **724 фрагмента / 663 документа**:
24 assignment, 694 discussion и 6 personal_note. Generation
`5d5502c69976163325ad6c35`, DB SHA
`9894d937c4bcbae653459a6fe758f231992571e436622a0cd33fcda7f707f11b`.
Переиндексации, нового corpus fetch или подмены embeddings не выполнялось.

Поиск полного чата включает все типы. История хранится целиком private;
активный контекст — до трёх завершённых пар и до пяти целых источников,
с удалением старых пар/целых низких источников при нехватке бюджета.
Follow-up использует пользовательский anchor для свежего поиска; история
не является доказательством фактов. Неоднозначный singular participant
просит уточнение; коллективное «они/из них» само по себе не делает группу
неоднозначной. Resolver имеет ограниченные грамматические правила.
Автосводок и поиска по старым диалогам нет.

Точные excerpts, author/date и refs проверяются программно по оригинальным
metadata/offsets; это техническая атрибуция, не автоматическое доказательство
смысловой поддержки каждого утверждения. Корпус, вопросы, gold, сообщения,
история и raw receipts хранятся в `private/`, 0700/0600, не публикуются в Git.
Loopback API отдаёт разговоры и materialized sources для локального UI; отдельного
HTTP маршрута к raw receipts/storage нет. Public reports показывают IDs, counts, hashes и оценки без
частных текстов. Новая публичная запись показывает только assignment sources;
capture privacy filter скрывает чужую историю и отсекает private cited evidence.
Он относится к recorder, а не меняет scope поиска runtime-приложения.

## Что уже измерено

Исходный benchmark: полнота E02 2/5 → 5/5 по двум warm повторам, generation
median43.51 →100.06s. Ускорение и снижение RSS10% не доказаны. Q8 — одна
неудачная warmup проба с length/incomplete JSON; scored warm Q8 не выполнялись.
Это отдельные historical результаты, не оценка качества всех вопросов полного
чата. [Исходное видео](video/Day29-live.mp4) и [Day29-code.zip](Day29-code.zip)
остаются прежними материалами benchmark; новый полный чат в этот ZIP не добавлялся.

Первый прогон выбранных **пяти** новых holdout, run
`405d5a5a7bac4e0da30aafccb6f600b7`: 6 generation / 3 embedding calls, HTTP errors0;
15 оставшихся holdout и четыре pilot не запускались.
[Runtime](quality-results/initial-five-runtime.json),
[независимая blind оценка](quality-results/initial-five-semantic.json).
Три A были сгенерированы, два кейса ошибочно запросили уточнение. В наблюдённых
ответах отмечены 15 supported atomic claims, 0 contradicted/unsupported,
но полностью покрыты только 4 из 12 gold-групп; ещё две группы частично.
Это не общий hallucination rate и не человеческая приёмка.

Завершённых B и сопоставимых A/B pairs — **0**: один repair envelope не вместился
в бюджет, два critic verdict insufficient_evidence, два no-generation случая
not_applicable. Поэтому улучшение B **не поддаётся оценке**, а не «доказано».
[Source-backed оценка критики](quality-results/initial-critic-semantic.json)
отметила ошибочный repair rejection и два неоправданных insufficient_evidence;
мнение критика не является gold. Critic не включён в обычный UI автоматически.

## Проверенные этапы и публикация

- **Resolver fix проверен:** 37 full-chat и 34 quality offline tests PASS,
  независимое [Astra review](quality-results/review-resolver-astra.md) APPROVED.
  [Payload equivalence](tests/full-chat-local-antecedent-evidence.json): для трёх
  первоначальных model answers query/messages/payload неизменны; поиск/prompt/options
  не менялись. [Restart](quality-results/resolver-restart.json) сохранил историю без replay.
- **Диагностический retest двух завершён:** run `5c2b89978dd64feeb73e99eede037f0d`,
  4 generation/2 embedding, HTTP errors0; B completed0. [Blind source grading](quality-results/diagnostic-two-semantic.json):
  H11 полнота2/3+1partial и5 supported claims; H06 корректный unknown по переданному
  контексту, но original названного дня отсутствовал в prompt. Это отдельный известный retest.
- **General exact-day source fix проверен:** [Luna](quality-results/review-day-parser-luna.md)
  → [Astra](quality-results/review-day-anchor-astra.md) APPROVED; fresh139 offline PASS.
  Word boundaries/полное число исключают ложные day matches. Same724 scorings, old3
  messages/payload exact. [Restart](quality-results/day-anchor-restart.json) сохранил4
  conversations без replay. Новый known **H06-only** diagnostic run
  `9d22f02d7a5e4f5ba80058fb0798bd96` завершён:2gen/1embed, HTTPerrors0, B0.
  Original точного дня теперь в prompt. [Независимая оценка](quality-results/diagnostic-one-source-semantic.json):
  A0/2, FALSE_REFUSAL_GIVEN_CONTEXT1. Улучшение B не доказано; новых tuning steps нет.
  Новых random вопросов нет.
- **Свежая live запись проверена:** [Day29-live-full-chat.mp4](video/Day29-live-full-chat.mp4),
  296.68s /1280×1000/H264/25fps. [Root media/receipt verification](quality-results/new-live-video-verification.json):
  3 новых asks,6 IDs disjoint dry/record, source supportPASS, private/pageerrors0,
  wholedecode0errors и9decoded frames прочитаны. B2/5,F5/5 по E02;
  fullDay11 пропустил2selfchecks. Это одиночный новый live pair, historicalwarm
  замеры и исходные неудачи сохранены; выигрышBcritic и общийhallrate не доказаны.
  В кадре safeсводка исходных5 и известных повторов, rawprivatecase/evidence не опубликованы.
- **Final delivery audit — APPROVED:** [Astra validation](quality-results/delivery-validation-astra.md),
  60 applicable PASS,0 FAIL,0 NOT PROVEN;142offlinePASS. Качество имеет ограничения выше;
  human acceptance и внешняя публикация отдельно от локального SPEC verdict.
- **Публикация проверена:** [код GitHub main/day29](https://github.com/RomaniumSSS/ai-advent-9/tree/main/day29),
  [новое видео Drive](https://drive.google.com/file/d/1qIRVmVwnBzPzozciiwdNXQ8-k5DU4S6H/view?usp=sharing) — primary account, указанная папка,
  Anyone with the link/Viewer. Анонимный previewHTTP200 без запроса доступа.
  Собственный комментарий **Лист1!AD132** содержит отдельные video/code URLs;
  заголовок/участник и запись проверены после полной перезагрузки, Saved to Drive.
  [Publication proof](quality-results/publication.json); пользовательская приёмка не заявлена.


Первоначальные неудачи и расходы сохраняются. Положительный результат B,
полнота всех 24 вопросов или человеческая приёмка не заявляются.
