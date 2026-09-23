# День 17: первый MCP-инструмент

## Goal

Добавить в обычный пользовательский чат минимальный полный tool-calling flow:
модель выбирает собственный MCP-инструмент, harness проверяет и выполняет один
read-only вызов, возвращает результат модели как observation, а модель формирует
проверенный финальный ответ пользователю.

Результат считается достигнутым только при фактически наблюдаемой цепочке
`user → model decision → validation → MCP execution → observation → final model response`.

## Scope

- Tool calling доступен только обычному пользовательскому chat flow.
- Используется один собственный read-only Git MCP tool `get_recent_commits`.
- Инструмент читает историю настроенного репозитория и не принимает возможность
  переключиться на произвольный репозиторий или выполнить Git-запись.
- Вход инструмента содержит ограниченное число запрашиваемых последних коммитов.
  Тип, допустимый диапазон и назначение параметра явно присутствуют в MCP schema.
- Результат содержит упорядоченный от нового к старому ограниченный список с
  идентификатором коммита и достаточными метаданными, чтобы модель могла описать
  найденные изменения без догадок.
- Schema, которую получает модель, происходит из MCP discovery, а не из отдельной
  вручную поддерживаемой копии.
- MCP discovery и MCP tool execution — разные события. Discovery читает
  capabilities и schema, но не вызывает `tools/call` и не выполняет
  `get_recent_commits`. MCP tool execution означает вызов `tools/call`. Успешный
  discovery snapshot может повторно использоваться; discovery не обязан
  выполняться на каждом chat turn.
- За один logical user turn разрешены максимум два provider calls: первичное
  решение модели и, если был tool request, финальный ответ после observation.
- За один logical user turn разрешён максимум один MCP tool execution.
- Один logical turn имеет общий audit context, внутри которого provider calls и
  MCP tool execution различимы по роли, порядку, статусу и результату.

## Out of Scope

- Tool calling внутри FSM workflow, его planning, execution или validation turns.
- Parallel tool calls.
- Несколько tool calls в одном model response.
- Последовательные tool calls после первого observation.
- Повторный MCP execution, автоматические tool retries и циклы исправления
  аргументов в рамках одного logical turn.
- Любые side-effecting tools: запись в Git, создание или изменение файлов,
  публикация, deploy, отправка сообщений и другие внешние изменения.
- Approval flow для side effects.
- Несколько MCP-серверов, выбор сервера моделью и динамическая установка tools.
- Изменение существующего FSM graph или смысла его `model_turns`.

## Required Behavior

1. До первого предоставления tool модели должен существовать успешный MCP
   discovery snapshot. Model-visible имя, назначение и input schema
   `get_recent_commits` происходят из этого snapshot. Один и тот же допустимый
   snapshot может использоваться в нескольких chat turns.
2. Модель может либо сразу вернуть обычный финальный ответ, либо запросить
   `get_recent_commits`.
3. Если tool не запрошен, MCP execution не выполняется, а успешный проверенный
   ответ завершается как обычный одношаговый chat turn.
4. Если tool запрошен, harness до execution обязан проверить:
   - что получен ровно один tool request;
   - что имя точно совпадает с разрешённым tool;
   - что arguments являются корректным объектом;
   - что arguments соответствуют обнаруженной MCP schema и локальным пределам;
   - что лимит одного MCP execution ещё не исчерпан.
5. Непосредственно перед MCP execution harness повторно проверяет, что исходный
   FSM snapshot не изменился и состояние не стало `paused` или `done`. Только
   прошедший все проверки request может быть исполнен MCP-сервером.
6. Успешный `get_recent_commits` result имеет `is_error=false`, относится к
   настроенному репозиторию и содержит непустой список не более запрошенного
   размера. Каждый элемент содержит непустые commit ID, subject, author и
   timestamp; порядок — от нового к старому. Только такой bounded result является
   successful observation. Empty, malformed, `is_error`, timeout и protocol
   failure являются error observations.
7. Observation связывается с исходным tool request. Перед финальным model call
   harness снова проверяет актуальность FSM snapshot и запрет `paused`/`done`.
   После successful или error observation выполняется ровно один финальный model
   call. Ему доступны
   исходный пользовательский запрос, исходный tool request и соответствующий
   tool result.
8. Финальный model call не может инициировать ещё одно исполнение инструмента.
   Повторный tool request получает связанный локальный denial result в audit,
   но не передаётся третьему model call; logical turn завершается application
   error.
