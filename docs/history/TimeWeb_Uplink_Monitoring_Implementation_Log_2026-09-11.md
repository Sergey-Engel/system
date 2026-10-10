---
type: work-log
topic: timeweb-uplink-monitoring
status: in-progress
created: 2026-09-11
updated: 2026-09-11
---

## Задача и границы

План: [TimeWeb_Uplink_Monitoring_Architecture_and_Plan](<../architecture/TimeWeb_Uplink_Monitoring_Architecture_and_Plan.md>). Начат этап 0:
проверка готовности среды и существующего локального мониторинга. Новый
server-side collector, Prometheus и API на TimeWeb пока не установлены.

Пользователь уточнил порядок работы: проверочные команды выполняет агент без
запросов разрешения; любые установки/обновления предварительно согласуются и
затем также выполняются агентом. На Mac весь Python запускается из штатной
`/Users/sergey/.venv`. Новую локальную среду не создавать.

## 2026-09-11: Python и зависимости

Подтверждено:

- `~/.zshrc` активирует `/Users/sergey/.venv/bin/activate` и добавляет ее bin в PATH.
- Python: `python3`, версия 3.13.12.
- `sys.prefix=/Users/sergey/.venv`, `sys.base_prefix` отличается: virtualenv действителен.
- В `pyvenv.cfg`: `include-system-site-packages=false`.
- PyYAML 6.0.3, requests 2.34.2 и pytest 8.3.5 импортируются.
- `prometheus_client` и `dns.resolver` не установлены. Текущий `host_probe.py`
  использует stdlib; его AST/import в `.venv` прошли без запуска server main.
- Пакеты не устанавливались и не обновлялись.

`python3 -m pip check` завершился с exit code 1:
11 существующих конфликтов требований. Это не результат текущих изменений.

```text
googleapis-common-protos 1.73.0 требует protobuf <7, установлен 7.35.1.
opentelemetry-proto 1.40.0 требует protobuf <7, установлен 7.35.1.
opik 1.6.9 требует openai <2, установлен 2.41.0.
langgraph-api 0.10.0 требует protobuf <7, установлен 7.35.1.
langgraph-api 0.10.0 требует starlette >=1.0.1, установлен 0.52.1.
streamlit 1.52.2 требует pandas <3, установлен 3.0.3.
streamlit 1.52.2 требует protobuf <7, установлен 7.35.1.
torchaudio 2.10.0 требует torch ==2.10.0, установлен 2.12.0.
grpcio-health-checking 1.80.0 требует protobuf <7, установлен 7.35.1.
grpcio-tools 1.80.0 требует protobuf <7, установлен 7.35.1.
datasets 5.0.0 требует fsspec[http] <=2026.4.0, установлен 2026.6.0.
```

Это сводка конфликтов, не полный requirements lock. Автоматический repair
общей среды не выполнялся: он способен повлиять на другие приложения.

## 2026-09-11: Docker и Grafana

Первоначально `docker version` показывал только Client и ошибку отсутствия
`~/.docker/run/docker.sock`. Выполнен запуск уже установленного Docker через
`docker desktop start --timeout 30`; скачивания/установки образов не выполнялись.

После запуска:

- Docker Desktop 4.87.0; Client/Engine 29.7.2, API 1.55.
- `vpn-connectivity-grafana` и `vpn-connectivity-prometheus` автоматически
  перешли в Up, опубликованы только localhost 3000/9090.
- Grafana `/api/health`: database `ok`, версия 13.1.3.
- Prometheus `/-/ready`: Ready.
- Проверка `http://prometheus:9090/-/ready` из контейнера Grafana успешна.
- Dashboard provisioning: UID `vpn-connectivity`, 5 панелей; JSON валиден.
- Infinity среди установленных Grafana plugins отсутствует; не устанавливался.
- В начале проверки Prometheus target `vpn-host-probe` был DOWN: connection refused на 9105.

## 2026-09-11: исправление Python-запуска probe

До правки wrapper, шаблон plist и установленный LaunchAgent использовали
`/usr/bin/python3`, хотя пользовательская штатная среда другая. Процесс probe
не работал; launchd показывал последнюю ошибку 78 (`EX_CONFIG`).

