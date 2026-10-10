---
type: inventory
topic: mikrotik
system: timeweb
status: active
created: 2026-06-28
updated: 2026-09-25
provider: TimeWeb
tags:
  - mikrotik
  - vpn
  - vps
  - timeweb
  - inventory
source:
  - "[TimeWeb_Configuration](<TimeWeb_Configuration.md>)"
  - "[TimeWeb_Client_Creation](<../../operations/TimeWeb_Client_Creation.md>)"
  - "[VPN_HLD](<../../architecture/overview.md>)"
  - "[VPN_Configuration_Registry](<../../registry/configuration.md>)"
---

## Подтвержденное состояние

Основа: live.json (source reference not migrated),
`hosts.timeweb`, 2026-09-13 14:45 UTC; дополнительная read-only проверка
правильного REALITY unit передана владельцем аудита 2026-09-13.
Это текущий серверный инвентарь, не приемка всего клиентского трафика.

Дополнение 2026-09-25: FLEX fleet расширен до трёх устройств. Для Mac Mini
добавлены identity `macmini-socks-flex`, отдельный WG peer `10.50.50.41/32`
и профиль `SOCKS-TW-FLEX-S-Mini.json`. Серверный маршрут `ready`, текущие
общие параметры при проверке: Cenuta, RU-direct ON. Профиль ещё не принят
клиентом; приведённые ниже счетчики относятся к базовому снимку 2026-09-13.

TimeWeb уже обслуживает legacy WireGuard, selector, BTH и host-level
VLESS/REALITY с выходами Fornex, Cenuta и BTH.
Архитектура: [VPN_HLD](<../../architecture/overview.md>), runtime-детали: [TimeWeb_Configuration](<TimeWeb_Configuration.md>).

## Хост и доступ

- Адрес: `94.241.171.65`; hostname: `6275803-hh441050`.
- Kernel: `6.8.0-134-generic`; uptime около 65 суток; failed units: 0.
- RAM: 1967 MiB; swap отсутствует; корневой раздел 29 GiB, занят на 40%.
- `eth0`: `94.241.171.65/24`; в свежем снимке global IPv6 не виден.
- Доступ: `root@94.241.171.65:22`; локальная ссылка на ключ:
  `.local/ssh/codex_timeweb_audit_20260628`. Проверка host key: [Host_Access_Guide](<../../operations/access.md>).
- SSH, firewall и сервисы при переписывании страниц не менялись.

## Listeners и роли

- `51820/udp`: Docker `wg-relay/wg0`, `10.10.10.1/24`,
  15 настроенных legacy peers; основной выход Fornex.
- `51830/udp`: `wg-relay/wg-home`, `10.30.30.1/24`,
  4 peers, включая домашний MikroTik и отдельный REALITY peer `10.30.30.5/32`.
- `51850/udp`: `wg-relay/wg-clients`, `10.50.50.1/24`,
  19 selector peers с назначенными маршрутами.
- `94.241.171.65:443/tcp`: `xray-timeweb-reality.service`,
  host-level VLESS/REALITY; 6 учетных записей для трех выходов.
- `22/tcp`: управление SSH; `10050/tcp`: дополнительный listener
  (ранее Zabbix, владелец процесса свежим `ss` не указан).
- Локальные TCP/UDP DNS stubs `127.0.0.53:53`, `127.0.0.54:53`;
  DHCP-клиент `94.241.171.65:68/udp`.
  Динамические UDP source-порты uplink не являются стабильными клиентскими endpoints.

Список устройств и импортируемых профилей: [TimeWeb_VPN_Registry](<../../registry/tunnels.md>).

## Namespace и маршруты

- `wg-relay`: running, restart `unless-stopped`;
  Docker-сеть `wg_wg-network`, адрес `172.19.0.2`.
  На момент снимка PID `1181`, namespace `net:[4026532282]`;
  эти значения не являются постоянными идентификаторами.
