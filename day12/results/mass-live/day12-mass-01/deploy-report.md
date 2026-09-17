# VPS smoke после массового live eval

Проверено 2026-09-16 после завершения всех 24 cases.

- `day12.service` active; PID 2931227; InvocationID
  `ae4bb30bea65468e81d3a3678272c3dc`.
- Порты 8035 и 8036 слушают только `127.0.0.1`.
- Публичные `/` и `/api/state` отвечают 200; POST к chat, profile, memory, reset и
  campaign отвечает 403.
- Прямое подключение извне к 8035 и 8036 недоступно (connect timeout).
- SQLite `PRAGMA integrity_check` вернул `ok`.
- Ledger: sent=24, stopped=null, restart=`restart_verified`; SHA-256 VPS ledger
  `b2cfabcf12685b7e5811bd374d015ce83b70d6a4ffa6651355103cf268fa1662`.
- Raw restart evidence SHA-256:
  `cd0fb16167d7ca703ae5134c28da01a43f1682e8587d6cb2032349e16b55bed3`.
- Локальные неизменяемые копии raw evidence приложены рядом с отчётом:
  `mass-preflight-network.txt` (`efc27acd…e2ea`),
  `mass-provider-metadata.json` (`a7e4ead9…2ae2`) и
  `mass-restart-raw.txt` (`cd0fb161…bed3`); hashes совпадают с VPS gate.
- Соседние сервисы и firewall проверены до кампании и сразу после рестарта;
  кампания не меняла их конфигурацию.

Платный endpoint публично не опубликован: управление возможно только через
локальный SSH-туннель на loopback-порт 8036.
