# Пилот TimeWeb uplinks

## Статус

2026-09-15: пилот работает, production-приемка не завершена.
`vpn-uplink-pilot.service` и `vpn-uplink-exporter.service` имеют
`active / enabled`; loopback `/readyz` подтвердил доступность SQLite, текущие
метрики Cenuta/Fornex имеют `state=1`, `observation_fresh=1`, `reason=ok`.
Точечный rollout затронул только collector batch и его config; два следующих
120-секундных слота завершились `UP / ok`. Evidence (source reference not migrated).

### Историческое состояние 13 сентября

**Пилот остановлен, не принят в production.**
Live snapshot (source reference not migrated)
от **2026-09-13 14:45:01 UTC**: оба units
`vpn-uplink-pilot.service` и `vpn-uplink-exporter.service`
имеют `inactive / dead / disabled`.
Наличие каталогов состояния не подтверждает сохранность и полноту SQLite.

Установка, API/Prometheus/Grafana и реальные короткие пробы 2026-09-11
относятся к прошлому:
[протокол](<../../../../docs/history/TimeWeb_Uplink_Pilot_Deployment_2026-09-11.md>).
Актуальная инструкция:
[Pilot Quick Guide](<../../../../docs/operations/TimeWeb_Uplink_Pilot_Quick_Guide.md>).

Локальный аудит не обнаружил TCP listeners на проверенных портах
3000, 9090, 9105, 19106. Пустой `local_docker` не доказывает отсутствие
контейнеров: subprocess returncode проигнорирован, stderr не сохранен.
Monitoring LaunchAgents в отфильтрованном списке не показаны,
порт 19107 не проверен.
Отсутствие диагностической команды не является отказом VPN.

## Содержимое и master-параметры

- `config.json`: явный `deployment_mode=pilot`,
  `allow_snapshot_scope=true`, `retention_days=7`. Для Cenuta и Fornex включен
  ограниченный `native -> WSS` failover: два подряд валидных full HTTPS
  failures, handshake старше 180 s, healthy независимый upstream/direct control
  и peer ICMP failure или `wg_one_way_suspect`. Автовозврата на native нет.
- `vpn-uplink-pilot.service`: state в `/var/lib/vpn-uplink-pilot`,
  server Python в `/opt/vpn-monitoring/pilot/.venv`.
- `vpn-uplink-exporter.service`: loopback `127.0.0.1:19106`,
  read-only SQL. В unit нет `User=`; не называть процесс непривилегированным.
- Collector limits: `MemoryMax=160M`, `CPUQuota=30%`;
  exporter: `MemoryMax=64M`, `CPUQuota=10%`. Это конфиг, не live-замер.
- Цикл **120 s**, deadline **45 s**, stale **180 s**;
  Mac scrape **30 s**, dashboard refresh **10 s**.
- SSH LaunchAgent template делает loopback forward 19106 -> 19106 и использует
  root destination. Отдельный ограниченный forwarding-user здесь не реализован.
- Dashboard `TimeWeb Uplinks - Pilot` читает существующий Mac Prometheus.
  Серверный Prometheus и Docker SSH-proxy не входили в эту схему.

Пилот не закрывает WG/firewall ABA. Обычный production gate запрещает запуск;
ограниченный режим требует также `--pilot`.
Наличие startup template не означает, что агент загружен или API доступен.

## История

Серверная retention **7 дней** применяется после цикла, не является hard quota.
При отключенном collector не идет ни сбор, ни prune.
При работающем collector отсутствие Mac не мешает серверной записи, но
Mac Prometheus не подкачивает пропущенные точки.
`30d` локального Prometheus не меняет срок TimeWeb SQLite.

History-sync уже реализован как local candidate, не «только спроектирован».
`deploy_sync.py` создает cache/LaunchAgent после server backup/update,
но успешный deployment и datasource Grafana не подтверждены:
[History Sync Plan](<../../../../docs/reference/TimeWeb_Uplink_History_Sync_Plan.md>).

Историческая синтетика `../evidence/20260911-retention-7d/`:
4 915 200 байт за 7 модельных суток. Резерв 50 MiB оценочный,
не quota или подтвержденный объем за неделю эксплуатации.

## Перед будущим изменением runtime

Все deploy/update/bootstrap/verify scripts требуют отдельного согласованного
операционного scope; их нельзя запускать как способ прочитать статус. В
stability rollout 15 сентября выполнены только `update.py` и read-only
`verify.py`; bootstrap, deploy и history-sync не запускались.

`update.py` передает только утвержденный inventory collector batch, сохраняет
локальный server backup и перезапускает только collector. Он намеренно не
заменяет `storage.py`, `exporter.py`, units, guards, маршруты, firewall или WG.
Единственное действие auto-failover - запуск allowlisted endpoint controller
соответствующего upstream; сам модуль не редактирует сеть.