- `wg1`: `10.20.0.1/24 -> 103.75.126.143:51821/udp`, table `100`.
- `wg-up-cenuta`: `10.40.40.2/32 -> 89.252.153.129:51840/udp`, table `200`.
- `wg-home`: BTH, default в table `300`.
- Selector RU split реализован native nft `inet ru_bth`:
  PREROUTING выставляет `0x30`, RPDB priority `190` выбирает table `300`.
  Пустая mangle в `iptables-save` не означает отсутствия RU split.
- Xray работает в namespace хоста, а его три WG outbounds в userspace:
  `10.20.0.3/32` через Fornex, `10.40.40.3/32` через Cenuta,
  `10.30.30.5/32` через `172.19.0.2:51830` к BTH.

## Сервисы и рабочие файлы

- `xray-timeweb-reality.service`: enabled, active/running;
  пользователь `reality-fornex`; конфиг `/opt/timeweb-reality/config.json`,
  бинарник `/opt/timeweb-reality/xray`.
  Unit: `/etc/systemd/system/xray-timeweb-reality.service`.
- REALITY guard: `/opt/timeweb-reality/guard.sh`, `guard.nft`, `guard.expected`;
  host nft `inet reality_fornex` ограничивает исходящий трафик UID `10001`.
- `bth-recovery.timer`: enabled; `OnBootSec=45s`,
  `OnUnitInactiveSec=120s`, `AccuracySec=5s`.
  `bth-recovery.service` выполняет `/opt/timeweb-reality/bth-recovery/bth_recover.sh`.
  Последняя дополнительная проверка: Result `success`, ExecMainStatus `0`;
  inactive между запусками нормально для oneshot.
- BTH recovery восстанавливает только свой runtime peer и guard при совпадении
  контракта; это не общий watchdog или безусловный restart VPN.
- Legacy/selector master на сервере: `/opt/wg/docker-compose.yml`,
  `/opt/wg/config/wg_confs/`, `/opt/wg-router/commands.sh`,
  `/opt/wg-router/state/`, `/opt/wg-router/apply-ru-bth.sh`.
- `vpn-uplink-pilot.service` и `vpn-uplink-exporter.service`:
  disabled, inactive/dead. Старый monitoring pilot не считается работающим.

## Мастер-копии и история

`System/...` отсчитывается от общего Dropbox рядом с `Obsidian/`.

- REALITY master: `services/transport/timeweb-reality/`;
  `stage56-timeweb/`, `stage8-cenuta/`, `stage9-bth/` относятся
  к соответствующим этапам. Они не заменяют текущий runtime-конфиг.
- BTH recovery release: `services/transport/timeweb-reality/bth-recovery-release/`.
- Текущие импортируемые профили: `.local/clients/`;
  владельцы конфигов и восстановление: [VPN_Configuration_Registry](<../../registry/configuration.md>).
- Оригинал этой страницы:
  `services/transport/documentation-audit-20260913/before/Obsidian/Personal/RESOURCE/IT/MIKROTIK/docs/TimeWeb_Parameters.md`.
- Существующая история:
  [Аудит TimeWeb 2026-06-28](<../../history/timeweb/2026-06-28T1726Z-live-audit/README.md>),
  [Внедрение selector](<../../history/timeweb/2026-06-29T0701Z-timeweb-selector-implementation/README.md>),
  [Меню обслуживания клиентов](<../../history/timeweb/2026-06-29T1550Z-client-maintenance-menu/README.md>).
  Соответствующие каталоги существуют в `.local/backups/timeweb/`.

Старые backups сохраняют свой исторический scope; они не являются
«последней безопасной копией» для полного restore. Полные конфиги, ключи,
PSK, UUID и QR в Obsidian не публикуются.

## Ограничения

Server-running, listener и handshake не доказывают Amnezia/TUN all-traffic
acceptance, DNS/IPv6 безопасность всех устройств, restart или стабильность.
Свежий экспорт домашнего роутера через proxy завершился timeout 45 s:
текущая конфигурация MikroTik этим аудитом не подтверждена.
Пакеты, reboot-required и effective SSH-security сейчас не проверены;
старые июньские значения не переносятся в текущий статус.
