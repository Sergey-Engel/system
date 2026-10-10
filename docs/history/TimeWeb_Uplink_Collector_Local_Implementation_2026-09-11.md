---
type: implementation-log
status: local-prototype-tested-production-not-deployed
created: 2026-09-11
updated: 2026-09-11
---

# TimeWeb: локальный collector и проверка случая Cenuta

> Текущее решение: интервал 120 s, deadline 45 s, stale 180 s; 50 тестов PASS.
> Изменение описано в конце документа. Предыдущие разделы сохраняют историю
> первоначального 10-секундного прототипа и его evidence, не текущий timing.

Архитектура: [TimeWeb_Uplink_Monitoring_Architecture_and_Plan](<../architecture/TimeWeb_Uplink_Monitoring_Architecture_and_Plan.md>).
Предыдущий этап: [TimeWeb_Uplink_Guards_Deployment_2026-09-11](<TimeWeb_Uplink_Guards_Deployment_2026-09-11.md>).
Инцидент: [Cenuta_MacBook_Selective_Access_2026-09-11](<Cenuta_MacBook_Selective_Access_2026-09-11.md>).

## Результат и границы

Создан и проверен **локальный прототип ядра**, не постоянный production
collector. Python: `python3`, 3.13.12. Пакеты не
устанавливались. На TimeWeb не установлены `.venv`, collector, exporter
или Prometheus; WG, клиентские конфиги, routes/rules и firewall не менялись.
На Mac существующий dashboard и его datasource не менялись.

Рабочая директория кода:
`services/monitoring/timeweb-uplinks/collector/`.

**43 локальных теста PASS.** Они проверяют классификацию, состояние,
хранение, DNS-кэш, bounded subprocess/scheduler и HTTP API. Это не полная
приемка T01-T35, не доказательство ресурсного бюджета на TimeWeb и не
приемка фонового daemon. Постоянный 10-секундный сбор еще не запущен.

## Что произошло на Cenuta и что определяем

Сохраненные защищенные пробы 09:34:53-09:35:11 UTC:

| Проверка | Fornex | Cenuta |
| --- | --- | --- |
| gstatic, ожидается HTTP 204 | 204, 0.230119 s | TCP connect timeout, 3.002689 s |
| Cloudflare, ожидается HTTP 200 | 200, 0.211753 s | TCP connect timeout, 3.002862 s |
| Helper | Валидное наблюдение | Валидное наблюдение, `curl_exit=28`, process exit 0 |
| Классификация ядра | `healthy` | `failed / tcp_connect_failed` |

Это достоверный отказ **проверяемого HTTPS/TCP egress**, не ошибка запуска
helper. После трех таких последовательных валидных циклов состояние
становится `DOWN`; первые один-два цикла сохраняются как короткий сбой.
Не интерпретировать заголовок будущей панели как «весь Интернет недоступен».

Позднее, в 10:21-10:23 UTC, captures реального MacBook показали двусторонний
UDP/443 и отсутствие ответов на TCP SYN к Speedtest. Для отдельного
контролируемого потока Cenuta -> TimeWeb:22 в 10:35:57-10:36:08 UTC:
TimeWeb получил SYN и отправил SYN-ACK, но ответ не появился на ens3 Cenuta.
Это доказательство потери на **обратном участке между двумя VPS для этого
потока**, не определение конкретного узла/оператора и не доказательство РКН.

Сами ранние HTTPS-пробы не содержат синхронной записи peer ICMP. Поэтому
replay не приписывает им выдуманное `transport_alive=1`: только
`tcp_connect_failed`, локализация `undetermined`. Сочетание свежего peer
ICMP с отказом HTTPS проверено отдельным fixture; оно дает признак
`beyond_peer_or_protocol_specific`. Синхронное подтверждение отказа прямого
egress самого VPS сужает область до `peer_host_egress_or_external_path`.
Это уровни локализации, а не автоматическое доказательство потери SYN-ACK.

## Повторная живая проверка 11:41:50-11:41:57 UTC

