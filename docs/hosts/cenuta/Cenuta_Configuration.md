---
type: configuration
topic: mikrotik
system: cenuta
status: active
created: 2026-06-28
updated: 2026-09-13
provider: Cenuta
tags:
  - mikrotik
  - vpn
  - wireguard
  - cenuta
  - configuration
source:
  - "[Cenuta_Parameters](<Cenuta_Parameters.md>)"
  - "[VPN_HLD](<../../architecture/overview.md>)"
  - "[VPN_Configuration_Registry](<../../registry/configuration.md>)"
---

## Основание и роль

Серверный снимок: live.json (source reference not migrated),
`hosts.cenuta`, 2026-09-13 14:45 UTC. Конфигурация уже реализована:
Cenuta выпускает трафик TimeWeb в Internet через `89.252.153.129`.
Это описание runtime, не план установки и не отчет о приемке всех клиентов.

Доступ и аппаратный инвентарь: [Cenuta_Parameters](<Cenuta_Parameters.md>), [Host_Access_Guide](<../../operations/access.md>).
Общая схема: [VPN_HLD](<../../architecture/overview.md>); реестр профилей: [TimeWeb_VPN_Registry](<../../registry/tunnels.md>).

## Namespace и маршрутизация

WireGuard работает непосредственно в namespace хоста, без Docker-границы.

- Внешний интерфейс `ens3`: `89.252.153.129/24`.
  Default route через `89.252.153.1`, source `89.252.153.129`.
- `wg-cenuta`: `10.40.40.1/24`, listener `51840/udp`.
- Peer `10.40.40.2/32`: существующий TimeWeb `wg-relay/wg-up-cenuta`;
  selector-трафик приходит через table `200` на TimeWeb.
- Peer `10.40.40.3/32`: отдельный userspace WG outbound `wg-cenuta`
  процесса `xray-timeweb-reality.service` на TimeWeb.
- В снимке у обоих peers есть handshake и ненулевые counters.
  Peer-адреса различаются; новый REALITY-выход не заменяет legacy uplink.
- Правила forward/NAT для `10.40.40.0/24 -> ens3` присутствуют.
  Значение sysctl IPv4 forwarding этим collector не снималось.
- На внешнем интерфейсе только link-local IPv6. Это не тест клиентских IPv6-утечек.

Cenuta не является BTH hub. REALITY listener `94.241.171.65:443/tcp`
находится на TimeWeb; Cenuta принимает только соответствующий WG uplink.

## Firewall

Подтверждено native nft в namespace хоста:

- `inet filter`: input/forward policy `drop`, output policy `accept`.
- Input разрешает loopback, established/related, ICMP/ICMPv6,
  DHCP-ответы, `22/tcp` и `51840/udp`; invalid отбрасывается.
- Forward разрешает established/related и
  `wg-cenuta -> ens3` с source `10.40.40.0/24`.
- `ip nat`: MASQUERADE сети `10.40.40.0/24` через `ens3`.
- `inet reality_c3`: отдельные input/forward hooks с приоритетом
  `filter - 10` для source `10.40.40.3` на `wg-cenuta`.
  Доступ к самому хосту блокируется; закрыты частные/служебные диапазоны,
  публичные IP трех VPS и любой egress кроме `ens3`.

Наличие guard в runtime доказано снимком правил. Полный контракт
восстановления после reboot этим аудитом не испытывался.

## Сервисы и listeners

- `wg-quick@wg-cenuta.service`: loaded, `active/exited`.
  Для поднятого через wg-quick интерфейса это нормальный oneshot-статус,
  не признак остановки туннеля.
- `nftables.service`: enabled, `active/exited`.
- `wg-quick.target` inactive не отменяет наличие активного instance/interface.
- `22/tcp`: SSH; `51840/udp`: WireGuard.
- Локальные TCP/UDP DNS stubs: `127.0.0.53:53`, `127.0.0.54:53`.
- DHCP-клиент: `89.252.153.129:68/udp`.
- Kernel `6.8.0-139-generic`, failed units: 0.

Точный autostart-статус instance `wg-quick@wg-cenuta`, SSH socket/service,
полный набор пакетов и reboot-required текущим выводом отдельно не сняты.
Старые значения «0 обновлений» и «reboot не нужен» не считаются текущими.

## Рабочие файлы и master

- `/etc/wireguard/wg-cenuta.conf`: действующий WG-конфиг;
  его SHA-256 есть в `hosts.cenuta.routing`.
- `/etc/nftables.conf`: основной persistent firewall.
- `/etc/reality-c3/guard.sh`, `guard.nft`, `guard.expected`:
  source guard REALITY; пути сверены по deployment master,
  содержимое этих файлов свежим collector отдельно не снималось.
- `/etc/wireguard/wg-cenuta.key` и `/etc/netplan/50-cloud-init.yaml`:
  ранее учтенные пути, наличие и права сейчас отдельно не проверены.
- `/root/wireguard-handoff/timeweb-wg-up-cenuta.conf`:
  историческая передача initial uplink, не будущая настройка и не current master.
- Локальный master REALITY: `services/transport/timeweb-reality/stage8-cenuta/`.
  Клиентская выдача: `.local/clients/`.
  Владельцы файлов и backup-политика: [VPN_Configuration_Registry](<../../registry/configuration.md>).

Пути `System/...` отсчитываются от Dropbox рядом с `Obsidian/`.
Полные конфиги, ключи, PSK, UUID и QR не публикуются в этих документах.

## Ограничения и история

Снимок доказывает наличие сервиса, интерфейса, peers, маршрутов и firewall,
но не all-traffic acceptance. В нем нет новых внешних HTTP/DNS,
Amnezia/TUN, IPv6/fail-closed, restart или stability-тестов.
Сентябрьские записи о временном отказе SSH/HTTPS и последующем восстановлении
сохранены как история; текущий отказ или его причина из них не выводятся.

Оригинал этой страницы:
`services/transport/documentation-audit-20260913/before/Obsidian/Personal/RESOURCE/IT/MIKROTIK/docs/agents/host-state/Cenuta_Configuration.md`.

Существующие исторические материалы:

- [Аудит Cenuta 2026-06-28](<../../history/cenuta/2026-06-28T1958Z-live-audit/README.md>).
- [Post-update 2026-06-28](<../../history/cenuta/2026-06-28T2017Z-post-update-check/README.md>).
- [Настройка wg-cenuta](<../../history/cenuta/2026-06-28T2025Z-wg-cenuta-setup/README.md>).
- Соответствующие каталоги `.local/backups/cenuta/`.

Это датированные backups/evidence, не актуальный образ для полного restore.
SSH и runtime в ходе переписывания страницы не менялись.
