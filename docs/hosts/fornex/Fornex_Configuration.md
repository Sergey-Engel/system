---
type: system-configuration
topic: mikrotik
system: fornex
status: active
created: 2026-06-28
updated: 2026-09-13
tags:
  - mikrotik
  - vpn
  - wireguard
  - docker
  - fornex
source:
  - "[Fornex_Parameters](<Fornex_Parameters.md>)"
  - "[VPN_HLD](<../../architecture/overview.md>)"
  - "[VPN_Configuration_Registry](<../../registry/configuration.md>)"
---

## Основание и границы

Текущее серверное состояние: live.json (source reference not migrated),
`hosts.fornex`, 2026-09-13 14:45 UTC. Пути и история AWG-миграции сверены с
локальным master `services/transport/fornex-awg31/`. Здесь нет новых
SSH-проверок или runtime-изменений. Доступ и ресурсы: [Fornex_Parameters](<Fornex_Parameters.md>),
[Host_Access_Guide](<../../operations/access.md>). Архитектура: [VPN_HLD](<../../architecture/overview.md>).

## Работающие контуры

### WireGuard-egress TimeWeb

`TimeWeb -> 103.75.126.143:51821/udp -> wg-exit/wg0 -> Internet`.

- Docker `wg-exit`: running, старт 2026-08-26; restart `unless-stopped`.
  Образ `lscr.io/linuxserver/wireguard:latest`; идентификатор образа зафиксирован в evidence.
- Namespace контейнера: сеть `wg_wg-network`, адрес `172.18.0.2`.
  Интерфейс `wg0`: `10.20.0.2/24`, порт `51821`.
- Два настроенных peer: legacy TimeWeb `10.20.0.1/32,10.10.10.0/24`
  и userspace WG из TimeWeb REALITY `10.20.0.3/32`.
  В снимке у обоих ненулевые counters и недавние handshake.
- `51820/udp` в Docker metadata не опубликован; рабочий endpoint здесь `51821`.
  `94.241.171.65` принадлежит TimeWeb, не Fornex.
- Runtime-конфиг: `/opt/wg/config/wg_confs/wg0.conf` на хосте,
  `/config/wg_confs/wg0.conf` внутри контейнера.
  Compose: `/opt/wg/docker-compose.yml`; mount `/opt/wg/config:/config`.
- Дополнение REALITY хранится в `/opt/wg/config/reality-f3/`
  (в контейнере `/config/reality-f3/`); локальный master:
  `services/transport/timeweb-reality/stage4-fornex/`.
  Полные source guards в `live.json` для Fornex не сняты:
  пути известны из deployment master, не являются повторной live-проверкой guard-контракта.
- Во время миграции AWG2 -> AWG31 `wg-exit` не изменялся.
  Это не означает отсутствия более раннего дополнения REALITY peer.

### Прямой AmneziaWG 3.1

`Клиент -> 103.75.126.143:46056/udp -> fornex-awg31/awg0 -> Internet`.

- `fornex-awg31`: running, отдельный namespace, `172.17.0.7`;
  restart `unless-stopped`, текущий старт 2026-09-13 14:00 UTC.
- `awg0`: `10.83.1.254/24`; 11 настроенных peers сети `10.83.1.0/24`.
  Адреса не образуют сплошной диапазон; roster в [TimeWeb_VPN_Registry](<../../registry/tunnels.md>).
- `/opt/fornex-awg31/awg0.conf` и `start.sh`;
  каталог смонтирован read-only. Конфигурация уже применена, не является планом установки.
- В namespace есть FORWARD `awg0 -> eth0` для `10.83.1.0/24`,
  обратный established/related и MASQUERADE этой сети через `eth0`.
- Локальный master: `services/transport/fornex-awg31/`, серверный комплект
  `release/`, roster `fleet.json`, клиентская выдача `.local/clients/`.
- `amnezia-awg2` удален; `46055/udp` не слушает.
  Первоначальные инструкции «оставить AWG2 параллельно» больше не описывают runtime.
  Старые профили не работают; восстановление AWG2 требует отдельного решения.

### Остальные Amnezia-контейнеры

Все перечисленные контейнеры running, restart `always`:

- `amnezia-xray`: host `443/tcp`.
- `amnezia-wireguard`: host `53/udp`; этот порт занят WireGuard, не DNS.
- `amnezia-openvpn`: host `34174/udp`.
- `amnezia-ipsec`: host `500/udp` и `4500/udp`.
- `amnezia-dns`: `172.29.172.254` в `amnezia-dns-net`,
  внутренние `53/tcp,udp`, host-порт не опубликован.

Они не являются процессом TimeWeb REALITY. Активного `wg-home` или
BTH listener `51830` в снятом инвентаре Fornex нет.

## Хостовые сервисы и ограничения аудита

Kernel `6.8.0-138-generic`, IPv4 `103.75.126.143/24`;
на `eth0` назначен global IPv6. Failed units: 0.
`nftables.service` имеет UnitFileState `disabled`; это не означает
отсутствия правил Docker/netfilter.

Помимо VPN, слушают `22`, `8080`, `4330`, `44321`, `44322`,
`44323/tcp`; `127.0.0.1:8189/tcp` доступен только локально.
Владельцы дополнительных listeners и доступность извне не установлены
текущим выводом `ss`. Полный service/package/SSH-security audit не выполнялся.

Запущенный сервер и handshake не заменяют прикладную приемку каждого
устройства. DNS, IPv6, полный Amnezia/TUN-трафик, fail-closed и длительная
стабильность не принимаются по этому снимку.

## Хранение и история

`System/...` означает каталог соседнего с Obsidian дерева Dropbox.
Владельцы конфигов и источники восстановления: [VPN_Configuration_Registry](<../../registry/configuration.md>).
Полные конфиги, ключи, UUID, PSK и QR в Obsidian не копируются.

- Оригинал страницы:
  `services/transport/documentation-audit-20260913/before/Obsidian/Personal/RESOURCE/IT/MIKROTIK/docs/agents/host-state/Fornex_Configuration.md`.
- Существующий июньский архив:
  [Аудит Fornex 2026-06-28](<../../history/fornex/2026-06-28T1410Z-live-audit/README.md>),
  `.local/backups/fornex/2026-06-28T1410Z-live-audit/`.
- Сохраненные AWG2 originals: `services/transport/fornex-awg31/retirement-backup/`.
  Ранняя копия `backup/` также существует, но относится к первоначальному этапу.

Это датированная история, не «последний безопасный backup».
Общий restore старого firewall, повторный первоначальный deploy/finalize
или возврат всего хоста по архиву не следуют из этой документации.
