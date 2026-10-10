---
type: handoff
status: active
priority: high
topic: vpn-connectivity-monitoring
created: 2026-08-17
updated: 2026-08-17
tags:
  - handoff
  - monitoring
  - grafana
  - prometheus
  - wireguard
  - cenuta
  - timeweb
  - fornex
source:
  - "[VPN_Connectivity_Monitoring_Architecture](<../architecture/VPN_Connectivity_Monitoring_Architecture.md>)"
  - "[VPN_Connectivity_Monitoring_Implementation_Plan](<../reference/VPN_Connectivity_Monitoring_Implementation_Plan.md>)"
  - "[Восстановление_доступа](<../reference/Восстановление_доступа.md>)"
---

# Handoff: мониторинг связности VPN

## 1. Назначение handoff

Этот документ передает задачу следующему процессу/агенту. Его нужно читать
вместе с двумя каноническими документами мониторинга:

- [VPN_Connectivity_Monitoring_Architecture](<../architecture/VPN_Connectivity_Monitoring_Architecture.md>) - целевая архитектура;
- [VPN_Connectivity_Monitoring_Implementation_Plan](<../reference/VPN_Connectivity_Monitoring_Implementation_Plan.md>) - последовательность
  реализации и критерии приемки.

Handoff не является заменой текущему журналу инцидента, реестру VPN-клиентов
или host-state snapshots. Он связывает их и фиксирует точку продолжения.

## 2. Текущий статус

### Инцидент

Пользователь работает через старый Cenuta WireGuard и наблюдает:

- перерыв связи примерно раз в 5–7 минут;
- длительность перерыва около 20–30 секунд;
- во время видеоконференции пользователь слышит собеседников, но собеседники
  не слышат пользователя;
- рабочая гипотеза: временно нарушается исходящий канал или исходящий
  медиатрафик, но это еще не доказательство односторонней потери пакетов.

Факт внесен в [Восстановление_доступа](<../reference/Восстановление_доступа.md>) в записи `2026-08-17 —
пользовательское наблюдение: периодические сбои через Cenuta WG`.

### Состояние старых VPN-контуров

По последней зафиксированной проверке 2026-08-17:

- TimeWeb `wg-up-cenuta` имел свежий handshake с Cenuta;
- TimeWeb `wg1` имел свежий handshake с Fornex;
- старый Fornex `wg-exit` работал на `51821/udp`;
- AmneziaWG на Fornex работал параллельно со старым WireGuard;
- конфигурация MikroTik, TimeWeb, Cenuta и Fornex в рамках этой проверки не
  изменялась.

Это означает, что прежний массовый отказ uplink-контуров сменился на
периодические сбои при наличии handshake. Свежий handshake сам по себе не
подтверждает исправную передачу пользовательского трафика.

### Точка остановки реализации

Документы архитектуры и плана созданы. Реализация еще не развернута.

Последняя локальная проверка:

```text
docker client: 29.5.3
OS/Arch: darwin/arm64
Context: desktop-linux
```

Docker daemon недоступен:

```text
failed to connect to the docker API at
unix:///Users/sergey/.docker/run/docker.sock
connect: no such file or directory
```

Пользователю уже дана следующая команда, но результат запуска Docker Desktop
еще не получен:

```bash
open -a Docker
```

### Следующее действие

После подтверждения, что Docker Desktop полностью запущен, дать ровно одну
следующую команду:

```bash
docker version
```

Если daemon доступен, продолжить с baseline текущей площадки. До этого не
создавать каталоги, compose-файлы и контейнеры.

## 3. Текущая цель

Развернуть на Mac локальный мониторинг рабочего маршрута через Cenuta WG:

```text
Mac host probe agent -> Prometheus -> Grafana
```

Требования:

- измерение каждые 10 секунд;
- история минимум 30 дней;
- отдельные проверки LAN gateway, ICMP, DNS, HTTPS и WireGuard;
- визуальный Grafana dashboard;
- возможность увидеть короткий провал длительностью 20–30 секунд;
- выполнение probes на самом Mac, а не только внутри Docker;
- отсутствие секретов в Obsidian, metrics и dashboard;
- отсутствие изменений на рабочих VPN-серверах и MikroTik на первом этапе.

## 4. Профили перемещающегося Mac

Mac перемещается между площадками. Его IP может меняться. Кроме того, на двух
площадках используется один и тот же адрес шлюза `192.168.88.1`, поэтому
нельзя определять площадку только по gateway.

| `site_profile` | Площадка | Провайдер | Gateway | Последний известный IP Mac | Интерфейс | Надежность |
| --- | --- | --- | --- | --- | --- | --- |
| `orekhovo_asarta` | Орехово, Детская 11 | Asarta (`asarta.ru`) | `192.168.88.1` | `192.168.88.20` | Wi-Fi | Последнее зафиксированное значение |
| `nakhimova_domru` | Нахимова 11 | Дом.ру / ER-Telecom | `192.168.88.1` | `192.168.88.28` | Ethernet | Последнее зафиксированное значение |

Текущий профиль для первого baseline: `orekhovo_asarta`, согласно последнему
указанию пользователя. IP самого Mac нельзя зашивать в конфигурацию. Exporter
должен каждый раз получать текущий IP и активный интерфейс средствами macOS.

Профиль передается явно через конфигурацию или переменную окружения и входит в
label каждой метрики. При переезде нужно сменить только профиль и повторить
baseline; старую историю не удалять.

## 5. Целевая архитектура

### Host probe agent

Локальный процесс на macOS:

- слушает только `127.0.0.1:9105`;
- при scrape выполняет проверки с ограниченными timeout;
- публикует Prometheus metrics;
- не содержит private keys и полных WireGuard-конфигов;
- определяет текущий LAN IP и интерфейс Mac динамически.

Минимальные проверки:

| Probe | Цель | Смысл |
| --- | --- | --- |
| `gateway` | `192.168.88.1` | локальный путь до роутера |
| `icmp` | `1.1.1.1` и второй независимый адрес | IP-доступность/потери ICMP |
| `dns` | запрос через внешний или системный DNS | отделить DNS-сбой |
| `https` | `https://api.ipify.org`, `https://example.com` | реальный TCP/TLS-доступ |
| `wireguard` | handshake age, TX/RX counters | состояние туннеля и обмен |

### Prometheus

- scrape interval: `10s`;
- retention: `30d`;
- target из контейнера: `host.docker.internal:9105`;
- локальный endpoint: `http://127.0.0.1:9090`;
- постоянное хранилище в Dropbox System или отдельном локальном каталоге;
- Prometheus не должен быть единственным источником сведений о WireGuard:
  серверные counters при необходимости сверяются отдельно.

### Grafana

- локальный endpoint: `http://127.0.0.1:3000`;
- источник данных первой версии: Prometheus;
- четыре панели:
  1. Connectivity state;
  2. Latency;
  3. Failure matrix;
  4. WireGuard handshake/TX/RX;
- временные диапазоны: 15 минут, 1 час, 6 часов, 24 часа, custom;
- dashboard без ключей, паролей и полных конфигов.

### Планируемые каталоги

```text
services/monitoring/vpn-connectivity/
├── compose.yaml
├── prometheus/
│   └── prometheus.yml
├── grafana/
│   └── provisioning/
├── probe/
└── evidence/
```

На момент создания handoff этот каталог еще не создавался.

## 6. Метрики и интерпретация

Ожидаемые имена метрик:

```text
vpn_probe_up{site_profile="...",probe="gateway|icmp|dns|https"} 0|1
vpn_probe_latency_seconds{site_profile="...",probe="..."} <value>
vpn_probe_duration_seconds{site_profile="...",probe="..."} <value>
vpn_probe_errors_total{site_profile="...",probe="..."} <counter>
vpn_host_info{site_profile="...",lan_ip="...",interface="..."} 1
vpn_wireguard_handshake_age_seconds{peer="..."} <value>
vpn_wireguard_tx_bytes_total{peer="..."} <counter>
vpn_wireguard_rx_bytes_total{peer="..."} <counter>
```

Интерпретация:

- gateway down: локальная сеть, Wi-Fi/Ethernet или MikroTik;
- gateway up, внешние probes down: проблема выше LAN или в VPN-маршруте;
- ICMP down, HTTPS up: ICMP может фильтроваться отдельно;
- DNS down, HTTPS по IP up: проблема DNS;
- HTTPS down при свежем WG handshake: туннель формально жив, но возможны
  NAT/маршрутизация/egress;
- handshake stale и внешние probes down: вероятен сбой WireGuard/UDP-пути;
- внешние probes up, а ВКС теряет голос: искать отдельную проблему
  UDP-медиатрафика, NAT или приложения.

Один `ping` не является достаточным доказательством доступности или отказа
интернета.

## 7. VPN-топология и точки проверки

### TimeWeb: центральный relay/router

- Public IPv4: `94.241.171.65`.
- SSH user: `root`.
- SSH audit key path: `.local/ssh/codex_timeweb_audit_20260628`.
- Regular clients: `wg0`, `94.241.171.65:51820/udp`, `10.10.10.0/24`.
- Fornex uplink: `wg1` -> `103.75.126.143:51821/udp`, table `100`.
- BTH: `wg-home`, `94.241.171.65:51830/udp`, table `300`.
- Selector clients: `wg-clients`, `94.241.171.65:51850/udp`, `10.50.50.0/24`.
- Cenuta uplink: `wg-up-cenuta` -> `89.252.153.129:51840/udp`, table `200`.
- Runtime: Docker container `wg-relay`.
- Compose: `/opt/wg/docker-compose.yml`.
- Client command wrapper: `/opt/wg-router/commands.sh`.
- Session command: `wg-status` / `/opt/wg-router/commands.sh sessions`.

### Cenuta: Turkish egress

- Public IPv4: `89.252.153.129`.
- SSH user: `ubuntu`.
- SSH audit key path: `.local/ssh/codex_cenuta_audit_20260628`.
- WireGuard: `wg-cenuta`, `51840/udp`, `10.40.40.1/24`.
- Service: `wg-quick@wg-cenuta`.
- Firewall: nftables; SSH `22/tcp` и WG `51840/udp` allowed.
- Role: egress only; not BTH hub and not client-config store.

### Fornex: second egress and Amnezia test

- Public IPv4: `103.75.126.143`.
- VPS ID: `34-278098`.
- SSH user: `root`.
- SSH audit key path: `.local/ssh/codex_fornex_audit_20260628`.
- Legacy WireGuard: `wg-exit`, `51821/udp`.
- AmneziaWG: installed on same VPS in parallel; last log evidence names
  runtime `amnezia-awg2` and port `46055/udp`.
- AmneziaVPN client used for installation: `5.0.0`.
- Do not stop `wg-exit` or other Amnezia containers during monitoring setup.

## 8. Документы в Obsidian

### Канонические human-facing documents

- README (source reference not migrated) - карта раздела MikroTik.
- [VPN_Connectivity_Monitoring_Architecture](<../architecture/VPN_Connectivity_Monitoring_Architecture.md>) - целевая архитектура.
- [VPN_Connectivity_Monitoring_Implementation_Plan](<../reference/VPN_Connectivity_Monitoring_Implementation_Plan.md>) - план выполнения.
- [Восстановление_доступа](<../reference/Восстановление_доступа.md>) - текущий инцидент, доступ к Cenuta, тесты
  TCP/UDP, восстановление uplinks и наблюдение 2026-08-17.
