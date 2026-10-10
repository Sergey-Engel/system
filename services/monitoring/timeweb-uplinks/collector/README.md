# Collector: локальный master

2026-09-16: серверные collector/exporter `active` и `enabled`; loopback
`/readyz` вернул storage `ok`, а текущие метрики Cenuta/Fornex имеют
`state=1`, `observation_fresh=1`, `reason=ok`. Batch фиксирует WG peer
счетчики до/после привязанных HTTPS-проб; exporter публикует абсолютные и
delta RX/TX, а также `one_way_suspect` как диагностический, не управляющий
сигнал. Подтвержденный rollout: evidence (source reference not migrated).
`storage.py` не изменяется этим updater; exporter перезапускается при замене
своего модуля, иначе он продолжает обслуживать старый импортированный код.

## Исторический снимок 13 сентября

Текущий статус:
[TimeWeb Pilot Quick Guide](<../../../../docs/operations/TimeWeb_Uplink_Pilot_Quick_Guide.md>).
Снимок (source reference not migrated) от
**2026-09-13 14:45:01 UTC** подтверждает collector/exporter TimeWeb
`inactive / dead / disabled`. Каталог состояния существует; содержимое
истории и совпадение установленного кода с master не проверены.

Исторический запуск 2026-09-11, SHA-сверки и прошлые test reports не являются
текущим working-state. Production-приемка не завершена.

## Контракт master

- `timing.py`: **120 s** interval, **45 s** deadline, **180 s** stale.
  Старые fixtures сохраняют собственную timing policy; v1 DB только читается.
- `daemon.py`: scheduler, TTL-aware DNS refresh и durable state. DNS TTL
  допускает только старт batch; ошибка сохраняется как `UNKNOWN`, а следующий
  слот не пропускается. Не восстанавливает guards и не меняет VPN.
- `adapter.py`: фиксированный batch-helper, hashes, manifest/targets validation.
- `model.py/state.py`: три полных валидных отказа подтверждают outage,
  два available-цикла закрывают его; UNKNOWN прерывает сегмент.
- `storage.py`: атомарная пара upstream, таблицы
  `channels/cycles/incidents/gaps/settings/daily`. Retention по умолчанию
  **7 дней**; daemon берет `retention_days` из config и вызывает prune после цикла.
- `exporter.py`: loopback HTTP, запросы не запускают сетевые пробы.
  Stale health/storage error может дать HTTP 503 вместо JSON UNKNOWN.
  Выдает выбранный transport, WG peer counters/deltas и one-way diagnostic;
  не вызывает контроллеры WSS и не меняет endpoint WireGuard.
- `history_export.py/history_cache.py/sync_daemon.py`: реализованный
  candidate sync; успешный deployment и Grafana integration не подтверждены.

Обычный production-запуск закрыт. Пилоту одновременно нужны `--pilot`,
`deployment_mode=pilot` и `allow_snapshot_scope=true`.
Это ограниченный `rtnl_and_snapshots` режим, не универсальная гарантия WG/firewall ABA.

## API и история

- `/healthz`: HTTP-процесс, не VPN.
- `/readyz`: storage/health, не сетевой успех.
- `/metrics`, `/api/current`: последние наблюдения при готовом storage.
- `/api/summary?from=<Unix ms>&to=<Unix ms>`: coverage/availability по доступным слотам.
- `/api/incidents?from=<Unix ms>&to=<Unix ms>&upstream=cenuta`:
  upstream требуется текущей реализацией; есть `offset`.
- `/api/sync?after=<slot>&limit=100`: candidate export до 100 циклов/200 строк.

Summary/incidents ограничивают запрос 30 днями; это не серверная retention.
При выключенном daemon prune не выполняется и новых циклов нет.
Нулевой coverage дает отсутствие данных, не 100% availability.
Cache API истории ограничен 7 днями, удаляет samples при успешном apply,
не по отдельному offline-таймеру.

Полный контракт, ограничения UUID/metadata и открытые тесты:
[History Sync Plan](<../../../../docs/reference/TimeWeb_Uplink_History_Sync_Plan.md>).

## Что не доказано

Local master поддерживает больше модельных признаков, чем реально собирает
batch. Не считать автоматическую сверку public egress IP, всю WG telemetry
или `local_service_down` принятой live-функцией по одной функции модели.
HTTPS проверяет curl/TLS и ожидаемый HTTP-код, но не body.
DNS batch использует source bind, не тот же interface bind, что HTTPS.

Synthetic replay, fixture DB и 43/50/78/83-test исторические отчеты не являются
непрерывной production-историей. В текущем ревью тесты и `verify_live.py`
не запускались.

Python на Mac: `python3 -B`.
Серверный Python исторического пилота:
`/opt/vpn-monitoring/pilot/.venv/bin/python`.
Runtime-файлы и зависимости этим документационным ревью не менялись.