До изменения сохранены копии Python-файла, wrapper, обоих plist, System README
и Quick Guide в backup (source reference not migrated).
Это backup локального запуска, не новый полный backup VPN-хостов.

Изменено:

- shebang `probe/host_probe.py`: `python3`;
- `probe/run_host_probe.sh`: exec через тот же абсолютный путь;
- template `probe/com.sergey.vpn-host-probe.plist` и установленный
  `~/Library/LaunchAgents/com.sergey.vpn-host-probe.plist`: одинаковый venv Python;
- stdout/stderr LaunchAgent перенесены из Dropbox в
  `/Users/sergey/Library/Logs/vpn-connectivity/host_probe.log`;
- обновлены System README и [VPN_Connectivity_Monitoring_Quick_Guide](<../operations/VPN_Connectivity_Monitoring_Quick_Guide.md>);
- в Quick Guide разнесены сообщение процесса и проверочная curl-команда по
  отдельным code blocks, чтобы сообщение не копировалось как команда.

Одной замены Python оказалось недостаточно: launchd сохранял `EX_CONFIG`.
После переноса log path и повторного bootstrap процесс запустился. Это
подтверждает успешность обхода проблемы log path; точная внутренняя причина
отказа старого пути (права/FileProvider/другая причина) отдельно не доказана.
Настройки приватности macOS и разрешения доступа не отключались.

Проверки после изменения:

- `plutil -lint` обеих копий plist: OK;
- `zsh -n` wrapper: OK;
- plist разобраны `plistlib`, copies equal, ProgramArguments содержит venv Python;
- launchd: `LastExitStatus=0`, PID 74035 на момент проверки;
- `/metrics` вернул ответ примерно за 0.94 с;
- gateway, ICMP, DNS, HTTPS GET/POST успешны в одном текущем замере;
- на scrape 07:01:21 UTC Prometheus target UP, `lastError=""`, duration около 1.07 с.

Запущен именно существующий локальный мониторинг. Новая серверная система пока
не развернута; runtime-код сборщика, кроме shebang, не менялся.

## Ограничение достоверности локальных меток

В plist сохранены старые `SITE_PROFILE=nakhimova_domru` и
`EGRESS_PROFILE=fornex_amnezia`. Фактический текущий замер показывает gateway
`192.168.68.1`, LAN `en1 / 192.168.68.115`, внешний IP `194.61.140.217`, имя VPN
`Unknown VPN`. Назначение внешней площадки/маршрута не установлено.

Статические профили не считать доказательством Нахимова или Fornex. `utun3`
без tunnel IPv4 также сам по себе не доказывает активный пользовательский VPN.
Эти ограничения старого probe не исправлялись попутно с заменой Python и
не должны влиять на выводы о работе TimeWeb upstream.

## 2026-09-11 06:56:53 UTC: дополнительный read-only preflight TimeWeb

- SSH успешен, NTP synchronized=yes.
- `wg-relay`: running, PID 1181.
- Считаны действующие `ip rule`: local, клиентские lookup main 180/181,
  RU fwmark rule 190 -> table 300, legacy 219 -> table 100, selector rules
  220-238 -> table 100/200, BTH iif rule 300, main/default.
- Для обоих upstream persistent keepalive = 25 секунд.
- На хосте есть `wg`, `nsenter`, `curl`, `ip`, системные python3/pip3.
- Ограниченный поиск `pyvenv.cfg` в `/opt` и `/root` до глубины 4 не нашел
  серверную `.venv`. Это не полный поиск всех возможных окружений на VPS.
- Серверный Python не запускался; пакеты, маршруты, SSH/WG-конфигурации не менялись.

Mac virtualenv не переносится на Linux. Для будущего сборщика согласовать
создание и зависимости отдельной серверной `.venv`, после чего использовать
только ее интерпретатор. Не устанавливать пакеты в системный Python TimeWeb.

## Что дальше

- Завершить read-only проверки реального пути проб через оба upstream,
  с привязкой интерфейса и проверкой отсутствия прямого fallback.
