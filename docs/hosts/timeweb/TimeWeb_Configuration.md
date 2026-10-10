---
type: system-configuration
topic: mikrotik
system: timeweb
status: active
created: 2026-06-28
updated: 2026-09-25
tags:
  - mikrotik
  - vpn
  - wireguard
  - docker
  - timeweb
source:
  - "[TimeWeb_Parameters](<TimeWeb_Parameters.md>)"
  - "[TimeWeb_Client_Creation](<../../operations/TimeWeb_Client_Creation.md>)"
  - "[VPN_HLD](<../../architecture/overview.md>)"
  - "[VPN_Configuration_Registry](<../../registry/configuration.md>)"
---

## Основание и границы

Базовый снимок: live.json (source reference not migrated),
`hosts.timeweb`, 2026-09-13 14:45 UTC. Runtime дополнен и проверен
2026-09-22: 12 REALITY identity, синхронный Cenuta WSS fallback для relay и
Xray, а также allowlist `127.0.0.1:51924`. Полные credentials не публикуются.
Поведение recovery сверено по локальному master
`services/transport/timeweb-reality/bth-recovery-release/`.

Конфигурация уже реализована. Это серверное состояние, не план внедрения
и не all-traffic acceptance. Доступ и ресурсы: [TimeWeb_Parameters](<TimeWeb_Parameters.md>),
[Host_Access_Guide](<../../operations/access.md>). Схема: [VPN_HLD](<../../architecture/overview.md>). Roster: [TimeWeb_VPN_Registry](<../../registry/tunnels.md>).

Дополнение 2026-09-25: `macmini-socks-flex` использует новый Xray outbound
`wg-flex-macmini` и WG peer `10.50.50.41/32` на `wg-clients`. Выделены
RPDB table `414`, mark `0x41`, source priorities `243/244`, mark priorities
`184/185`, nft guard `flex_macmini` и `timeweb-flex-macmini.timer`.
`timeweb-flex-fleet` теперь управляет тремя устройствами; Mac Mini наследует
общие Gateway/RU-direct или получает независимые overrides. На сервере
подтверждены `ready` и `BTH_CONTRACT_VALID`; клиентский импорт и трафик
не подтверждены. Базовые счетчики и PID ниже относятся к старому снимку.

## Две runtime-границы

### Docker WireGuard

`wg-relay` running, restart `unless-stopped`, старт 2026-07-10.
Сеть `wg_wg-network`, контейнер `172.19.0.2`, bridge `172.19.0.1`.
PID `1181` и namespace `net:[4026532282]` относятся только к снимку;
после recreate их нельзя использовать без нового разрешения namespace.

- `wg0`: `10.10.10.1/24`, host `51820/udp`, 15 legacy peers.
- `wg-clients`: `10.50.50.1/24`, host `51850/udp`, 19 selector peers.
- `wg-home`: `10.30.30.1/24`, host `51830/udp`, 4 peers:
  домашний MikroTik `10.30.30.2`, два обычных BTH peer и REALITY `10.30.30.5`.
- `wg1`: `10.20.0.1/24`, uplink `103.75.126.143:51821`.
- `wg-up-cenuta`: `10.40.40.2/32`, uplink `89.252.153.129:51840`.

WG-интерфейсы и policy routing находятся в namespace контейнера.
Хостовый `wg show` не заменяет их проверку.
Compose: `/opt/wg/docker-compose.yml`;
mount `/opt/wg/config:/config`, `/lib/modules:/lib/modules:ro`.
Пять серверных конфигов находятся в `/opt/wg/config/wg_confs/`.

### Host-level REALITY

`xray-timeweb-reality.service` работает в namespace хоста,
не внутри `wg-relay`. Listener `94.241.171.65:443/tcp`,
VLESS/REALITY, SNI `www.apple.com`, target снимка `23.12.156.37:443`.

Три userspace WireGuard outbounds:

- `wg-fornex`: `10.20.0.3/32 -> 103.75.126.143:51821`.
- `wg-cenuta`: `10.40.40.3/32 -> 89.252.153.129:51840`.
- `wg-bth`: `10.30.30.5/32 -> 172.19.0.2:51830`,
  далее существующий `wg-home` и домашний выход.