Пробы запущены **установленным guardctl.sh**, с его bound sockets,
pre/post manifest и RTNL watcher, не только ручным curl.

| Направление | Peer ICMP | gstatic | Cloudflare |
| --- | --- | --- | --- |
| TimeWeb -> Fornex | 2/2, среднее 56.905 ms | HTTP 204, 0.205550 s | HTTP 200, 0.213386 s |
| TimeWeb -> Cenuta | 2/2, среднее 98.410 ms | HTTP 204, 0.470666 s | HTTP 200, 0.490434 s |

До и после: `VALID generation=5`. Последние handshakes на момент
диагностических снимков: Fornex около 90 s, Cenuta около 70 s.
Local source HTTPS: `10.20.0.1` / `10.40.40.2`; pinned destinations:
`172.217.23.227` и `104.16.123.96`. Оба направления классифицированы
`healthy` по двум HTTPS-целям. Peer ping здесь дополнительная разовая
диагностика; не переносить его автоматически в другой по времени цикл.

Старый `probe-targets.json` просрочен. Для проверки создан отдельный
root-only DNS snapshot с TTL из свежих ответов `dig`; срок проверен и после
завершения проб. Canonical targets/manifest не перезаписывались.
Разовый verifier допускает только прямые публичные A-records и отказывает
на CNAME; это не подмена полноценного production DNS resolver.
На TimeWeb оставлен диагностический файл в
`/root/vpn-monitoring-verification-ApColQIL/targets.json`; он не используется
рабочими сервисами и непригоден после своего expires_unix.

**Положительный production HTTPS egress Cenuta через guard helper теперь
подтвержден в коротком окне.** Клиентский regression, все T01-T35, длительный
baseline и причины восстановления этим не подтверждаются. Capture всех
пакетов повторно не запускался; отсутствие direct fallback опирается на
существующие guards/manifest и предшествующую routing-приемку.

Ограничения и следующий этап

- Guards сейчас runtime-only в текущем namespace. **Нет auto-reapply после
  перезагрузки или пересоздания контейнера.** Старый manifest будет отвергнут;
  перед новым применением нужен свежий audit и новый проверенный manifest.
- `probe` использует bound sockets, pinned DNS/TLS, pre/post manifest и
  RTNL watcher link/address/route/rule. Проверяются фактический PID/socket
  inode watcher, подписки, Drops и пустая очередь перед приемкой.
- RTNL ABA проверен. Обнаружение временного out-of-band изменения и возврата
  WG peers через generic netlink или firewall не доказано: их persistent
  drift ловит pre/post snapshot, но это не универсальный generation monitor.
- DNS targets имеют expires_unix. Истекший snapshot дает REFUSED, а не DOWN.
  Автоматический безопасный refresh и постоянное поколение состояния
  должны войти в collector. Не отключать срок годности ради зеленой панели.
- Helper выполняет одну пробу, не имеет истории и не классифицирует HTTP
  response в итоговое UP/DOWN. Exit 0 с `curl_exit=28` означает достоверный
  timeout. Это необходимо учитывать будущему collector.
- Полные T01-T35, положительный production egress Cenuta, прикладной
  клиентский regression и длительный baseline еще не приняты.
- Следующий технический шаг: локальная реализация collector/state machine,
  fixture-тестов, scheduler и exporter в штатной `.venv`. Установки на
  TimeWeb `.venv`, collector и Prometheus согласовываются отдельно.

### Где находятся реализованные компоненты

Мастер-копия кода, конфигурации и тестов:
`services/monitoring/timeweb-uplinks/`.
Модули из таблицы ниже находятся в `collector/uplink_monitor/`, а
`verify_live.py` и `replay_incident.py` в `collector/`.
Collector, scheduler и exporter пока **не установлены на TimeWeb**.
На сервере размещена исполняемая копия guard helper в
`/opt/vpn-monitoring/guards/`.

Правило: изменения сначала в локальном System, затем проверенное
развертывание и сверка SHA-256; аварийные серверные изменения обязательно
переносятся в мастер после сверки diff. Подробный состав, соответствие
путей и отличие конфигурации от генерируемого состояния:
[README мастер-копии](<../../services/monitoring/timeweb-uplinks/README.md>).