- Подтвердить актуальность восстанавливаемых backups перед изменениями на VPS.
- До установки согласовать точный состав Python-зависимостей и серверной `.venv`.
- Установку Infinity и нового Prometheus на TimeWeb согласовать отдельно.
- Не исправлять 11 конфликтов общей `.venv` в рамках этого внедрения.

## 2026-09-11 08:11-08:19 UTC: активная проверка обоих upstream

Выполнено по команде пользователя «проверяй». Только чтение конфигураций,
короткие ICMP/HTTPS/TCP-пробы и ограниченные captures заголовков. Пакеты,
службы и Python-окружения не устанавливались; VPN не перезапускались,
маршруты, firewall, ключи и клиентские конфиги не изменялись.

Исходные результаты: results.json в System (source reference not migrated).
Это диагностические данные, не backup конфигурации. Содержат адреса и
публичные peer keys, но не private/preshared keys или содержимое TLS-сессий.

### Состояние и фактический путь

| Проверка | Fornex | Cenuta |
| --- | --- | --- |
| SSH с Mac | Успешен | Успешен, scoped `known_hosts_cenuta` |
| TimeWeb interface/source | `wg1 / 10.20.0.1` | `wg-up-cenuta / 10.40.40.2` |
| Peer и endpoint | `10.20.0.2`, `103.75.126.143:51821` | `10.40.40.1`, `89.252.153.129:51840` |
| Клиентская таблица | 100, default via `10.20.0.2 dev wg1` | 200, default dev `wg-up-cenuta` |
| Ping внутреннего соседа | 2/2, среднее 58.3 мс | 2/2, среднее 115.9 мс |
| HTTPS api.ipify.org через WG | HTTP 200, IP `103.75.126.143` | TCP connect timeout |
| HTTPS Cloudflare через WG | HTTP 200, IP `103.75.126.143` | TCP connect timeout |
| HTTPS gstatic через WG | HTTP 204 | TCP connect timeout |
| Handshake age в финальном замере | 76 секунд | 14 секунд |

На TimeWeb подтверждены PID `wg-relay=1181`, интерфейсы, AllowedIPs и keepalive
25 секунд; финальный `ip rule` совпадает с исходным. Пробы исполнялись через
`nsenter -t 1181 -n` системным curl 8.5.0, не Python. Для curl использованы
`-q`, `-4`, `--noproxy '*'`, `--interface if!<WG>`, проверка TLS, конечные
connect/total timeouts. DNS-адрес каждой HTTPS-цели сначала получен на TimeWeb,
затем одинаковый `--resolve` использован в direct и обоих WG-тестах.
Это не проверка DNS внутри туннелей.

IP целей этого замера: api.ipify.org `172.67.74.152`, www.cloudflare.com
`104.16.124.96`, www.gstatic.com `172.217.23.227`. Для постоянного сборщика
они не фиксируются бессрочно: требуется DNS refresh с учетом TTL.

Обычный direct control с TimeWeb прошел все три HTTPS-цели и показал
`94.241.171.65`. `ip route get <target> from <WG source> oif <WG>` и lookup
с одним `oif` возвращают соответствующий WG-интерфейс без новых правил.
Но это еще не доказательство полной изоляции всех служебных пакетов.

### Cenuta: локализация наблюдаемого сбоя

На Cenuta `wg-quick@wg-cenuta`, nftables и systemd-networkd active,
`ip_forward=1`; AllowedIPs для TimeWeb `10.40.40.2/32`. Правила разрешают
forward из `10.40.40.0/24` через ens3, обратные established/related пакеты и
masquerade. В прочитанном ruleset OUTPUT accept; явного запрета тестов нет.

Прямо с Cenuta, без TimeWeb/WG, не прошли те же три HTTPS-цели (connect
timeouts 2-3 с). Новые TCP/22 подключения с Cenuta к TimeWeb и Fornex также
завершились timeout по 3 с. Одновременно ICMP к `1.1.1.1` прошел 2/2,
среднее 67.7 мс. Поэтому это не полный отказ сервера/интернета и не
доказательство блокировки всех протоколов.

Синхронный capture в 08:18:35-08:18:38 UTC показал четыре попытки одного
TCP SYN с одинаковым sequence:

