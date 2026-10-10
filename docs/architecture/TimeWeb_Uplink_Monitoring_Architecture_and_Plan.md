---
type: architecture
topic: timeweb-uplink-monitoring
status: running-pilot-not-production-accepted
created: 2026-09-11
updated: 2026-09-23
resource_check_utc: "2026-09-11T06:31:42Z"
tags:
  - timeweb
  - wireguard
  - monitoring
  - prometheus
  - grafana
---

## Статус и источники

**Текущий статус: пилот работает, production-приемка не завершена.**
Каноническая краткая сводка: [TimeWeb_Uplink_Pilot_Quick_Guide](<../operations/TimeWeb_Uplink_Pilot_Quick_Guide.md>).
**2026-09-23 09:54 UTC:** после добавления FLEX-маршрута восстановлен сбор
TimeWeb: новый цикл для Cenuta/Fornex записан, в Mac Prometheus
`vpn_uplink_probe_valid=1`, `reason=ok`. Предшествующие циклы отклонялись
сначала как `helper_pre_manifest_invalid` из-за новых RPDB/routes FLEX вне
guard baseline, затем как `helper_revision_changed` из-за старого pinned SHA
batch helper. Guard generation 9 включает точные новые правила и маршруты;
для table 410 разрешены только два точных направления FLEX (FX/CEN), остальные
части snapshot проверяются строго. Изменения затронули только мониторинг,
транспорт VPN не переключался. Исторический пробел в Prometheus не заполнен.
На **2026-09-15 06:25 UTC** оба units `active / enabled`; loopback exporter
вернул storage `ok`, а текущие метрики обоих uplink имели `state=1`,
`observation_fresh=1`, `reason=ok`. После точечного rollout два плановых
слота (`06:22` и `06:24 UTC`) записаны как `UP / ok`.

В историческом live snapshot (source reference not migrated)
от **2026-09-13 14:45:01 UTC** оба units
`vpn-uplink-pilot` и `vpn-uplink-exporter` имеют
`ActiveState=inactive`, `SubState=dead`, `UnitFileState=disabled`.

Старый план целиком сохранен, включая исходные T01-T35, расчеты ресурсов,
варианты размещения и прежние результаты:
[agents/history/TimeWeb_Uplink_Monitoring_Architecture_and_Plan_Before_Review_2026-09-13](<../history/TimeWeb_Uplink_Monitoring_Architecture_and_Plan_Before_Review_2026-09-13.md>).
Это исторический материал, а не продолжение текущего runbook.
Поле `resource_check_utc` выше тоже историческое: запас ресурсов 11 сентября
не переносится автоматически на 13 сентября.

Различать три вида основания:

1. **Live snapshot:** состояние конкретных units и наличие каталогов на время снимка.
2. **Локальный master:** реализованный контракт, defaults, units и dashboard;
   не доказательство развертывания и не совпадение SHA с сервером сегодня.
3. **Датированная история:** установка, лабораторные тесты, разовые успешные
   пробы и synthetic replay; не текущий uptime и не полная приемка клиентов.

Исходный аудит 14:45:01 UTC не обнаружил TCP listeners на проверенных портах 3000, 9090, 9105,
19106; порт 19107 не проверялся. Это наблюдение только на время снимка.
Пустой `local_docker` не доказывает отсутствие контейнеров: `audit.py`
сохранил только stdout `docker ps -a`, проигнорировав returncode и stderr.
Monitoring LaunchAgents не показаны в отфильтрованном списке; это не проверка
их файлов на диске. Ошибка отсутствующей команды означает неполноту
диагностики, а не DOWN. Подробные ограничения снимка приведены в Quick Guide.

В дополнении (source reference not migrated)
от **2026-09-13 15:19:59 UTC** `lsof` проверил TCP LISTEN на
**3000, 9090, 9105, 19106, 19107**: `rc=1`, stdout/stderr пусты,
listeners на этих портах не обнаружены. `docker ps -a` вернул `rc=1`
из-за отсутствующего сокета `~/.docker/run/docker.sock`; список контейнеров
не получен, их отсутствие не доказано. Это отдельная локальная проверка,
не отмена ограничений исходного аудита и не повторная проверка units TimeWeb.