| Модуль | Что реально есть | Ограничение |
| --- | --- | --- |
| `model.py` | Раздельные validity/success; фазы TCP connect, TLS, HTTP/body, unknown; частичная доступность и диагностические признаки | Старый helper не дает полных phase timings; фазу неизвестного timeout не угадывать |
| `state.py` | Три неуспеха для DOWN, два success для закрытия отказа; короткие сбои и UNKNOWN | После UNKNOWN первый полностью успешный цикл дает UP согласно архитектуре, это не закрытие прерванного outage |
| `storage.py` | SQLite WAL, транзакция на upstream/слот, idempotency, incidents/gaps, coverage, retention | Два upstream пока не коммитятся одной общей транзакцией; нет production-дневных агрегатов и полного storage health channel |
| `targets.py` | Публичные IPv4, TTL, atomic replace/fsync, поколение cache, запрет продления старой записи при ошибке refresh | Автоматический refresh-loop еще не подключен; dnspython отсутствует, при попытке реального backend будет REFUSED |
| `collector.py` | Прием фиксированного batch-контракта, общий deadline/expiry/generation, фильтр старых diagnostic signals, запись результатов | Не production trust boundary: результат должен поступать от доверенного фиксированного adapter, не HTTP-клиента |
| `scheduler.py` | Слоты 10 s, monotonic, привязка старта к UTC-слоту, без catch-up, process-group cleanup, timeout/output limit | Это примитивы расписания и bounded runner; рабочего бесконечного daemon/adapter еще нет |
| `exporter.py` | Loopback-only read-only API и Prometheus text metrics, stale -> UNKNOWN | Не подключен к действующей Grafana/Prometheus; лимиты CPU/RAM и production HTTP hardening еще не приняты |
| `verify_live.py` | Разовая SSH-проверка с новым ограниченным DNS snapshot | Не daemon, не автоматическое исправление guards |
| `replay_incident.py` | Разбор сохраненного отказа и подтвержденного восстановления, тест истории | Повторение одной реальной пробы на синтетической шкале, не новая история реальной сети |

Метрики разделяют `vpn_uplink_state` (HTTPS egress), `probe_valid`,
`probe_success`, TCP/TLS phase и `transport_alive`. Непроверенная фаза
отсутствует, не превращается в 0. При stale не экспортируются старые
probe success как свежие. Два ожидаемых upstream остаются в выдаче UNKNOWN.
Dynamic IDs, HTTP body, ключи и raw error text не попадают в labels.

Exporter: `/metrics`, `/healthz`, `/api/current`, `/api/summary`,
`/api/incidents`. Времена API `from/to` в Unix milliseconds; максимум
30 дней, 1000 incidents на страницу, явный `next_offset`, максимум 1 MiB.
Чтение SQLite read-only, SQL execution budget 0.7 s на соединение, один HTTP
request одновременно. HTTP handler не запускает пробы. `/healthz` говорит
только о HTTP-процессе, не о доступности WG/Интернета. При ошибке SQLite
ответ 503, а не пустой успешный отчет. Production testing query limits остается.

## Дифференцирующие проверки

Следующая таблица обязательна для adapter. **Параметры модели уже есть,
но их непрерывный автоматический сбор еще не реализован.**

| Проверка | Что отличает | Период / граница |
| --- | --- | --- |
| Bound ICMP peer + WG metadata | Рабочий обмен внутри WG против отказа egress | 10 s; handshake не заменяет active probe |
| Две pinned HTTPS-цели разных операторов | Общий TCP/TLS отказ против отказа одной цели | 10 s, общий deadline 8 s |
| TCP connect / TLS / HTTP result отдельно | TCP timeout, TLS negotiation/certificate, HTTP 403/429/5xx | Внутри тех же запросов, не отдельная пачка socket tests |
| DNS UDP и TCP через тот же WG | Проблема resolver/UDP против общего HTTPS отказа | Раздельные результаты, не системный DNS TimeWeb |
| Те же pinned цели direct TimeWeb и через другой upstream | Общая неисправность цели или локализация на одном направлении | Direct строго отдельный control, не fallback неудачной WG-пробы |
| Google/Speedtest как дополнительные service checks | Избирательная недоступность сайта при здоровых базовых целях | По событию или 60 s; отдельный статус сайта, не голос полного outage |
| Прямой HTTPS с peer VPS | Неисправность TimeWeb -> peer против собственного egress peer | По событию; постоянные права доступа согласовать отдельно |
| Двусторонний SYN/SYN-ACK capture | На каком межхостовом участке исчезает ответ | Только ограниченная диагностика с обеих сторон, не постоянный payload capture |