Сначала свежий namespace/guards audit, проверка истории/backup и SHA master
против установленной копии. Не применять старый manifest после reboot/recreate.
Рабочие WG, routes и клиентские конфиги не перезапускать ради пилота.

## Loopback operator console

`vpn-uplink-console.service` - отдельная stdlib HTTP-служба на
`127.0.0.1:19108`; публичный listener, Docker, CDN и внешняя база не
используются. На Mac с настроенным SSH-профилем `timeweb-console` консоль
открывается одной командой:

```bash
timeweb-vpn
```

`pilot/open_console.sh` использует существующий SSH-профиль и его `LocalForward`,
проверяет ответ именно консоли TimeWeb, затем открывает браузер. Повторный
запуск переиспользует работающий туннель; `timeweb-vpn status` проверяет
доступность, `timeweb-vpn stop` останавливает только туннель, запущенный этим
скриптом.
Запуск/status выводят этапы, PID/PPID/elapsed и принадлежность соединения.
SSH запускается через `-fN` и остается в фоне после выхода launcher; повторный
start явно сообщает reuse без нового SSH. `timeweb-vpn logs` показывает
последние сообщения из `.local/runtime/timeweb-vpn/launcher.log` (mode 600).
Для установки короткой команды на другом Mac создать ссылку на
синхронизированный `open_console.sh` в локальном `~/.local/bin` (должен быть в
`PATH`). SSH-профиль и ключ на каждом Mac настраиваются отдельно; ключ не
копируется скриптом. Если порт занят, а консоль не отвечает, скрипт сообщает
об ошибке и не завершает чужой SSH-сеанс. Страница показывает monitoring, handshake и Xray mode
для Cenuta и Fornex. Переключатель `Backend transport` выбирает UDP/WSS сразу,
без дополнительного подтверждения; состояние переключателя меняется только
после проверенного server-side read-back. Во время команды управление блокируется.
Если режим не подтверждён, причина ошибки записывается в audit log и Recent
commands, а сообщение в карточке держится не менее 10 s. Адреса и обычное состояние failover раскрываются
через `Details`; значимый failover event остается видимым в карточке. Ниже
находится FLEX route для MacBook. Статус читается через `GET /state`
в фоне каждые 15 с без перезагрузки страницы; незавершенный выбор Exit и
RU-direct в форме сохраняется. Под карточками выводятся последние шесть
записей audit log с UTC timestamp, запрошенным действием и подтвержденным
результатом. Результат POST больше не остается постоянным баннером: после
команды страница переходит к истории. Доступны фиксированные действия
`native` и `backup` для каждого upstream и allowlisted FLEX exit/RU mode.
POST защищен same-origin проверкой и per-browser CSRF token;
команды выполняет исключительно точный controller path, без shell/параметров
из формы. Каждое действие записывается в
`/var/lib/vpn-uplink-pilot/console-actions.jsonl` с правами `0600`.

Если согласованное изменение транспорта добавляет route, peer, адрес или
firewall в namespace `wg-relay`, строгий guard manifest остановит pilot до
reviewed baseline update. Требуются: доказанный точный diff, backup manifest и
ownership state, атомарная замена обоих при остановленном только pilot, затем
`guardctl ... check` и подтверждение свежей SQLite/exporter записи. Удалять
state или ослаблять проверку нельзя. Для WSS fallback Fornex baseline содержит
`103.75.126.143/32 via 172.19.0.1 dev eth0`, чтобы сессия WSS не маршрутизировалась
через `wg1` рекурсивно.

Инцидент 2026-09-23 после FLEX показал вторую обязательную часть rollout:
при изменении `candidate/guardctl-batch.sh` обновить закрепленный
`helper_sha256` в pilot config и сверить его с установленным файлом.
Иначе guard `check` может быть валиден, но collector откажет с
`helper_revision_changed`. FLEX table 410 допускает два точных маршрута
(Fornex или Cenuta); все остальные поля baseline остаются строгими.

Исторические installation lessons, не команды повторного запуска:

- Linux `.venv` не копировать с Mac; app/pip используют согласованную server env.
- Перед повтором неуспешной установки выяснять состояние своего удаленного процесса;
  локальный SSH timeout сам по себе не доказывает завершение удаленного installer.
- Архив с Mac не должен оставлять UID 501 вместо ожидаемого root-owned deployment.
  Не ослаблять ownership validation.
- SQLite WAL reader может требовать служебные файлы; `ReadWritePaths` каталога
  состояния в exporter unit не разрешает SQL write и не делает процесс непривилегированным.
- Не удалять locks, volumes или историю; не заменять живой VPN конфигурацией из backup.

Mac Python в этом ревью только `python3 -B`.
Существующие wrappers/units не переписывались. Runtime и зависимости не менялись.