## Назначение и разделение контуров

Пилот оценивает **IPv4 HTTPS egress с TimeWeb через Cenuta/Fornex**.
Он не оценивает весь путь клиента, текущую REALITY-схему, Apple TV, браузер,
DNS-утечки, IPv6, fail-closed или качество UDP-медиа.

Mac-monitoring проверяет запросы самого Mac по его текущему маршруту:
[VPN_Connectivity_Monitoring_Architecture](<VPN_Connectivity_Monitoring_Architecture.md>).
Два контура используют одну локальную Grafana, но не одну семантику проб.

Историческое сопоставление пилота: Cenuta через `wg-up-cenuta` / table 200,
Fornex через `wg1` / table 100 в namespace `wg-relay`.
Эти значения используются локальным master, но до возобновления требуют
новой проверки. Старый manifest привязан к конкретному boot/container/netns.
Нельзя считать конфигурацию REALITY новым именем того же проверенного пути.

## Фактически реализованный состав

- Master: [System/timeweb-uplinks](<../../services/monitoring/timeweb-uplinks/README.md>).
- Серверная копия пилота по протоколу 2026-09-11: `/opt/vpn-monitoring/pilot`.
  Python приложения: `/opt/vpn-monitoring/pilot/.venv/bin/python`.
- Collector: `collector/uplink_monitor/daemon.py`, `adapter.py`, отдельный
  `candidate/guardctl-batch.sh` и `batch_probe.sh`.
- SQLite/health: `/var/lib/vpn-uplink-pilot/`; exporter: loopback `19106`.
- Mac: SSH LaunchAgent, job локального Prometheus, dashboard
  `timeweb-uplink-pilot`. Шаблон туннеля использует root SSH, а не отдельного
  ограниченного forwarding-пользователя. Секреты здесь не приводятся.
- Кандидат подкачки: `history_export.py`, `history_cache.py`,
  `sync_daemon.py`, локальный API `19107`. Deployment не подтвержден.
- В units master нет `User=`: exporter не следует называть
  непривилегированным. SQL read-only и systemd-hardening не равны смене UID.

Серверный Prometheus, Docker SSH-proxy с портом 19090 и Infinity datasource
были прежним проектным вариантом. Они не являются установленной схемой пилота.
Не устанавливать их по архивному плану без нового решения.

## Интервалы и история

- TimeWeb: цикл **120 s**, deadline **45 s**, stale **180 s**.
- Mac scrape TimeWeb: **30 s**; refresh dashboard: **10 s**.
- Mac host probe: scrape **10 s**, timeout **8 s**; выполняет проверки
  по HTTP-запросу, а не по отдельному 120-секундному scheduler.
- TimeWeb SQLite: **7 дней**, очистка после цикла; не quota и не гарантия coverage.
- Mac Prometheus: **30d** в Compose. Пропуски scrape не подкачиваются.
- Локальный кандидат cache: удаляет старые samples при успешном apply;
  диапазон API истории до 7 дней. Offline очистка отдельным таймером не реализована.
- Legacy evidence с интервалом 10 s сохраняется с исходной timing policy.
  Legacy v1 DB только читается; нельзя дописывать 120-секундные циклы в чужую timing DB.

Без Mac серверная история могла накапливаться, пока collector работал.
**При отключенном collector новые измерения не возникают**, а retention-cleanup
не выполняется. Снимок подтверждает каталоги, но не файл, строки или
целостность SQLite. Отсутствие измерений не означает ни UP, ни сетевой DOWN.

API summary/incidents разрешает запрос до 30 дней, но coverage отражает
только доступные валидные 120-секундные слоты. Нулевой coverage означает
нет данных, не 100% availability. Число outage segments не обязательно равно
числу физических разрывов. UNKNOWN не заполняется соседним успехом.