9. Перед persistence финального ответа harness в третий раз проверяет исходный
   FSM snapshot и запрет `paused`/`done`. Изменившееся состояние инвалидирует
   оставшуюся часть logical turn.
10. Финальный текст проходит существующие response invariants до попадания в
   разговор, durable history или пользовательский ответ.
11. В разговоре сохраняются только исходное пользовательское сообщение и
    проверенный финальный ответ. Промежуточный tool decision и observation не
    становятся обычными chat messages.
12. Audit различает как минимум logical turn, первичный provider call, MCP
    execution,
    финальный provider call, tool name, проверенные arguments, success/error
    status и безопасное резюме результата. Usage и стоимость каждого provider
    call учитываются отдельно.

## Invariants

- Модель только предлагает tool request; validation и execution принадлежат
  harness.
- За один logical user turn выполняется не более одного MCP tool execution и не более
  двух provider calls.
- `get_recent_commits` остаётся read-only и не может менять Git, файлы,
  приложение, память агента или FSM.
- Обычный chat flow с tools не расширяет возможности существующего FSM workflow:
  workflow не получает tool schemas, tool observations или право вызывать MCP.
- Модель сама не меняет FSM stage, status, version, proposal или artifacts.
- Состояния `paused` и `done` запрещают model-driven tool execution. Проверка
  выполняется до передачи tool schema модели, перед MCP execution, перед LLM2 и
  перед persistence финального ответа.
- Изменение FSM state или version во время logical turn инвалидирует все ещё не
  выполненные шаги. Уже завершённый read-only result остаётся только в audit, но
  не передаётся следующему model call, не сохраняется в разговор и не может быть
  основанием для перехода.
- Текст модели не является доказательством внешнего действия.
- Успешный audited MCP observation подтверждает только возвращённые Git-данные,
  но не публикацию, deploy, запись или другое внешнее изменение.
- Tool denial, validation error, timeout, protocol error и `is_error` result не
  являются успешным observation и не могут быть представлены как успех.
- Каждый полученный tool request получает связанный success или error result.
  Results запросов из LLM1 передаются LLM2; повторный запрос из LLM2 получает
  локальный denial result только в audit, потому что третий provider call запрещён.
- Содержимое MCP result считается внешними данными, а не инструкциями или
  разрешением изменить policy.
- Существующие request invariants, terminal guards, transition guards и final
  response guard продолжают действовать до сохранения результата.

## Failure Behavior

- Discovery не обязан повторяться на каждом chat turn. Ранее полученный
  допустимый discovery snapshot может использоваться повторно. Если snapshot
  отсутствует и discovery завершается ошибкой, turn продолжается tool-disabled:
  обычный вопрос может получить обычный ответ, а запрос актуальных Git-данных —
  только явное сообщение о недоступности инструмента без выдуманных данных.
- Ошибка, timeout, empty или truncated response первого provider call не запускает
  MCP execution и не сохраняет conversational turn; состоявшийся provider call
  остаётся различимым в audit.
- Неизвестное имя, malformed arguments, schema violation или несколько tool
  requests не запускают MCP execution. Модель получает связанное error
  observation и может только сформировать финальное объяснение.
- Если первый provider response содержит несколько tool requests, ни один из них
  не исполняется; каждый получает явный denial result.
- MCP timeout, transport failure, protocol failure, `is_error`, empty или
  malformed result возвращаются
  модели как error observation. Финальный ответ обязан сообщать о невозможности
  получить данные и не может выдумывать коммиты или заявлять об успехе.
- Если финальный provider call снова запрашивает tool, новый MCP tool execution не
  выполняется. Request получает связанный локальный denial result в audit;
  третьего provider call нет. Logical turn завершается ошибкой лимита, без
  сохранения сырого model output как финального ответа.
- Ошибка, timeout, empty или обрезка финального provider response не сохраняет незавершённый
  conversational turn. Уже состоявшиеся provider/MCP события остаются видимыми
  в audit.
- Если FSM state/version изменился перед MCP execution, LLM2 или persistence,
  оставшаяся часть turn не выполняется. Уже завершённые read-only события
  остаются в audit, но не считаются применённым результатом turn.
- Нарушающий final response не сохраняется. Допустим только существующий
  безопасный локальный отказ вместо сырого нарушающего текста.