- [VPN_HLD](<../architecture/overview.md>) - общая архитектура VPN и роли MikroTik/TimeWeb/Fornex/Cenuta.
- [MikroTik_Quick_Guide](<../quick-start.md>) - быстрые команды подключения, WG sessions,
  переключение провайдеров и текущие устройства.
- [TimeWeb_Client_Creation](<../operations/TimeWeb_Client_Creation.md>) - создание selector-клиентов и RU-via-BTH.
- [TimeWeb_VPN_Registry](<../registry/tunnels.md>) - реестр текущих клиентских профилей и IP.
- [TimeWeb_Parameters](<../hosts/timeweb/TimeWeb_Parameters.md>) - операционная карточка TimeWeb.
- [Cenuta_Parameters](<../hosts/cenuta/Cenuta_Parameters.md>) - операционная карточка Cenuta.
- [Fornex_Parameters](<../hosts/fornex/Fornex_Parameters.md>) - операционная карточка Fornex.
- [Current_Mikrotik_hAP_ax3_Config](<../hosts/nakhimova/Current_Mikrotik_hAP_ax3_Config.md>) - текущий сохраненный контур hAP ax3.
- [Orekhovo_Detskaya_11_MikroTik](<../hosts/orekhovo/Orekhovo_Detskaya_11_MikroTik.md>) - площадка Орехово, Детская 11.
- [Orekhovo_Detskaya_11_Router_Configuration](<../hosts/orekhovo/Orekhovo_Detskaya_11_Router_Configuration.md>) - конфигурация hEX
  `RB750Gr3` RouterOS `6.47` на Орехово.
- [DomRu_IP_Policy](<../reference/DomRu_IP_Policy.md>) - особенности сети Дом.ру и CGNAT.
- [Hosting_com_tr_Quick_Start](<../reference/Hosting_com_tr_Quick_Start.md>) - выбранный альтернативный провайдер
  hosting.com.tr; это отдельный будущий контур, не часть текущего monitoring
  bootstrap.

### Agent-facing documents and historical evidence

- agents/README (source reference not migrated) - правила агентской области и внешнего System storage.
- [agents/host-state/TimeWeb_Configuration](<../hosts/timeweb/TimeWeb_Configuration.md>) - фактическая конфигурация
  TimeWeb, Docker, interfaces, routes и client state.
- [agents/host-state/Cenuta_Configuration](<../hosts/cenuta/Cenuta_Configuration.md>) - фактическая конфигурация
  Cenuta, nftables, host-level WireGuard и ограничения.
- [agents/host-state/Fornex_Configuration](<../hosts/fornex/Fornex_Configuration.md>) - фактическая конфигурация
  Fornex, legacy WireGuard и Amnezia state.
- [agents/runbooks/TimeWeb_Agent_Operations](<../operations/agent-workflow.md>) - операционные правила для
  TimeWeb.
- [agents/reference/timeweb-scripts/commands.sh](<../../services/transport/timeweb-reality/maintenance-wg/commands.sh>) - reference wrapper для
  создания/удаления/проверки клиентов.
- agents/reference/timeweb-scripts/wg-status (source reference not migrated) - именованный статус WG
  peers по selector, legacy, BTH и uplinks.
- [agents/history/timeweb/README](<timeweb/README.md>) - индекс исторических изменений TimeWeb.
- [agents/history/cenuta/README](<cenuta/README.md>) - индекс аудитов Cenuta.
- [agents/history/fornex/README](<fornex/README.md>) - индекс аудитов Fornex.
- [agents/history/workplans/Cenuta_Routing_Setup](<workplans/Cenuta_Routing_Setup.md>) - исторический план
  запуска Cenuta routing.
- [agents/history/workplans/MikroTik_DigitalRazor_Cenuta_Routing_Workplan](<workplans/MikroTik_DigitalRazor_Cenuta_Routing_Workplan.md>) -
  исторический план DigitalRazor.

