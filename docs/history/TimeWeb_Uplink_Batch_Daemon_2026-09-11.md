---
type: implementation-report
created: 2026-09-11
status: local-candidate-tested-production-gates-open
---

# TimeWeb: batch helper и локальный daemon

Основной план: [../../TimeWeb_Uplink_Monitoring_Architecture_and_Plan](<../architecture/TimeWeb_Uplink_Monitoring_Architecture_and_Plan.md>).
Предыдущий этап: [TimeWeb_Uplink_Collector_Local_Implementation_2026-09-11](<TimeWeb_Uplink_Collector_Local_Implementation_2026-09-11.md>).
Мастер: `services/monitoring/timeweb-uplinks/`.
Интервал 120 s, deadline 45 s, stale 180 s. Установленный helper и
production-конфигурация WG не изменяются. Серверные установки отдельно.

## Защита cleanup от повторного сигнала

Расширенный Linux netns-тест обнаружил оставшийся каталог batch после
принудительного timeout, хотя lock освобождался. Увеличение ожидания
cleanup и вынос переменных владения из local scope не устранили дефект.
Трассировка `evidence/20260911T124434Z-batch-lab/result.json` показала:
первый SIGTERM вызывает `exit 90`, затем EXIT/cleanup; второй SIGTERM
повторно вызывает `exit 90` внутри cleanup и обрывает удаление ресурсов.

Правило для кандидата: обработчик cleanup в начале отключает повторный
EXIT и игнорирует TERM/INT/HUP на время ограниченной очистки. Владение
PID/process group и каталогом должно жить дольше stack frame измерения.
Тест проверяет и освобождение lock, и удаление каталога; один exit code
124 этого не доказывает. SIGKILL/падение ОС не дают гарантии выполнения
shell trap, поэтому production требует отдельной стратегии orphan recovery.

## Граница приемки

RTNL и pre/post snapshots не доказывают обнаружение произвольного WG/
firewall ABA. На стенде быстрые изменения с возвратом воспроизводятся
без отказа batch. Кандидат явно выводит `universal_generation=false`.
По умолчанию daemon запрещает запуск с такой неполной гарантией;
`allow_snapshot_scope` нельзя включать как способ сделать панель зеленой.
Нужна отдельная приемка модели изменений или иной механизм изоляции.

Стенд создает много новых интерфейсов. Их отложенные RTNL-события во время
первой пробы должны давать REFUSED, а не игнорироваться ради PASS.
Перед позитивным сценарием стенд ожидает завершения начальной настройки;
observer в helper не отключается и очередь событий не очищается.
Для разбора отказа сохраняется ограниченный текст RTNL-событий.

## Реализованные изменения

| Часть | Мастер в System | Результат |
| --- | --- | --- |
| Batch helper | `candidate/guardctl-batch.sh`, `candidate/batch_probe.sh` | Один общий flock и pinned namespace; шесть HTTPS, максимум два curl одновременно; общий pre/post manifest и watcher |
| Стенд | `candidate/batch_lab.sh`, `candidate/run_lab.py` | Отдельные Linux netns, без изменения WG production; SHA helper и hash live rules/routes/firewall до/после |
| Фиксированный adapter | `collector/uplink_monitor/adapter.py` | Проверка root-owned путей, двух SHA файлов helper, полного набора шести результатов, cache/manifest revision до/после |
| Постоянный цикл | `collector/uplink_monitor/daemon.py` | 120 s, deadline 45 s; single-instance lock, persistent epoch и backoff, обработка SIGTERM; нет auto-reapply |
| DNS | `targets.py`, `collector/requirements.txt` | dnspython 2.8.0; реальные TTL/expiration; refresh при нехватке остаточного TTL; не продлевать старый cache при ошибке |
| Durable state | `runtime.py`, `storage.py` | Atomic JSON/fsync; оба upstream и epoch одной SQLite-транзакцией; clock/config/guard/cache revision, run/boot identity |
| Данные | `storage.py` | Дневные агрегаты для summary; retention пересчитывает частично удаленный день; окна начала/восстановления и цензурирование неизвестных границ |
| Exporter | `exporter.py` | Отдельный health JSON; при ошибке storage/stale health `/metrics`, `/readyz`, `/api/current` дают 503; `/healthz` только о HTTP-процессе |
| Конфигурация | `collector/config.candidate.json` | Будущие серверные пути, точные SHA, `allow_snapshot_scope=false`; не установленный production config |

HTTPS теперь имеет раздельные connect/TLS timings. Поэтому timeout после
TCP connect не классифицируется как отсутствие TCP-связи. Batch дополнен
peer ICMP и возрастом WG handshake; в production-ветке есть DNS UDP/TCP
с WG source и guards. DNS-сигналы этой ветки пока не проверены полным
Linux daemon end-to-end. Direct controls выполняются в host namespace,
WG-пробы в pinned namespace; default route host namespace не имеет
отдельного непрерывного RTNL watcher. Это дополнительный предел атрибуции.

## Что проверено

76 локальных тестов PASS в `/Users/sergey/.venv`: atomic rollback второго
канала, повторный batch, настоящий SQLite `SQLITE_FULL` через ограничение
числа страниц, поврежденная БД, retention, начальные неизвестные границы
инцидента, clock regression при restart/внутри batch, смена config/cache,
DNS error без продления snapshot, daemon loop, API health, malformed batch,
разбор TCP/TLS timeout, прежние fixtures и 120-секундная политика.
`SQLITE_FULL` не означает испытание заполнения файловой системы сервера.

dnspython установлен **только на Mac**, в штатную `.venv`, после запроса
разрешения инструментом. Реальные A-запросы прошли: gstatic TTL около 88 s,
Cloudflare около 119 s на момент проверки. Эти ответы не являются
постоянной конфигурацией целей и не продлеваются вручную.

