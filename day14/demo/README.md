# Видео дня 14

`record.py` сам проходит responsive-check и записывает немой WebM. Перед запуском
нужна чистая локальная БД и офлайн-панель:

```bash
preview_dir=$(mktemp -d /tmp/day14-preview.XXXXXX)
uv run python day14/web.py --db "$preview_dir/day14.db" --port 8044
/opt/anaconda3/bin/python day14/demo/record.py http://127.0.0.1:8044
```

Итог: `day14-invariants.webm`; визуальные доказательства — в `../results/`.