### История, которую читать для восстановления контекста

- [agents/history/timeweb/2026-07-09T1332Z-softreload-sessions/README](<timeweb/2026-07-09T1332Z-softreload-sessions/README.md>) -
  мягкий reload и sessions.
- [agents/history/timeweb/2026-07-09T1343Z-sveta-macbook-m3/README](<timeweb/2026-07-09T1343Z-sveta-macbook-m3/README.md>) -
  пара новых selector-профилей.
- [agents/history/timeweb/2026-07-10T0546Z-sergey-ipad-9.7-selector-pair/README](<timeweb/2026-07-10T0546Z-sergey-ipad-9.7-selector-pair/README.md>) -
  последние профили Sergey iPad.
- [agents/history/cenuta/2026-06-28T2025Z-wg-cenuta-setup/README](<cenuta/2026-06-28T2025Z-wg-cenuta-setup/README.md>) -
  первоначальная настройка Cenuta WireGuard.
- [agents/history/fornex/2026-06-28T1410Z-live-audit/README](<fornex/2026-06-28T1410Z-live-audit/README.md>) -
  первоначальный live-аудит Fornex.

## 9. Внешнее хранилище System

В Obsidian не хранить private keys, preshared keys, QR-коды и полные
импортируемые `.conf`. Полные файлы и backups находятся в Dropbox System.

- System README (source reference not migrated)
- [Текущие полные client configs](<../../.local/clients>)
- [README каталога clients](<../registry/tunnels.md>)
- [Текущий MikroTik hAP ax3: router artifacts](<../../.local/backups>)
- [README текущего hAP ax3](<../../.local/backups>)
- [Текущий MikroTik Орехово: router artifacts](<../../.local/backups>)
- [README текущего Орехово router](<../../.local/backups>)
- [Архивные/evidence backups](<../../.local/backups>)
- [README backups](<../../.local/backups>)
- [Deprecated artifacts](<../../.local/backups>)

### Что искать в System

- `.local/clients` - только актуальные полные клиентские конфиги; внутренние
  host-to-host/uplink configs туда не помещать.
- `System/Mikrotik/current/router` - текущие exports/backups hAP ax3.
- `System/Mikrotik/current/orekhovo-router` - текущие exports/backups
  Орехово `RB750Gr3`.
- `.local/backups` - полные evidence backups TimeWeb/Cenuta/Fornex
  и MikroTik.
- `services/monitoring/vpn-connectivity` - планируемое место мониторинга; на
  момент handoff еще не создано.

## 10. Применимые skills

Использовать skills как инструкции процесса, но не выполнять их действия
вместо проверки текущего состояния:

- context-engineering (source reference not migrated) -
  собрать focused context и определить source of truth перед продолжением.
- planning-and-task-breakdown (source reference not migrated) -
  сохранять малые проверяемые этапы, blockers и acceptance gates.
- debugging-and-error-recovery (source reference not migrated) -
  применять при каждом сетевом или Docker-сбое; сохранять точную ошибку и не
  повторять одну и ту же гипотезу без новой информации.
- source-driven-development (source reference not migrated) -
  использовать для version-sensitive Grafana/Prometheus/Docker решений и
  проверять официальную документацию.
- create-timeweb-vpn-client (source reference not migrated) -
  использовать только если будущая задача снова потребует создавать,
  менять, удалять или синхронизировать TimeWeb client profiles.
- doubt-driven-review (source reference not migrated) -
  применять перед изменениями production VPN, маршрутизации, firewall или
  внешних серверов.

Для текущего мониторинга `create-timeweb-vpn-client` не нужен: клиентские
конфиги не меняются.

## 11. Правила выполнения

1. Работать по одной команде или одному действию за раз.
2. Ждать результат пользователя перед следующим шагом.
3. На первом этапе только локальная Mac-инфраструктура; серверы и MikroTik не
   менять.