```text
TimeWeb wg-up-cenuta Out: 10.40.40.2:51402 -> 172.67.74.152:443
Cenuta wg-cenuta In:     10.40.40.2:51402 -> 172.67.74.152:443
Cenuta ens3 Out (NAT):   89.252.153.129:51402 -> 172.67.74.152:443
Ответного SYN-ACK в capture Cenuta нет; curl завершился timeout через 4 с.
```

Факт: тест доходит по WG до Cenuta, проходит forward/NAT и виден на выходе
ens3. Для этого теста отказ наблюдается дальше либо на обратном внешнем
пути; capture внутри гостевой ОС не доказывает доставку на физическую сеть
провайдера. Причина/виновник не установлены: возможны внешняя фильтрация,
security group провайдера или другая сетевая неисправность. Утверждать
«РКН заблокировал UDP TimeWeb-Cenuta» по этим данным нельзя.

### Fornex и изоляция будущего сборщика

На Fornex `wg-exit` и контейнеры Amnezia Up около двух недель; DNS-контейнер
healthy. Это проверка процесса, не функциональный тест всех протоколов Amnezia.
На ОС Fornex `wg` отсутствует: после ошибки 127 проверка продолжена через
`docker exec wg-exit wg ...`, без установки пакетов. В контейнере подтверждены
peer TimeWeb, обратные маршруты, разрешающий forward и MASQUERADE.
Прямой HTTPS с Fornex также успешен.

Capture TimeWeb подтвердил, что SYN/SYN-ACK, TLS и HTTP-обмен с ipify шли
через `wg1`, HTTP 200 и внешний IP Fornex совпали. Однако после закрытия
curl-сокета в 08:18:35-08:18:36 поздние FIN/ACK от сервера пришли через WG,
а несколько ответных RST с source `10.20.0.1:41388` появились на `eth0`.
Это согласуется с генерацией RST ядром без прежней привязки сокета; сам
механизм отдельно не трассировался. Это не HTTP fallback через TimeWeb,
но критерий «ни одного служебного TCP-пакета мимо туннеля» пока не выполнен.

Отрицательный тест `--interface if!probe-absent` завершился curl code 45,
HTTP 000, без успешного прямого fallback. Удаление маршрута, остановка WG
и изменение production rules для теста не выполнялись. Полный fail-closed
тест с потерей маршрута и поздними RST остается обязательным на стенде.

### Коррекции методики во время проверки

- Первый запрос www.cloudflare.com с принудительным адресом `1.1.1.1`
  получил HTTP 403/error 1034 напрямую и через Fornex. Этот тест исключен
  из оценки доступности: повтор с DNS-адресом сайта дал 200 в контроле.
- Первые port-filtered captures дали 0 отображенных пакетов. Повторный
  capture по адресу цели показал, что фактические локальные порты были
  `41388/51402`, а не запрошенные `45193/45194`. Причина расхождения curl
  отдельно не установлена. Фильтр по желаемому порту не является надежным
  доказательством отсутствия трафика; сверять `local_port` и capture.
- Повторный capture Cenuta был подтвержден как listening до запуска проб;
  capture TimeWeb и запросы синхронизированы одним shell-сценарием.
  Все captures завершены; exit 124 означает штатное ограничение timeout.

### Решение по следующему этапу

Основной путь проб через оба WG установлен; Fornex egress работает,
Cenuta имеет наблюдаемый TCP egress failure при живом туннеле. Постоянный
сборщик должен сохранять эти два признака отдельно, не показывать зеленый
«Интернет» только по handshake. Продолжать диагностику Cenuta отдельно от
установки мониторинга; исправность обоих каналов не обязательна для сбора
достоверной истории их отказов.

До постоянного запуска решить на изолированном стенде маршрутизацию поздних
RST/непривязанных kernel replies и защиту от fallback. Одних `iif lo + oif`
правил может не хватить; проверить ограниченные local-source selectors или
отдельный probe namespace, не затрагивающие forwarded клиентский трафик.
Изменения production routing, создание серверной `.venv`, установка
Prometheus/Infinity пока не выполнены. Полные приемочные тесты не пройдены.

## 2026-09-11 08:25-08:39 UTC: изолированный стенд защиты проб

