# TimeWeb Uplink Monitoring: локальный master

Код, конфигурационные кандидаты и датированные evidence. Этот каталог не
является подтверждением запущенного runtime. Пользовательская документация:

- [Текущий статус и Pilot Quick Guide](<../../../docs/operations/TimeWeb_Uplink_Pilot_Quick_Guide.md>)
- [Состав и оставшаяся приемка](<../../../docs/architecture/TimeWeb_Uplink_Monitoring_Architecture_and_Plan.md>)
- [Guards](<../../../docs/operations/TimeWeb_Uplink_Guards_Quick_Guide.md>)
- [History sync](<../../../docs/reference/TimeWeb_Uplink_History_Sync_Plan.md>)

## Текущий статус

При любом изменении состава тоннелей обязателен
[monitoring completion gate](<../../../docs/operations/agent-workflow.md#обязательный-gate-мониторинга-при-изменении-тоннелей>):
inventory, точный diff обоих контрактов (BTH и monitoring), согласованные
generation/helper hashes, два новых валидных цикла и проверка Grafana.
Запущенный exporter и target UP не являются подтверждением валидности проб.

2026-09-27: после добавления Mac Mini FLEX monitoring baseline не включал
четыре RPDB-правила peer `10.50.50.41` и table 414, поэтому collector
отклонял измерения с `helper_pre_manifest_invalid`. Проверен точный diff;
manifest обновлен до generation 10, batch helper допускает только точные
FLEX defaults через Fornex/Cenuta для tables 410/412/414. Закрепленный hash
batch helper синхронизирован; collector/exporter перезапущены. VPN-маршруты
не изменялись. Проверка и ограниченное обновление:
`pilot/audit_macmini_manifest.py`. Backup на TimeWeb:
`/var/backups/vpn-monitoring-manifest-20260927T060359Z/`.
Цикл 06:06 UTC подтвердил оба направления UP: HTTPS gstatic/cloudflare,
DNS UDP/TCP и peer ICMP успешны, handshake и byte counters снова доступны.

2026-09-23: после добавления универсального SOCKS-TW-FLEX pilot начал
отклонять циклы с `helper_pre_manifest_invalid`: guard baseline не содержал
четыре RPDB-правила FLEX и маршруты tables 410/411. Точный live diff был
проверен до обновления manifest. Generation 9 сохраняет строгую проверку
остального snapshot; для переключаемого table 410 разрешены только точные
маршруты через Fornex `wg1` или Cenuta `wg-up-cenuta`. После замены batch
helper обновлен его закрепленный SHA-256 в pilot config; иначе collector
отклонял цикл как `helper_revision_changed`. Слот 09:54 UTC прошел,
Prometheus получил `vpn_uplink_probe_valid=1` и `reason=ok` для обоих
направлений. Менялись только мониторинговые manifest/helper/config и
pilot service; маршруты VPN не переключались. Backup исходных файлов на
TimeWeb: `/var/backups/vpn-monitoring-manifest-20260923T094526Z/original/`.
Промежуток без проб нельзя восстановить из обычного scrape Prometheus.

2026-09-14: collector/exporter запущены, пять циклов Cenuta/Fornex UP,
120 s / 7 дней, SQLite OK, guards generation=8. Autostart disabled.
Evidence: acceptance (source reference not migrated).
BTH принимает два точных RPDB inventory; маршруты клиентов не изменены.
SQL sync и локальные сервисы Mac этим шагом не запускались.

### Исторический снимок 13 сентября

Sanitized snapshot (source reference not migrated),
`time_utc=2026-09-13T14:45:01.429720+00:00`:
оба TimeWeb units `vpn-uplink-pilot.service` и
`vpn-uplink-exporter.service` имеют `inactive / dead / disabled`.
Значение preset `enabled` в отдельном списке units не означает автозапуск.

Каталоги `/var/lib/vpn-uplink-guards` и `/var/lib/vpn-uplink-pilot`
существуют. Guard rules/generation, SQLite integrity, coverage и последний
цикл снимком не проверены. «Установлено 11 сентября» не означает «работает сейчас».

На Mac аудит не обнаружил TCP listeners на проверенных портах
3000, 9090, 9105, 19106; порт 19107 не проверялся.
**Пустой `local_docker` не доказывает отсутствие контейнеров:** audit берет
только `.stdout` от `docker ps -a`, игнорирует subprocess returncode
и не сохраняет stderr. Ошибка CLI/daemon неотличима от пустого списка.
В отфильтрованном launchd-списке monitoring agents не показаны;
наличие файлов plist не проверено.
`command missing` / exit 127 означает ошибку диагностики, не отказ VPN.
Новых live-проверок и запусков в документационном ревью не было.

## Master и установленная копия

Master находится в этом дереве Dropbox. Серверная копия пилота по протоколу
2026-09-11 размещалась в `/opt/vpn-monitoring/pilot`;
разовый guard helper в `/opt/vpn-monitoring/guards`.
Совпадение с сегодняшним сервером требует новой SHA-256 сверки.

- `guardctl.sh`: apply/check/probe/точный rollback собственных 22 IPv4 rules.
  Его наличие не доказывает активный guard layer.
- `guard-manifest.json`: snapshot конкретного boot/container/netns и ownership.
  Не универсальная повторно применимая конфигурация.
- `probe-targets.json`: исторический ограниченный по TTL snapshot.
- `candidate/guardctl-batch.sh`, `candidate/batch_probe.sh`: отдельный batch
  helper пилота, ограниченное RTNL/pre-post покрытие; не замена разового helper.
- [collector](<collector/README.md>): daemon, adapter, модель состояний,
  SQLite, exporter и candidate history-cache/sync.
- [pilot](<pilot/README.md>): installer/updater, units, config, SSH LaunchAgent
  и исходник dashboard. Это инструменты изменения runtime, не read-only проверки.
- `collector/config.candidate.json`: запуск по умолчанию запрещен;
  `pilot/config.json`: отдельный явный pilot, не production acceptance.
- `collector/tests/`: исходники тестов, не свежий отчет об их прохождении.
- `evidence/`: датированные проверки, synthetic fixtures и replay.
  Историю тестового replay не смешивать с реальной историей мониторинга.

## Интервалы и данные

Master: цикл **120 s**, deadline **45 s**, stale **180 s**.
Pilot config: `retention_days=7`; очистка после цикла.
Остановленный collector не записывает новые наблюдения и не выполняет prune.
Хранилище может содержать более старые данные; 7 дней не равны hard quota
или гарантированному coverage.

Local Prometheus scrape TimeWeb: **30 s**; dashboard refresh **10 s**.
Mac host probe имеет отдельный scrape **10 s** и локальный retention **30d**.
Серверный Prometheus не входил в развернутую схему пилота.
Prometheus на Mac не подкачивает пропущенную историю.

## Диагностика транспорта

В каждом batch `candidate/batch_probe.sh` берет снимки `wg show <interface>
transfer` до и после двух interface-bound HTTPS-проб. В Store сохраняется
только валидная неотрицательная дельта peer RX/TX; public key, payload и raw
вывод `wg` не сохраняются. Если в batch одна сторона имеет нулевую дельту, а
другая не менее 128 bytes, exporter публикует `vpn_uplink_wg_one_way_suspect=1`.
Это сопутствующая диагностика, а не сигнал изменения маршрута.

`vpn_uplink_selected_transport_info` отражает атомарное состояние ручных
контроллеров Fornex/Cenuta: `native` или `backup`. Карточки Grafana показывают
его в составе соответствующего upstream. Collector и exporter не запускают
`timeweb-*-wg-transport backup/native`; автоматический failover остается
отдельным будущим этапом.

History API/cache реализованы в master, но deployment/подключение Grafana
не подтверждены. Cache удаляет старые samples при успешной синхронизации,
не постоянно offline. Диапазон API и срок реально доступных данных различаются.

## Изменения и ограничения

Сначала согласовать scope, изменить локальный master, проверить, затем отдельно
развернуть выбранные файлы и сверить hashes. Не переносить аварийные серверные
правки поверх local master без diff. Runtime-state не редактировать как config.

`apply_live.sh`, `build_manifest.py`, `finalize_manifest.py`,
`confirm_guard_layer.sh` и датированные timers не являются универсальными
повторными installer/recovery-командами. `verify_live.py` и SSH runners
обращаются к серверу; lab/canary/probe создают трафик и могут менять стенд.
Даже guard `check` открывает lock/state directory.

Production gate остается закрыт: WG/firewall ABA не покрыт универсально,
клиентская приемка, backup/restore, долгий baseline и history-sync не завершены.
Root в SSH-шаблоне и отсутствие `User=` в exporter unit не соответствуют
прежнему обещанию полностью непривилегированного мониторинга.

Живую серверную SQLite держать вне Dropbox. Согласованные backup/evidence
можно хранить в System. При этом существующий Mac Compose в соседнем
`vpn-connectivity` все еще использует live `./data` под Dropbox:
перенос не выполнен этим ревью. Секреты и полные VPN-конфиги не публиковать.

Python-проверки на Mac: только `python3 -B`.
