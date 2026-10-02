# Day21 — индексация документов

Две стратегии нарезки одного корпуса → Qwen3-Embedding 0.6B → два SQLite-индекса.
Python 3.12+, Linux/macOS. Код сборки идентичен проверенному на VPS.

## Состав

- index_pipeline.py — Fixed (400 токенов, overlap 60), Structure, эмбеддинги, сохранение и возобновление сборки.
- inspect_index.py — проверка готовой пары без вызовов модели.
- corpus.py — импорт и версионирование Telegram-материалов, ручные решения отбора.
- smoke_embed.py — отдельная проверка локального эмбеддера на нейтральном тексте.
- test_*.py — проверки на синтетических данных; не заменяют реальный запуск модели.
- example-documents.json — искусственный пример формата входа; не учебный корпус.
- RESULT.md — агрегаты реального запуска.

Приватные переписки, исходный корпус, индексы, модель и токенизатор не включены.
Архив содержит основной код Day21; проектные эксперименты облачного отбора не входят.

## Установка и офлайн-тесты

Команды из распакованной папки day21:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
mkdir -p private
chmod 700 private
.venv/bin/python test_corpus.py
.venv/bin/python test_index_pipeline.py
.venv/bin/python test_inspect_index.py
```

## Новая сборка на своих данных

Нужны локальный Ollama 0.17.7 с qwen3-embedding:0.6b, JSON документов и tokenizer.json
модели Qwen/Qwen3-Embedding-0.6B. Проверенная ревизия токенизатора:
97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3;
SHA256 tokenizer.json: def76fb086971c7867b829c23a26261e38d9d74e02139253b38aeb9df8b4b50a.
Векторы: 1024 координаты; truncate=false. Вызовы эмбеддера только на loopback.

```sh
.venv/bin/python index_pipeline.py --help
.venv/bin/python index_pipeline.py \
  --documents example-documents.json \
  --tokenizer /path/to/tokenizer.json \
  --tokenizer-revision 97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3 \
  --tokenizer-sha256 def76fb086971c7867b829c23a26261e38d9d74e02139253b38aeb9df8b4b50a \
  --model-digest ac6da0dfba84a81fdbfbaf330198c33cd77c4cdfc53e8bc50eb581914a15621d \
  --root ./private/example-index --build
.venv/bin/python inspect_index.py --root ./private/example-index
```

Замените путь к токенизатору. Digest должен соответствовать установленной модели;
автоматическая подмена запрещена. Без --build выполняется подготовка Fixed без модели.
Новый запуск example-documents.json демонстрирует механизм, но не воспроизводит метрики приватного корпуса.
Не пересобирайте уже готовую пару ради просмотра: используйте inspect_index.py.

## Ограничения

Fixed может разрывать слова на границах токенов; overlap не гарантирует законченности мысли.
Structure сохраняет помещающиеся связи вопрос–ответ и использует структуру документа.
Результаты не доказывают точность поиска: поиск и ответы RAG относятся к Day22.

## Демонстрация

[Видео Day21](video/Day21-demo.mp4) — 90 секунд, без звука. Видеопрезентация кода и агрегатов реальной сборки; приватных сообщений нет.