По команде «делай» выполнен следующий согласованный шаг: отдельный
network namespace-стенд на TimeWeb, не внедрение в production. Подробный
отчет со схемой, evidence и ограничениями:
[TimeWeb_Uplink_Monitoring_Isolation_Lab_2026-09-11](<TimeWeb_Uplink_Monitoring_Isolation_Lab_2026-09-11.md>).

Использованы только имеющиеся системные программы. Созданы два временных
namespace, отдельный WG и HTTPS fixture; veth не соединялись с host/relay.
Пакеты и серверные Python-окружения не устанавливались.

- Утечка поздних RST воспроизведена: 7 напрямую без защиты; с guards
  8 через WG, 0 напрямую.
- Дополнены `iif lo + oif` rules второй парой local-source lookup/prohibit.
- Отдельно выявлено, что bound curl может продолжать работу по WG при
  исчезнувшем явном route. Добавлена pre/post manifest validation:
  не запускать запрос либо отвергать полученный HTTP 200 как UNKNOWN.
- Первый прогон прервался из-за ошибки forwarded-source fixture; второй
  выявил ошибочное ожидание от kernel route lookup. Оба результата сохранены,
  причины и превентивные правила зафиксированы в архитектуре.
- Финальный прогон 08:39:07-08:39:24 UTC: 16 сценариев, 41 assertion PASS,
  failures=0, exit 0. Включены потеря/восстановление route, mid-request
  route change, down/up/delete интерфейса, успешный direct control.
- В 08:39:54 UTC хеши рабочих routes/rules/адресов и relay firewall совпали
  с baseline 08:31:51 UTC; PID wg-relay остался 1181. Тестового listener
  в host namespace и временных каталогов нет; cleanup завершен.

Выбран кандидат реализации: guards плюс валидатор пути. Перенос в
production требует аудита local-service replies/приоритетов/исключений,
backup и ограниченного rollback. Сам helper и постоянный collector еще не
установлены. Стенд не является полной приемкой T01-T35 или нагрузочным
тестированием; ABA/generation tracking остается задачей реализации.

## 2026-09-11 09:10-09:50 UTC: guard layer применен

Подробный отчет, manifest, ошибки стенда и evidence:
[TimeWeb_Uplink_Guards_Deployment_2026-09-11](<TimeWeb_Uplink_Guards_Deployment_2026-09-11.md>). Команды проверки/отката:
[TimeWeb_Uplink_Guards_Quick_Guide](<../operations/TimeWeb_Uplink_Guards_Quick_Guide.md>).

- Создан полный configuration backup до изменения, проверены 232 файла
  после изолированной распаковки и SHA256 локальной копии. Это не VM snapshot.
- Аудит CoreDNS выявил wildcard DNS/health listeners. Сохранены маршруты
  ответов в клиентские/служебные сети; проверены DNS UDP/TCP и health с
  host network и через WG с Fornex. Source replies Cenuta также проверены.
- Реализован и установлен root helper с exact ownership manifest,
  namespace identity, идемпотентным apply, точным rollback, pre/post validation
  и RTNL watcher. Согласованная граница: только 22 local rules, не routes.
- После v3 добавлено исключение gateway validation перед local-oif guard:
  без него штатное восстановление table 100 default via 10.20.0.2 не проходит.
- Canary 09:32:21: apply/NOOP/probes и rollback. Снимок 09:33:18 совпал с
  baseline. Повторно применены 22 rules в 09:34:35, generation 5; после
  проверок timer точного rollback остановлен в 09:40:39, guards оставлены.
- 130 local/forwarded route lookups идентичны до/после. Остальные rules,
  routes, firewall, peers и host routing совпадают с исходными.
- Bounded capture: 6 HTTPS-проб, 94 пакета, 0 drops, 0 исходящих TCP проб на
  eth0. Fornex: 3 успешных HTTP 204/200; Cenuta: 3 TCP timeout, как до guards.
- v4: 23 PASS. Дополнительный v5 подтвердил late RST isolation, но ABA-триггер
  был недостаточно изолирован от предыдущего сценария. Добавлены SYN-only
  capture, readiness и временные отметки. v6 (09:47) и v7 (09:49) прошли
  по 26 assertions: 8 late RST через WG, 0 напрямую; raw HTTP 200 после
  route ABA корректно отвергается как UNKNOWN. Неуспешные evidence сохранены.