## Валидность и классификация

Batch проверяет два независимых HTTPS target через оба uplinks и direct
TimeWeb control. Bound HTTPS использует `--interface if!...`, pinned IPv4,
SNI/TLS verification, без proxy и fallback без привязки.
Ответ direct control не подставляется вместо результата WG.

Helper проверяет identity/manifest, RTNL events и pre/post snapshot.
Это ограниченное `rtnl_and_snapshots` покрытие, не гарантия против всех
WG/firewall ABA. Полный production gate в master закрыт.

DNS refresh-loop в daemon уже реализован. Он не продлевает старый snapshot:
TTL допускает снимок DNS только к началу batch. После этого helper работает с
собственной неизменяемой копией не более 43 секунд; новый цикл с истекшим
снимком обязан выполнить новый DNS refresh. Если к старту нет валидной цели,
batch получает `UNKNOWN`; истекший snapshot не продлевается и не переиспользуется.
Разовый `guardctl.sh probe` и постоянный batch имеют разные контракты.
В batch DNS-диагностика использует `dig -b <source>`, не ту же привязку
сокета к интерфейсу, что HTTPS; ее путь требует отдельной приемки.

Три валидных полных отказа подтверждают DOWN; два available-цикла закрывают
эпизод. UNKNOWN сбрасывает последовательность и прерывает сегмент.
UP требует двух успешных независимых HTTPS-целей без предупреждений.
Старый handshake сам по себе не доказывает DOWN, свежий не доказывает UP.

Master проверяет curl exit/TLS и ожидаемый HTTP-код, но не содержимое
Cloudflare body и не внешний IP выхода: body отбрасывается.
`public_ip_match` поддерживается моделью, но текущий batch его не измеряет.
Поэтому автоматическую сверку egress IP нельзя объявлять реализованной.

### Диагностика одностороннего WG-трафика

Начиная с 2026-09-16 batch снимает `wg show <interface> transfer` до и после
двух привязанных HTTPS-проб. В exporter публикуются абсолютные peer-счетчики
и дельты `received/sent` за этот же защищенный batch. Счетчики не содержат
public key, payload или клиентские данные.

`wg_one_way_suspect` возникает только если в течение batch одна из дельт равна
нулю, а противоположная не менее 128 байт. Это **сопутствующий** признак, а не
доказательство блокировки: `PersistentKeepalive`, фоновый трафик и reset peer
могут исказить пассивные счетчики. При reset или некорректном выводе `wg show`
метрика отсутствует, а цикл остается валидным по своим HTTPS-правилам.

Внутренний peer ICMP (`10.20.0.2` / `10.40.40.1`) проходит внутри WireGuard и
не равен ICMP до публичного IP VPS. Он полезен для локализации, но не является
обязательным условием для будущего failover: ICMP может фильтроваться отдельно,
а прикладной путь может быть нарушен при ответах на ICMP.

## Автоматический failover Cenuta и Fornex

С 2026-09-16 `vpn-uplink-pilot.service` одинаково управляет Cenuta и Fornex:
после атомарного сохранения валидного batch он может вызвать строго
allowlisted controller соответствующего upstream:
`timeweb-cenuta-wg-transport backup` или
`timeweb-fornex-wg-transport backup`. Состояния раздельны, поэтому отказ
одного направления не сбрасывает подтверждение второго. Автоматика оценивает
только native режим и переключает только `native -> backup`; `backup -> native`
остается ручным.

Для действия одновременно требуются:

1. Два последовательных валидных batch с отказом обеих независимых HTTPS-целей,
   handshake старше 180 секунд, healthy противоположный upstream и healthy
   direct control.
2. Хотя бы один транспортный признак: отказ внутреннего peer ICMP
   **или** `wg_one_way_suspect` во время того же контролируемого batch.
3. Отсутствие cooldown: предыдущий переход был не менее 900 секунд назад.
4. При `UNKNOWN`, stale, неготовом WSS или невалидных guards не переключать,
   а фиксировать необходимость ручной проверки.