Linux-стенд проверяет: healthy batch, отсутствие маршрута, RTNL ABA,
воспроизведение слепой зоны WG/firewall ABA, поздний RST без прямого выхода,
TCP timeout, остановленный TLS server, принудительный deadline, cleanup,
освобождение lock, expiry и точный rollback тестовых правил. Неуспешные
прогоны сохранены; их нельзя выдавать за новые сбои Cenuta/Fornex.

Общий test report и SHA исходников:
`services/monitoring/timeweb-uplinks/evidence/20260911-batch-daemon/`.
Linux evidence: датированные `evidence/*-batch-lab/result.json`; итоговый
точный путь указан в `source-manifest.json`. Датированные серверные staging
каталоги содержат только кандидата для стенда, не установленный daemon.

## Ресурсы

Ускоренный synthetic load: 30 суток, 21 600 циклов, 43 200 записей каналов,
60 дневных агрегатов; это не реальная история сети. Итоговый прогон на Mac:

| Показатель | Измерено |
| --- | --- |
| Wall time генерации и проверки | 30.29 s |
| CPU time процесса | 23.93 s |
| Peak RSS | 29.77 MiB |
| SQLite после checkpoint | 20 930 560 bytes, около 20 MiB |
| p95 двух summary за 30 дней | 5.57 ms |
| SQLite integrity_check | ok |

Бюджеты локального теста соблюдены. Расчет CPU, распределенный на условные
30 дней, не является измерением загрузки TimeWeb. Linux helper children,
ядро, HTTP-нагрузка и Prometheus не входят в этот RSS. Серверные 96/32/384
MiB и средняя CPU-нагрузка <5% еще требуют отдельного baseline.
Свежая read-only проверка TimeWeb перед стендом: RAM 1967 MiB,
MemAvailable 1465 MiB. Пакеты и `.venv` там не устанавливались.

## Готовность и следующий барьер

Локальная функциональная реализация существенно продвинута, но критерии
production-перехода **не закрыты**:

1. WG/firewall ABA воспроизведен как пропуск observer. RTNL watcher
   проверяет PID/starttime, namespace, фактический socket inode, подписки,
   queue/Drops и отсутствие событий; это не покрывает все generic netlink
   и firewall изменения. Доказательство непрерывной generation integrity
   остается отдельной задачей, а не значением DNS cache generation.
2. Необходимо выбрать и проверить границу управления: все mutators под
   общим durable epoch/lock (с явным исключением обхода через root) либо
   изолированный стабильный namespace и/или отдельный kernel observer.
   Простое периодическое `wg show` не закрывает ABA. Ни один вариант
   этой записью не объявляется уже реализованным.
3. Нужны tests потери/переполнения watcher, смены PID/namespace во время
   batch, SIGKILL/orphan recovery; live end-to-end Python adapter + helper,
   expiry именно внутри длинного Linux batch, throughput/query concurrency.
4. Runtime-only guards не переживают смену namespace. Никакого reapply
   старого manifest; сначала новый audit и точный manifest.
5. Затем отдельное согласование серверной `.venv`, зависимостей,
   collector/exporter и Prometheus, свежий backup, deployment, клиентский
   regression, длительный baseline и Grafana/SSH integration.

До этих проверок не включать `allow_snapshot_scope` в production и не
подключать synthetic SQLite как историю настоящих отказов.

## Воспроизводимость

Локальные tests:

```bash
python3 -m pytest services/monitoring/timeweb-uplinks/collector/tests
```

Проверка комплекта, контрольных сумм и evidence без подключения к серверу:

```bash
python3 services/monitoring/timeweb-uplinks/collector/verify_bundle.py
```

Повтор Linux-стенда требует доступного TimeWeb и существующего базового
fixture staging. Runner не устанавливает пакеты и не меняет production
helper. Все Python-команды исполняются на Mac в `.venv`, в namespace
используются уже имеющиеся Linux shell/network tools.

Источники проверки API:
[dnspython Resolver и Answer.expiration](https://dnspython.readthedocs.io/en/stable/resolver-class.html),
[WireGuard netlink specification](https://www.kernel.org/doc/html/next/netlink/specs/wireguard.html).
Текущая спецификация WG описывает get/set-device; считать ее наличием
универсальной подписки на все изменения нельзя. Стендовое воспроизведение
ABA является самостоятельным свидетельством ограничения нашего observer.

## Итоговая проверка комплекта

Финальный Linux-прогон:
`evidence/20260911T125144Z-batch-lab/result.json`, `SUMMARY failures=0`.
Проверка повторного TERM прошла после защиты cleanup от повторного входа.
Позитивная проба запускается после стабилизации начальных интерфейсов
стенда; отказ RTNL во время начальной настройки сохранен в предыдущем
неуспешном evidence, а не удален из истории.

SHA-256 установленного и локального исходного `guardctl.sh` совпал:
`2f883e3ea356b1d88719a148acb89a5b50ccc629b6b51fd619fe2f67ab88cde1`.
Hash rules/routes/filter/nat/mangle рабочего namespace до/после совпал:
`17597d1d23a28c176c76ad601626882cb5d700c1885da1de4797de7322c94c4a`.
Проверка `verify_bundle.py`: 36 файлов, Python AST/Bash syntax, SHA
двух файлов helper в candidate config, 76/76 tests, final load report
и успешный Linux evidence. Это проверка локального комплекта, не deployment.

TLS-stop тест проверяет timeout установки TLS; у curl `connect-timeout`
охватывает и эту фазу. Случай уже установленного TLS с зависшим HTTP body
и полным `max-time=5` остается отдельной будущей Linux fixture-проверкой.