4. Не останавливать рабочий Cenuta WG, Fornex legacy WG или AmneziaWG.
5. Не считать свежий handshake доказательством end-to-end трафика.
6. При интерпретации сбоя сопоставлять как минимум gateway, ICMP, DNS, HTTPS и
   WireGuard counters.
7. Не использовать жестко заданный IP Mac; использовать `site_profile` и
   динамический сбор адреса.
8. Не публиковать в чат или Obsidian private keys, PSK, QR-коды и полные
   configs.
9. Любое изменение файлов фиксировать в handoff или отдельном checkpoint.
10. Если команда зависла или вернула неожиданный результат, остановить
    реализацию, сохранить точный вывод и локализовать проблему.

## 12. Ближайший план действий

### Шаг A - завершить запуск Docker Desktop

Пользователь выполняет:

```bash
open -a Docker
```

После визуального состояния Docker Desktop `Running` выполнить отдельно:

```bash
docker version
```

### Шаг B - baseline текущей площадки

Профиль: `orekhovo_asarta`.

Получить текущий интерфейс/IP Mac, не используя старый IP как факт текущего
состояния. Затем отдельно проверить gateway, внешний IP, DNS и HTTPS. Все
результаты привязать ко времени и профилю.

### Шаг C - подготовить локальное хранилище

Создать только после успешного Docker baseline:

```text
services/monitoring/vpn-connectivity/
```

Сначала подготовить `compose.yaml`, `prometheus.yml` и host probe. Потом
проверить exporter локально и только затем запускать Prometheus/Grafana.

### Шаг D - проверка без изменения VPN

Приемка первой версии:

- exporter отвечает на `127.0.0.1:9105`;
- Prometheus target `UP`;
- точки появляются примерно каждые 10 секунд;
- Grafana показывает минимум 15 минут истории;
- dashboard различает LAN, ICMP, DNS, HTTPS и WG;
- рабочий маршрут остается Cenuta WG;
- остановка мониторинга не влияет на VPN.

### Шаг E - наблюдение реального сбоя

Оставить Mac через Cenuta WG минимум на 60 минут. При очередном перерыве
сохранить время начала/окончания и сравнить с метриками. Для серверной
корреляции использовать read-only проверки TimeWeb/Cenuta после фиксации
локального события.

## 13. Stop-lines

Остановиться и не продолжать автоматически, если:

- Docker daemon не запускается;
- host probe не может работать на Mac и предлагается перенести его только в
  контейнер;
- требуется открыть Grafana наружу;
- требуется менять WireGuard, firewall, routes или Docker на VPS;
- требуется выключить старый WG или AmneziaWG;
- появляются запросы на вывод ключей или полных конфигов;
- одинаковые метрики нельзя надежно связать с текущим `site_profile`.

## 14. Definition of Done

Задача считается завершенной только когда:

- обе площадки описаны как profiles;
- текущий профиль можно переключить без изменения кода probes;
- сбор идет с Mac и подтвержден текущим маршрутом;
- данные хранятся 30 дней;
- Grafana dashboard отображает короткий сбой;
- есть отдельные показатели для LAN/ICMP/DNS/HTTPS/WG;
- есть безопасный export evidence;
- документация и пути хранения обновлены;
- не было незадокументированных изменений рабочих VPN-контуров.

## 15. LOG продолжения

### 2026-08-17 — Docker Engine проверен

- Docker Desktop на Mac установлен/обновлен до `4.87.0 (236836)`.
- Docker Engine доступен через context `desktop-linux`.
- Docker Engine version: `29.7.2`.
- API version: `1.55`, minimum `1.40`.
- Архитектура Docker Server: `linux/arm64`.
- Сетевые хосты, VPN-конфиги и существующие контейнеры не изменялись.
- Шаг A завершен. Следующий шаг: baseline текущего сетевого контекста Mac.