Все три имеют MTU `1380`, `ForceIPv4`; это не дополнительные kernel WG
интерфейсы хоста. Выход выбирается по учетной записи, всего 12 независимых
REALITY identity: девять базовых FX/CEN/BTH и три отдельных `SOCKS-TW-CEN`
для MacBook Sergey, Mac Mini M4 Sergey и iPhone 12 Sergey. Полные UUID не
публикуются.
Неизвестный/неразрешенный TCP/UDP-трафик направляется в `blocked`.
В конфиге закрыты частные/служебные адреса, адреса трех VPS и IPv6.

Встроенный DNS Xray общий: DoH `1.1.1.1:443` через Fornex и
`1.0.0.1:443` через Cenuta, `UseIPv4`, fallback не отключен.
Это не выделенный домашний DNS для BTH и не доказательство отсутствия
клиентских DNS-утечек.

## Selector и native nft RU split

В namespace `wg-relay` действуют:

- Table `100`: default через `10.20.0.2 dev wg1` к Fornex.
- Table `200`: default через `wg-up-cenuta` к Cenuta.
- Table `300`: default через `wg-home` к BTH.
- RPDB `180/181`: возврат к `10.50.50.0/24` и `10.10.10.0/24` через main.
- RPDB `190`: `fwmark 0x30 -> table 300`;
  `219`: legacy `10.10.10.0/24 -> table 100`.
- RPDB `220-238`: назначенные source-маршруты selector;
  `300`: входящий `wg-home -> table 300`.

Native nft `inet ru_bth` присутствует. Его PREROUTING hook с priority
`mangle` маркирует `0x30` RU-назначения для sources из `clients_v4`
на `wg-clients`; отдельное правило предусмотрено для `legacy_clients_v4`
на `wg0`. RU-трафик SNATится к `10.30.30.1` при выходе через `wg-home`.

В `clients_v4` 16 selector sources; `10.50.50.24`, `.25`, `.38`
не входят в этот set. `legacy_clients_v4` пуст, legacy override сейчас отсутствует.
Non-RU использует назначенный Fornex/Cenuta route и соответствующий NAT.

**Пустой mangle в `iptables-save` не означает отсутствия RU split:**
маркировка реализована native nft и подтверждена в `hosts.timeweb.routing`.

Серверные master-файлы управления:
`/opt/wg-router/commands.sh`, `apply-ru-bth.sh`,
`state/clients.tsv`, `state/ru_networks_v4.txt`,
`state/ru_bth_clients.tsv`, `state/legacy_ru_bth_clients.tsv`.
Профили находятся в `/opt/wg-router/client-configs/`,
`/opt/wg/clients/`, `/opt/wg/clients_bth/`;
процедура обслуживания: [TimeWeb_Client_Creation](<../../operations/TimeWeb_Client_Creation.md>).

## REALITY guard и сервис

- Правильный unit: `/etc/systemd/system/xray-timeweb-reality.service`;
  enabled, active/running, User `reality-fornex`.
- ExecStart: `/opt/timeweb-reality/xray run -config /opt/timeweb-reality/config.json`.
- Дополнительная проверка: MemoryCurrent `15319040` bytes,
  MemoryMax `268435456` bytes (256 MiB), CPU quota `50%`.
  Текущее потребление памяти не является постоянным параметром.
- `/opt/timeweb-reality/guard.sh`, `guard.nft`, `guard.expected`:
  host native nft `inet reality_fornex` привязан к UID `10001`.
- Guard разрешает три native WG endpoints, TCP/443 к REALITY target,
  loopback WSS endpoints `127.0.0.1:51923` (Fornex) и
  `127.0.0.1:51924` (Cenuta), а также established replies с source port 443.
  Остальной исходящий трафик этого UID отбрасывается. `guard.nft` и
  `guard.expected` являются одной парой: их drift запрещает новый outbound,
  даже если WSS carrier запущен.

Поле `hosts.timeweb.recovery` содержит ошибочную проверку отсутствующего
`timeweb-reality`. Его `inactive/dead` не относится к рабочему Xray:
источник статуса правильного unit - `hosts.timeweb.units` и дополнительная проверка.