Для site checks нужны свои допустимые redirect/HTTP-коды и свежие pinned
адреса. Код 301 для корня Google/Speedtest ожидаем, но для gstatic generate_204
он считается unexpected. Не добавлять Speedtest в обязательный кворум:
антибот HTTP 403 или сбой CDN не равен полной потере Интернета.
Две базовые цели не гарантируют обнаружение любой избирательной блокировки.

## Тесты и evidence

Все пути далее относительно
`services/monitoring/timeweb-uplinks/`:

- `evidence/20260911-guards/production-captures.json`: реальные исходные
  helper observations отказа, подтверждение `PROBE_WAN_DIRECT_COUNT=0`.
- `diagnostics/20260911-macbook-selective-access/`: captures MacBook и
  контролируемого TCP/22, диагностика и восстановление Google/Speedtest.
- `evidence/20260911T114146Z-collector-live-verification/`: свежие DNS,
  отдельный targets JSON, stdout guard helper, производная classification.
- `evidence/20260911-collector-local-replay/`: `report.json`, synthetic
  SQLite, `.prom`, `pytest.xml`. Report содержит SHA256 источников.

В replay одна сохраненная неуспешная пара проб повторяется в трех
**синтетических** слотах, затем дважды повторяется успешная пара, затем
вставляется UNKNOWN. Проверены переходы DOWN/UP и исключение UNKNOWN из
downtime. Числа 30 s отказа / 10 s UNKNOWN / 1 episode в этом отчете являются
fixture-ожиданиями, не статистикой реального инцидента 11 сентября.

Локально проверены части T01, T04-T12, T14, T16-T18, T20-T22, T26.
Это не полное закрытие соответствующих T: например, T12 без реального
Prometheus, T22 включает locked SQLite, но не реальный full disk.
При разработке исправлены неверное число SQL placeholders и ошибка чтения
удаленного retention-циклом probe snapshot. Replay expectation после UNKNOWN
сверено с архитектурой: первый healthy дает UP. Неуспешные тесты не являются
новыми сбоями сети.

Команда повторной проверки, только на Mac в штатной `.venv`:

```bash
python3 -m pytest services/monitoring/timeweb-uplinks/collector/tests
```

Реальный collector/exporter сейчас запускать не требуется. Fixture SQLite
не подключать как production datasource и не переносить в текущую историю.

## Следующие шаги и критерий перехода

1. **Пакетный helper.** Нынешний `guardctl.sh` держит общий `flock -n` все
   время одной пробы. Шесть последовательных 5-секундных timeout не помещаются
   в 10 s; параллельные вызовы конкурируют за lock. Нужен один batch под общим
   guard check/watcher с ограниченной конкуренцией и приемкой всего поколения.
   Проверить Linux netns, поздние RST, ABA, cleanup и deadline; live helper
   пока не менять. Пересмотреть RTNL watcher и blind spots WG/firewall ABA.
2. **Завершить локальный daemon.** Подключить фиксированный batch adapter,
   safe DNS refresh с реальной библиотекой, пре-/пост-cache revision,
   persistent clock/config/guard generation, restart/backoff и storage-health.
   Текущий cache generation не заменяет универсальный generation monitor.
3. **Данные и нагрузка.** Общий transactional batch, уточненные границы
   incidents, дневные агрегаты/кэш API, disk-full/corruption/clock tests,
   30-дневный synthetic load test. Измерить RSS/CPU в пределах бюджетов.
