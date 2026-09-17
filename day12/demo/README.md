# Видео дня 12

`day12-mass-replay.webm` — итоговое видео из сохранённого отчёта 24 реальных
вызовов. При записи сеть браузера заблокирована, поэтому replay не вызывает модель
повторно. Видео показывает все ответы, request ID, стоимость, deterministic
predicates, семь `quality_fail` и финальную сводку с restart evidence.

[Смотреть видео на Google Drive](https://drive.google.com/file/d/1dfeolXiyUC1thOaVCHYea_YMXdMR8co4/view?usp=sharing).

- длительность: 68,72 с;
- VP8, 1280×800, 25 fps;
- SHA-256: `9e9ce77d5a3ae811949f01a6bd6ba7d99e8a91d2a2fc67ed888297b7fb49a72b`;
- отчёт просмотра: `../results/mass-live/day12-mass-01/video-report.md`.

Воспроизвести из `day12/` без новых API-вызовов:

```sh
node demo/record.cjs results/mass-live/day12-mass-01/report.json
```