### 2026-08-17 — baseline: default route

- Команда `route -n get default` выполнена на Mac.
- Default gateway: `192.168.88.1`.
- Активный интерфейс: `en0`.
- Профиль площадки пока не выбирается автоматически: такой gateway используется
  и на Нахимовой, и на Орехово.
- Изменений сетевой конфигурации и VPN не выполнялось.

### 2026-08-17 — baseline: active route and egress

- Текущий IP Mac на `en0`: `192.168.88.28`.
- На `en1` также присутствует адрес `192.168.88.20`; это не default
  interface текущего маршрута.
- Обнаружен активный `utun4` с адресом `10.8.1.3`.
- Таблица маршрутов содержит `0/1 -> utun4` и `128.0/1 -> utun4`; весь IPv4
  трафик направляется через этот туннель.
- Внешний IPv4: `103.75.126.143`, то есть текущий egress — Fornex, а не
  Cenuta.
- Установка мониторинга пока не начиналась; рабочие VPN и сетевые настройки не
  изменялись.

### 2026-08-17 — выбор текущего профиля мониторинга

- Пользователь подтвердил: текущий рабочий маршрут — AmneziaVPN/AmneziaWG через
  Fornex.
- Первым профилем реализации выбран `fornex_amnezia`.
- Cenuta не отключался и не изменялся; его можно будет подключить позже как
  сравнительный профиль.
- План и архитектура мониторинга обновлены; установка exporter и контейнеров
  еще не начиналась.

### 2026-08-17 — локальный стек мониторинга запущен

- Создан каталог `services/monitoring/vpn-connectivity`.
- Host probe размещен в `probe/host_probe.py`; он выполняется на Mac и слушает
  только `127.0.0.1:9105`.
- Профили запуска: `SITE_PROFILE=nakhimova_domru` и
  `EGRESS_PROFILE=fornex_amnezia`.
- Probe подтвержден вручную: gateway, DNS и HTTPS равны `1`; маршрут содержит
  `utun4`, IP туннеля `10.8.1.3`, LAN `en0/192.168.88.28`.
- Prometheus и Grafana запущены Docker Compose; порты доступны только на
  `127.0.0.1:9090` и `127.0.0.1:3000`.
- Prometheus настроен на scrape каждые 10 секунд и хранение 30 дней.
- Цель `host.docker.internal:9105` подтверждена в Prometheus как `health=up`;
  scrape ошибок не имеет.
- Grafana health: database `ok`, version `13.1.3`.
- Добавлен provisioning-дашборд `VPN Connectivity` и README в каталоге
  мониторинга.
- Первая попытка держать probe через `launchd` завершалась с кодом
  `78 (EX_CONFIG)`; это задание выгружено. Рабочий probe запущен в отдельном
  видимом окне Terminal в foreground. VPN и маршруты не менялись.
- Grafana: `http://127.0.0.1:3000`.
- После проверки интерфейса панель `Current route` переведена из table в stat:
  label-метрика теперь отображает gateway, LAN-интерфейс/IP и utun-интерфейс/IP
  одной строкой.
- В probe добавлены `external_icmp` до `1.1.1.1` и `https_upload` через
  HTTPS POST; текущая проверка внешнего интернета агрегируется в панели
  `Internet status` отдельно от LAN-проверки gateway.
- На момент проверки `external_icmp`, DNS, HTTPS download и HTTPS upload
  равны `1`; активный туннель Fornex Amnezia не менялся.
- Разрывы на графиках диагностированы как пропуски Prometheus scrape:
  последовательное выполнение пяти проверок иногда превышало старый timeout
  `5s`, цель получала `context deadline exceeded` и переходила в `down`.
- Probe переведен на параллельное выполнение проверок, Prometheus timeout
  увеличен до `8s`; после исправления ответ probe занял `0.7s`, цель снова
  `health=up`, `lastError` пустой.
