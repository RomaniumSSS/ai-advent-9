# T4 — доказательства исполнителя

Дата: 04.10.2026. Область: SPEC R1–R8, PLAN P4. Независимый gate ещё не выполнен.

Файлы: `app/index.html`, `app/app.js`, `app/style.css`, `app/web.py` (маркер синтетического стенда и обработка закрывшегося браузерного соединения), `app/preview_fixture.py`, `app/test_web_chat.py`, три `app/browser_*checks.js`, актуализированная `app/README.md`. Service/контекст/ledger T1–T3 не изменены; Day24 не изменён.

## Офлайн API и регрессии

Локальный macOS/Python 3.14: `cd day25/app && python3 -W error::ResourceWarning -m unittest -v test_chats test_context test_states test_web_chat` — 27 тестов PASS, 3.691с. `node --check day25/app/app.js` и browser_checks.js — PASS (Node24.11.1). `git diff --check` — PASS. Хеши Day24 — PASS.

Новые HTTP-тесты проходят реальный loopback сервер и API-путь create → memory v1 → ask → archive/result → feedback → clear v2 → новый Service/restart. Проверены конфликт версии, отсутствие чужой истории/памяти, Host/Origin/token, обязательный chat_id, закрытые private/static маршруты. public-only не раскрывает private title/goal/вопрос/ответ/trace ни из state, ни из архива, ни из одиночного результата; загрязнённый результат не позволяет feedback или повтор ask.

## Реальный браузер и JavaScript

Playwright MCP/Chromium использовал настоящие HTML/CSS/JS и HTTP, синтетический preview на 127.0.0.1:8053; отдельный public-only на 8054. Preview явно помечен в странице «СИНТЕТИЧЕСКАЯ ОФЛАЙН ПРОВЕРКА»; поиск/провайдер/ключ/usage фиктивные, настоящие requests и subprocess/SSH запрещены runner. Данные находились в `/tmp/day25-t4-offline-fixture` и `/tmp/day25-t4-public-fixture`, не в приложении.

- `app/browser_checks.js`: PASS создание чата, память v1, два вопроса/продолжение, открытие источника, явные цитаты, безопасный `<script>` из текста документа (window.pwned отсутствует), refresh без увеличения mock счётчиков, создание/переключение второго чата без чужой памяти, no_context и unverified без успешного answer, очистка v2 и новая память v3. Browser page errors: 0.
- `app/browser_pending_checks.js`: PASS refresh после отправки POST до ответа. Число mock searches увеличилось 10 → 11, generations 8 → 9: ровно один поиск/вызов. Новый POST при восстановлении не делался.
- Настоящий stop/start собственного preview-процесса с тем же каталогом, затем browser reload: PASS выбранный чат, пять реплик и goal «Учиться короткими шагами» сохранились. Mock счётчики 5 searches/4 generations до и после чтения совпали. Это отдельная проверка от простого создания нового Service в unittest.
- `app/browser_public_checks.js`: PASS приватный чат и загрязнённый private:note результат отсутствуют в DOM/полной диагностике. Создание/ask в public-only использовали scope=public и chat_id. PUBLIC fixture имеет синтетический private title/goal и PRIVATE_ONLY_ маркеры для проверки; ни один не попал в страницу.
- Дополнительно через браузер: feedback сохраняется после reload; конфликт версии памяти показывает понятную ошибку и оставляет несохранённую правку в форме. Mobile отправка делает ровно один новый mock search/generation.

## Визуальный просмотр

Просмотрены desktop1280×800, tablet768×1024 и mobile375×812. Горизонтального переполнения документа нет на tablet/mobile. Sidebar становится компактным списком над чатом; ответ, источники и цитаты читаются на телефоне. Исходный тёмный стиль Day24 сохранён; текст о самостоятельных вопросах заменён объяснением продолжений и памяти.

Артефакты, все с синтетическими данными:

- [Desktop](t4-desktop.png)
- [Mobile — начало страницы](t4-mobile.png)
- [Mobile — ответ и цитата](t4-mobile-answer.png)
- [Public-only](t4-public.png)

## Границы

Реальных SSH/модельных вызовов и расходов: 0. Mock usage/cost не являются реальным расходом. Смысловая оценка, два длинных разговора на провайдере и сдаваемое видео относятся к T5 и не подтверждены T4. Browser localStorage хранит только выбранный чат и незавершённый ID, без токена и текстов. Refresh восстанавливает чтение запроса; сервер сохраняет прежний запрет автоматического повтора неизвестного платного исхода. В редакторе списков одна строка соответствует одной записи.