## BTH recovery

REALITY peer `10.30.30.5/32` является runtime-дополнением `wg-home`.
Его отдельный guard `inet reality_b5` находится в namespace `wg-relay):
блокирует доступ к самому relay, частным/служебным адресам и адресам трех VPS,
разрешает egress только через `wg-home`.

- `bth-recovery.timer`: enabled; `OnBootSec=45s`,
  `OnUnitInactiveSec=120s`, `AccuracySec=5s`.
  Это 120 s после завершения предыдущего oneshot, не жесткий интервал старта.
- `bth-recovery.service`: root oneshot,
  ExecStart `/bin/bash /opt/timeweb-reality/bth-recovery/bth_recover.sh`.
  Timeout `30s`, MemoryMax `96M`, CPUQuota `20%`, TasksMax `32`.
- Дополнительная проверка: Result `success`, ExecMainStatus `0`,
  ActiveState `inactive`. Между запусками это штатное состояние.
- Файлы сервера: `/opt/timeweb-reality/bth-recovery/`;
  контракт `contract.json`, guard `relay.nft` и `relay.expected`.
  Состояние проверки: `/run/bth-recovery-state.json`.

Контракт из master проверяет свежие container ID/PID/namespace, image,
mount и адреса, хеши WG/Xray/guard, peer identity, RPDB, table 300,
остальные AllowedIPs и host guard. Namespace закрепляется на время проверки.
Только при совпадении контракта восстанавливаются собственный BTH guard
и peer; при отказе peer не должен оставаться включенным без защиты.
Fornex/Cenuta не перезапускаются, общий firewall не сбрасывается.

`restored=false` в снимке означает проверку без восстановления,
не отказ. Это не доказательство успешного восстановления после реального reboot.
Локальный master: `services/transport/timeweb-reality/bth-recovery-release/`.

## Мониторинг и ограничения

`vpn-uplink-pilot.service` и `vpn-uplink-exporter.service` disabled,
inactive/dead. Старых RPDB guards `31000-31021` в текущем routing-снимке нет;
сохраненные каталоги `/var/lib/vpn-uplink-guards` и
`/var/lib/vpn-uplink-pilot` не доказывают работающий мониторинг.
`nftables.service` inactive/disabled на хосте не отменяет реально загруженные
native nft guards и правила в Docker namespace.

Серверный listener, route и handshake не заменяют DNS, IPv6, Amnezia/TUN,
fail-closed, restart и stability-приемку реальных клиентов.
Свежий export MikroTik через proxy завершился timeout 45 s:
текущая конфигурация роутера не подтверждена этим аудитом.
Пакетный статус, reboot-required и эффективные SSH-настройки не обновлялись.

## Мастер-копии и история

`System/...` отсчитывается от Dropbox рядом с `Obsidian/`.
REALITY master: `services/transport/timeweb-reality/`; этапные каталоги
`stage56-timeweb/`, `stage8-cenuta/`, `stage9-bth/` сохраняют свой scope.
Текущая выдача: `.local/clients/`.
Источники конфигов и восстановления: [VPN_Configuration_Registry](<../../registry/configuration.md>).
Ключи, PSK, UUID, QR и полные приватные конфиги здесь не публикуются.

Исходная страница со всей ранней историей:
`services/transport/documentation-audit-20260913/before/Obsidian/Personal/RESOURCE/IT/MIKROTIK/docs/agents/host-state/TimeWeb_Configuration.md`.

Существующие исторические ссылки:
[Аудит 2026-06-28](<../../history/timeweb/2026-06-28T1726Z-live-audit/README.md>),
[Внедрение selector](<../../history/timeweb/2026-06-29T0701Z-timeweb-selector-implementation/README.md>),
[Исправление AllowedIPs](<../../history/timeweb/2026-06-29T1520Z-selector-allowedips-viewer-fix/README.md>),
[Меню обслуживания](<../../history/timeweb/2026-06-29T1550Z-client-maintenance-menu/README.md>).
Соответствующие каталоги есть в `.local/backups/timeweb/`.
Они не являются текущим образом для полного restore; старые серверные
backup-пути сохранены в оригинале, но их наличие сейчас не перепроверялось.