Состояние подтверждения и перехода хранится с правами `0600` раздельно в
`/var/lib/vpn-uplink-pilot/cenuta-auto-failover.json` и
`/var/lib/vpn-uplink-pilot/fornex-auto-failover.json`; в journal пишутся только
ограниченные события `cenuta_failover` и `fornex_failover`, без payload или
ключей. Controller сам проверяет WSS listener/carrier и peer ICMP. При неуспехе
он возвращает native UDP и не записывает backup mode.

Live acceptance 2026-09-16: частичный HTTPS-отказ дал `DEGRADED` без
переключения; изменение guard в `wg-relay` дало `UNKNOWN` без переключения;
полная блокировка native UDP дала один `awaiting_confirmation`, а второй
квалифицированный цикл переключил Cenuta на WSS. Отдельная блокировка WSS
подтвердила rollback controller в native UDP.

Для Fornex применен тот же failover state machine и unit-тест его отдельного
controller/state. На момент внедрения не выполнялись fault-injection тесты на
Fornex: разрешение на disruption было дано только для Cenuta. До отдельной
приемки Fornex подтверждены штатный native режим и отсутствие ложного
переключения, но не live-переход и rollback при искусственной аварии.

## Операторская консоль TimeWeb

Для ручной работы с транспортом развернута отдельная лёгкая loopback-консоль,
не заменяющая Grafana. На TimeWeb она слушает только `127.0.0.1:19108` и
открывается с рабочей машины через SSH local forward.

На настроенном Mac Mini используется SSH alias `timeweb-console`; он пробрасывает
локальный `127.0.0.1:19118` на серверный `127.0.0.1:19108`. Операционный запуск:

```sh
ssh -N timeweb-console
```