4. **Отдельно согласовать установки** TimeWeb `.venv`, зависимости,
   collector/exporter и Prometheus. Затем backup, deployment, regression,
   baseline и Grafana/SSH integration по основному плану.

Не отключать expiry ради UP. Не продлевать старый snapshot при DNS error.
Не делать auto-reapply по старому manifest. Не выдавать локальный replay
или короткий production probe за полную эксплуатационную приемку.

Источники реализации:
[Prometheus exposition format](https://prometheus.io/docs/instrumenting/exposition_formats/),
[Python subprocess](https://docs.python.org/3/library/subprocess.html),
[dnspython resolver](https://dnspython.readthedocs.io/en/stable/resolver-class.html).

## 2026-09-11: переход на интервал 120 секунд

По запросу пользователя все периодические uplink-проверки проектируются
раз в 120 s. Изменены только локальный прототип и архитектура; серверный
collector по-прежнему не установлен, локальный Mac host_probe не изменялся.

Единая политика `uplink_monitor/timing.py`: `interval=120`, `deadline=45`,
`stale_after=180`. Scheduler, validator, SQLite history и exporter используют
согласованные значения. Timeout отдельной HTTPS-пробы остается до 5 s;
45 s ограничивает весь цикл, не один запрос. Пропуски не догоняются.

Пороги сохранены: три последовательных неуспеха для DOWN, два success для
подтверждения восстановления. Первое предупреждение в ближайшем цикле;
подтвержденный отказ через 4-6 минут от начала плюс время проб, восстановление
через 2-4 минуты плюс время проб. Короткие перерывы между пробами могут
не попасть в историю вообще. Интервал оценочной статистики теперь 120 s.

Политика timing записывается в metadata новой SQLite schema v2. Запись
с другим timing в ту же БД запрещена. Сохраненные v1 evidence читаются
read-only с прежней политикой 10/8/25, без автоматической миграции и без
переоценки старых слотов как 120-секундных. Старый replay явно использует
LEGACY_TIMING; реальная production DB еще не создана.

50 тестов PASS в штатной `.venv`. Добавлены проверки 120-секундных слотов,
пропуска и отсутствия catch-up; state thresholds, freshness 180 s,
интервальной статистики, deadline 45 s, expiry внутри цикла, неизменной
семантики legacy DB и запрета несовместимой записи. Evidence:
`services/monitoring/timeweb-uplinks/evidence/20260911-collector-120s/pytest.xml`.

Следующий кандидат: последовательный adapter существующих guard-проб
с общим deadline 45 s. Шесть timeout по 5 s дают бюджет 30 s плюс накладные
расходы; это оценка, не выполненный Linux baseline. Параллельный batch
больше не обязателен только ради 10-секундной скорости. Проверки поколения,
межпробных изменений, TTL, cleanup, Linux baseline и согласование серверных
установок остаются обязательными. Не расширять TTL ради длинного цикла.

Предварительное изменение документа не применилось из-за неполного
строкового якоря; файл перечитан, изменения применены отдельными точными
патчами. Исходные captures, старые тест-отчеты и история не переписывались.

## 2026-09-11: batch helper, daemon и нагрузочный тест

Продолжение реализовано в локальном мастере System. Подробный состав,
Linux-проверки и незакрытые gates:
[TimeWeb_Uplink_Batch_Daemon_2026-09-11](<TimeWeb_Uplink_Batch_Daemon_2026-09-11.md>).
76 локальных тестов PASS; ускоренные 30 дней истории, atomic batch,
дневные агрегаты, daemon, dnspython refresh, health и fixed adapter.
Последний Linux-стенд: `evidence/20260911T125144Z-batch-lab/result.json`,
`SUMMARY failures=0`, рабочие rules/routes/firewall и helper не изменены.
Cleanup повторного SIGTERM исправлен и перепроверен. Необнаруженный
WG/firewall ABA воспроизведен: production-запуск запрещен по умолчанию.
Серверные `.venv`, collector и Prometheus не устанавливались.