- Client capture содержал только входящие SYN от Cenuta-only selector
  10.50.50.24, ответов нет. Это не полноценный прикладной regression.
  Пользователю предложен тест сайтов с существующего клиента TimeWeb ->
  Fornex без переключения рабочего Mac. Подтверждение пока не получено.

Guards runtime-only: не восстанавливаются автоматически после reboot/recreate.
Helper откажется от устаревшего namespace/manifest. Постоянный мониторинг,
серверные `.venv`, collector и Prometheus не установлены. Следующая работа:
локальный collector с fixture-тестами, затем отдельное согласование установок.
Полная приемка T01-T35 и длительный baseline остаются открытыми.

### 09:54 UTC: итоговое сохранение

Helper повторно дал `VALID generation=5`, все 22 правила на месте.
`final-audit.json` подтверждает неизменность остальных правил, маршрутов,
firewall, peers и namespace. Оставшихся lab/watchers/rollback timers нет.
MemAvailable 1471 MiB, свободно 18 GiB, handshake обоих upstream свежий.

Скачан `checkpoint-20260911T095404Z.tar.gz` с установленными guard files,
state и runtime rules/routes; проверены SHA256 архива, 7 внутренних файлов
и совпадение с локальными исходниками. SHA и ссылки в отчете внедрения.
Итоговая сводка `acceptance-summary-final.json` сохранена отдельно от ранней.
Обновлены текущая конфигурация TimeWeb, архитектура и индексы; создан
[TimeWeb_Uplink_Guards_Quick_Guide](<../operations/TimeWeb_Uplink_Guards_Quick_Guide.md>).

## 2026-09-11: локальное ядро collector и проверка отказа Cenuta

Подробности: [TimeWeb_Uplink_Collector_Local_Implementation_2026-09-11](<TimeWeb_Uplink_Collector_Local_Implementation_2026-09-11.md>).
На Mac в `python3` реализованы parser/classifier,
state machine, SQLite incidents/gaps/coverage, atomic TTL target cache,
bounded scheduler primitives и read-only loopback exporter/API.
43 локальных теста PASS, включая сохраненные наблюдения реального TCP
отказа и восстановления. Повторение этих наблюдений на synthetic timeline
проверяет пороги, но не является статистикой фактического простоя.

На TimeWeb 11:36 UTC guards VALID generation 5, старый targets snapshot
просрочен. В 11:41:50-11:41:57 UTC выполнены разовые пробы helper с
отдельным новым TTL snapshot: Fornex 204/200, Cenuta 204/200; оба peer ping
2/2. Guards до/после VALID generation 5. Положительный Cenuta HTTPS через
RTNL-guarded helper подтвержден, но client regression и baseline не закрыты.

Серверные установки, routing/firewall, WG и работающий Mac VPN не менялись.
Выявлен обязательный следующий шаг: общий flock текущего helper удерживается
всю одиночную пробу, поэтому наивный scheduler из 6 вызовов не обеспечивает
10-секундный цикл. Нужны batch helper/watcher и отдельная приемка, затем
DNS refresh-loop, permanent daemon и согласование установок на TimeWeb.

## 2026-09-11: частота проверок снижена до 120 секунд

По запросу пользователя изменены локальные defaults и текущая архитектура:
одна проверочная серия раз в 120 s, общий deadline 45 s, stale 180 s.
Пороги три fail / два success сохранены. Задержка подтверждения отказа
4-6 минут плюс время проб; короткие сбои между пробами могут быть пропущены.

SQLite сохраняет timing policy и не переинтерпретирует старые 10-секундные
слоты. 50 тестов PASS. Постоянный collector не запущен; серверы и локальный
Mac host_probe не изменены. Далее допустим последовательный bounded adapter,
не обязательно параллельный batch. Подробности:
[TimeWeb_Uplink_Collector_Local_Implementation_2026-09-11](<TimeWeb_Uplink_Collector_Local_Implementation_2026-09-11.md#2026-09-11-переход-на-интервал-120-секунд>).