Пока команда работает, консоль доступна по
[http://127.0.0.1:19118](http://127.0.0.1:19118). Alias является настройкой
конкретной рабочей машины, поэтому на другой машине нужен эквивалентный
`LocalForward` или переносимая команда:

```bash
ssh -N -L 19108:127.0.0.1:19108 -o ExitOnForwardFailure=yes \
  -o PermitLocalCommand=yes \
  -o 'LocalCommand=printf "\\nConsole ready: http://127.0.0.1:19108\\n"' \
  root@94.241.171.65
```

Панель читает SQLite/state контроллеров и может
вызвать только фиксированные `native` или `backup` команды для Cenuta/Fornex.
Локальный порт допустимо заменить при конфликте с другой программой: это не
меняет защищённый server-side listener `127.0.0.1:19108`.
Произвольные shell-команды, редактирование WG, firewall и маршрутов через UI
не предусмотрены. `POST` требует same-origin и CSRF token, а действия пишутся
в ограниченный audit log. Grafana остаётся источником исторических графиков;
консоль показывает оперативное состояние и точку ручного переключения.

Prometheus регулярно считывает exporter TimeWeb и хранит временные ряды;
Grafana отображает их в dashboard `TimeWeb Uplinks - Pilot`. Они не принимают
решений о ручном переключении: `NO DATA` означает отсутствие отображаемых
метрик, а не подтверждённый сетевой отказ. Для текущего режима транспорта
используется консоль, для анализа динамики и разрывов — Grafana.

Ручной controller сначала проверяет namespace-local listener и обходной маршрут
WSS carrier. Затем он направляет peer endpoint на local UDP listener и требует
успешный bound ICMP probe до внутреннего peer при сохранении local endpoint.
Требование нового WG handshake здесь ошибочно: уже установленная WG-сессия
может передать probe без нового handshake. При неуспехе controller обязан
вернуть native endpoint и остановить WSS client. TLS certificate verification
остается включенной; private CA WSS-сервера устанавливается в system trust
store TimeWeb через `update-ca-certificates`.

Изменение namespace, storage error, отсутствие команды и невозможность
прочитать состояние относятся к недостоверности наблюдения.
Библиотечная поддержка `local_service_down` не доказывает, что live adapter
отдельно распознает остановленный контейнер: отказ manifest может дать UNKNOWN.

## Ресурсные ограничения

По локальным unit-файлам: collector `MemoryMax=160M`, `CPUQuota=30%`;
exporter `MemoryMax=64M`, `CPUQuota=10%`.
Это конфигурационные лимиты, не измеренный расход и не доказательство
применения этих файлов к текущим серверным units.

Исторический расчет 2026-09-11: 720 batches / 1440 строк в сутки,
10 080 строк за 7 синтетических суток, 4,6875 MiB.
Резерв 50 MiB не является hard quota; WAL, indices, logs и открытые
инциденты учитываются отдельно. Нет подтвержденного семисуточного baseline.

Живая серверная SQLite не должна быть в Dropbox.
Но существующий Mac Compose **фактически задает** `./data/prometheus`
и `./data/grafana` внутри Dropbox; образы указаны как `latest`.
Это ограничения master, а не уже выполненный перенос/фиксация версий.
В этом ревью runtime, образы и размещение данных не менялись.

## Следующие этапы приемки

Это backlog, не разрешение на запуск или установку.

1. Дополнить снимок: локальные команды с returncode/stderr, наличие и состояние
   agents, listeners включая 19107, Docker daemon/контейнеры отдельно.
2. Проверить старую SQLite согласованным read-only способом: integrity,
   schema/timing, min/max времени, число циклов по upstream, gaps, coverage,
   incident boundaries. Не копировать открытый WAL-файл обычным копированием.
3. До возобновления заново проверить guards, namespace, ownership, TTL,
   hashes master/installed, положительный путь обоих WG и адресные captures.
   Не применять прежний manifest и не трогать VPN ради зеленого dashboard.
4. Согласовать ограниченный pilot run; отдельно проверить API из macOS и
   контейнера Prometheus/Grafana. Health/API availability не равно egress UP.
5. Завершить bounded history-sync и Grafana acceptance:
   [TimeWeb_Uplink_History_Sync_Plan](<../reference/TimeWeb_Uplink_History_Sync_Plan.md>).
6. Проверить restart, storage failures, source DB change, clock rollback,
   retention gaps, отсутствие ложного UP; затем ресурсный baseline и клиентский
   regression в согласованном окне.
7. Отдельно решить production blockers: WG/firewall ABA, права exporter,
   ограниченный SSH forwarding, backup/restore, несинхронизируемые live DB,
   версии образов, доказуемый срок хранения и отдельную приемку failover state
   machine по критериям выше.

Исходные T01-T35 доступны в архиве. Их нельзя автоматически отмечать PASS
или выполнять без адаптации: там есть уже отклоненный серверный Prometheus
и инвазивные сценарии. Тесты/SSH/runtime в документационном ревью не запускались.

## История и связанные материалы

- [TimeWeb_Uplink_Guards_Quick_Guide](<../operations/TimeWeb_Uplink_Guards_Quick_Guide.md>)
- [TimeWeb_Uplink_History_Sync_Plan](<../reference/TimeWeb_Uplink_History_Sync_Plan.md>)
- [agents/history/TimeWeb_Uplink_Pilot_Deployment_2026-09-11](<../history/TimeWeb_Uplink_Pilot_Deployment_2026-09-11.md>)
- [agents/history/TimeWeb_Uplink_Guards_Deployment_2026-09-11](<../history/TimeWeb_Uplink_Guards_Deployment_2026-09-11.md>)
- [agents/history/TimeWeb_Uplink_Batch_Daemon_2026-09-11](<../history/TimeWeb_Uplink_Batch_Daemon_2026-09-11.md>)
- [VPN_Connectivity_Monitoring_Improvements](<../reference/VPN_Connectivity_Monitoring_Improvements.md>)

Предыдущие успешные пробы, replay и лабораторные результаты остаются
датированными свидетельствами. Они не устанавливают причину нового сбоя
и не доказывают текущую доступность клиентов.