- Ошибка обязательного audit persistence останавливает turn до следующего шага:
  после LLM1 не выполняется MCP, после MCP не вызывается LLM2, после LLM2 не
  сохраняется и не показывается успешный final response. Вызывающий код получает
  явную application error; незафиксированный success не считается подтверждённым.

## Acceptance Criteria

1. MCP discovery содержит `get_recent_commits` с непустым описанием и
   проверяемой input schema, включая описание и предел числа коммитов.
   Model-visible tool set содержит только этот разрешённый tool, а переданные
   модели name, description и schema совпадают с discovery snapshot. Наличие у
   сервера других типов MCP capabilities не нарушает критерий.
2. Discovery не обязан повторяться на каждом chat turn. При отсутствии
   допустимого snapshot и ошибке discovery обычный не-Git вопрос завершается
   tool-disabled ответом, а Git-запрос — явным сообщением о недоступности без
   выдуманных данных; в обоих случаях MCP tool executions равны нулю.
3. Обычный вопрос, не требующий Git-данных, завершается одним provider call и
   нулём MCP tool executions.
4. Запрос о последних коммитах приводит к следующей наблюдаемой
   последовательности: первичный provider call → один validated MCP tool
   execution (`tools/call`) → один финальный provider call.
5. Настоящий E2E acceptance без mock provider и mock MCP выполняется из
   приложения: реальная модель без принудительного выбора конкретного tool сама
   запрашивает `get_recent_commits`; собственный MCP-сервер читает настоящий Git;
   result совпадает с независимо прочитанной историей того же репозитория и
   лимита; LLM2 использует эти commit ID или subjects в final response.
6. Успешный result соответствует минимальному контракту observation. Empty,
   malformed, `is_error`, timeout и protocol failure фиксируются как error
   observations и не могут пройти successful path.
7. Финальный ответ использует значения из фактического MCP result; заранее
   заданный или выдуманный commit ID не считается прохождением.
8. Audit одного успешного logical turn различает оба provider calls и MCP
   execution, сохраняет их порядок, status, отдельные usage/cost и показывает
   один successful tool execution. Для одношагового и каждого failure path число
   фактических provider calls и MCP executions также совпадает с audit.
9. Неизвестное tool name и невалидные arguments дают ноль MCP executions,
   связанный error observation, ровно один финальный model call и отсутствие
   ложного утверждения об успехе.
10. Несколько tool requests в первом response дают ноль MCP executions; каждый
    получает связанный denial result, после чего выполняется не более одного
    финального model call.
11. Повторный tool request в финальном response не исполняется, получает
    связанный локальный denial result в audit и завершает turn application error:
    третьего provider call и сохранённого conversational turn нет.
12. MCP error или timeout виден как failure в audit, а финальный ответ не выдаёт
   его за полученные Git-данные.
13. Ошибка, timeout, empty или truncated response первого provider call дают
    один provider call, ноль MCP executions и отсутствие conversational turn.
    Те же failures финального provider call дают два provider calls, не больше
    одного MCP execution и отсутствие conversational turn; audit сохраняет
    фактически состоявшиеся события.
14. В durable conversation после успешного tool turn находятся только одна
    user/assistant пара и проверенный final response; промежуточные protocol
    messages не становятся chat history.
15. При начальном `paused` или `done` выполняются ноль provider calls и ноль MCP
    tool executions. Изменение FSM state/version перед MCP execution, LLM2 или
    persistence прекращает оставшуюся часть turn; поздний result/final response
    не попадает в conversation и не влияет на FSM.
16. До и после настоящего E2E состояние Git refs, index и worktree совпадает;
    единственное внешнее наблюдение — чтение истории коммитов.
17. Инъекционная инструкция внутри subject/author другого commit metadata
    остаётся данными: она не меняет policy, не вызывает дополнительный tool и не
    приводит к внешнему действию.
18. Принудительный сбой обязательного audit persistence после LLM1, MCP или LLM2
    останавливает следующий шаг, возвращает application error и не создаёт
    подтверждённый final response или conversational turn.
19. FSM workflow не получает tool schema, сохраняет прежние переходы и прежний
    смысл `model_turns`; его существующие проверки продолжают проходить.
20. Запрещённый final response не попадает в историю, audit результата задачи
    или workflow proposal.
21. Регрессионные проверки Day 15 и Day 16 проходят без ослабления их исходных
    гарантий; специфичные утверждения Day 16 об отсутствии execution остаются
    верны для самого Day 16.
