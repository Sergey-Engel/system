---
type: inventory
topic: mikrotik
system: timeweb
status: active
created: 2026-06-28
updated: 2026-10-21
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

21 октября установлен ручной split data plane2.0.0 поверх прежнего SSTP1.1.1:
SSTP-Cenuta/SSTP-Fornex, controller4.0.0. BTH и управление остаются WG;
старые WG/Xray не перезапускались. Новый namespace connector, только
точные source selectors, без root veth/NAT/default route. Проверены
оба HTTPS egress, блокировка при отказе, переподключение PPP и Undo.
Полный reboot split-топологии не выполнялся. CPU pressure остаётся высоким.
[Протокол, резервные копии и ограничения](../../history/2026-10-21-sstp-split-manual-routing.md).

Актуальное обслуживание и новый SSTP проверены 20 октября 2026:
см. раздел «Хост и доступ» и
[протокол обслуживания](../../history/2026-10-20-timeweb-maintenance-sstp-newip.md).
Старые количества peers, PID и показатели ниже сохранены как датированные
свидетельства, а не как текущая телеметрия.

Историческая основа: live.json (source reference not migrated),
`hosts.timeweb`, 2026-09-13 14:45 UTC; дополнительная read-only проверка
правильного REALITY unit передана владельцем аудита 2026-09-13.
Это серверный снимок, не приемка всего клиентского трафика.

Дополнение 2026-09-25: FLEX fleet расширен до трёх устройств. Для Mac Mini
добавлены identity `macmini-socks-flex`, отдельный WG peer `10.50.50.41/32`
и профиль `SOCKS-TW-FLEX-S-Mini.json`. Серверный маршрут `ready`, текущие
общие параметры при проверке: Cenuta, RU-direct ON. Профиль ещё не принят
клиентом; приведённые ниже счетчики относятся к базовому снимку 2026-09-13.

TimeWeb уже обслуживает legacy WireGuard, selector, BTH и host-level
VLESS/REALITY с выходами Fornex, Cenuta и BTH.
Архитектура: [VPN_HLD](<../../architecture/overview.md>), runtime-детали: [TimeWeb_Configuration](<TimeWeb_Configuration.md>).

## Хост и доступ

### Дополнение 20 октября 2026: адреса сервера

В панели TimeWeb сервер называется **Lucky Bridge**; проверенный hostname ОС
остаётся 6275803-hh441050, provider server ID **6275803**.
ОС: Ubuntu **24.04.5 LTS**, 1 vCPU, около 2 GiB RAM; переход на новую
версию Ubuntu не выполнялся. Пользователь добавил дополнительный публичный IPv4
и разрешил использовать его для SSTP от MikroTik Нахимова.
Источник назначения: предоставленный пользователем скриншот раздела «Сеть».
Затем выполнено отдельно разрешённое обслуживание через strict SSH;
установка адреса, listener и автозапуск проверены реальным reboot.

| Адрес | Назначение | Подтверждённое состояние на 20 октября |
| --- | --- | --- |
| 94.241.171.65 | Прежний основной IPv4, SSH/WireGuard/Xray | В ОС: eth0, /24, DHCP/default сохранены. Xray по-прежнему слушает только 94.241.171.65:443; configs/keys неизменны, службы перезапускались при разрешённом обслуживании |
| 91.222.238.208 | Дополнительный IPv4 для отдельного SSTP endpoint | eth0, /24; persistent netplan overlay. Приём TCP443, peer10.60.65.2, autostart/reboot и soak904.9s приняты |
| 2a03:6f01:1:2::1:105f | IPv6, показанный в панели провайдера | При исходном обследовании global IPv6 в ОС не обнаружен; этим этапом не настраивался и для SSTP не используется |

Работающий отдельный endpoint: **91.222.238.208:443/TCP**, release1.1.1.
Backend127.0.0.1:5444 находится только внутри namespace sstp-timeweb;
старый публичный listener94.241.171.65:5444 не включён. Новый серверный
сертификат имеет SAN91.222.238.208. На этапе 20 октября production routing
был выключен; 21 октября добавлен ручной выбор Cenuta/Fornex. Failover выключен.
Смена внешнего IP Нахимова требует reviewed source allowlist update.

Обслуживание: 25 package upgrades, Docker29.9.1/containerd2.4.2,
kernel6.8.0-147-generic после reboot, swap2GiB. После restart доступно около
1.3GiB RAM; вместо 9027 shim threads наблюдалось 13-15 без прежних FIFO waits.
При этом CPU по-прежнему занят фоновыми routing checks: load примерно6-8.
Эта CPU-проблема требует отдельной оптимизации/согласованного увеличения
ресурсов; успешный SSTP soak её не скрывает.

[Точный объём, копии и ограничения](../../history/2026-10-20-timeweb-maintenance-sstp-newip.md),
[первоначальный preflight](../../history/2026-10-20-timeweb-maintenance-preflight.md),
[исторический неуспешный кандидат](../../history/2026-10-20-sstp-timeweb-candidate.md).

### Исторический базовый снимок

Следующие параметры относятся к исходному обследованию, а не к новой
полной проверке сервера 20 октября.

- Адрес: `94.241.171.65`; hostname: `6275803-hh441050`.
- Kernel: `6.8.0-134-generic`; uptime около 65 суток; failed units: 0.
- RAM: 1967 MiB; swap отсутствует; корневой раздел 29 GiB, занят на 40%.
- `eth0`: `94.241.171.65/24`; в свежем снимке global IPv6 не виден.
- Доступ: `root@94.241.171.65:22`; локальная ссылка на ключ:
  `.local/ssh/codex_timeweb_audit_20260628`. Проверка host key: [Host_Access_Guide](<../../operations/access.md>).
- SSH, firewall и сервисы при переписывании страниц не менялись.

## Исторические Listeners и роли

Следующие количества peers/identity и дополнительные listeners относятся
к исходному снимку. Актуальные два TCP443 endpoint приведены выше.

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
Timeout экспорта MikroTik 45 s и отсутствие проверки пакетов относятся
к исходному аудиту сентября. Они не описывают результат 20 октября:
получены свежие exports и encrypted backup Нахимова, пакеты обновлены,
ядро после reboot проверено. При контрольной проверке 20 октября
reboot-required отсутствует. Полный новый аудит effective SSH-security
не выполнялся; прежние значения не выдаются за текущую проверку.

## Резервные Копии И Публикация

Свежие копии TimeWeb и Нахимова, локальный переносимый набор и точные
SHA256 перечислены в
[checkpoint публикации](../../history/2026-10-20-timeweb-publication-checkpoint.md).
Полные архивы, CA/PPP material и пароль RouterOS backup хранятся только
в закрытой `.local` и canonical store; в Git публикуются исходники,
паспорта, реестры и обезличенные результаты. Это конфигурационные копии,
не образы диска и не проверка полного восстановления машины.
