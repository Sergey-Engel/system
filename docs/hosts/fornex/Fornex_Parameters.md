---
type: inventory
topic: mikrotik
system: fornex
status: active
created: 2026-06-28
updated: 2026-10-23
provider: Fornex
tags:
  - mikrotik
  - vpn
  - vps
  - fornex
  - inventory
source:
  - "[Fornex_Configuration](<Fornex_Configuration.md>)"
  - "[VPN_HLD](<../../architecture/overview.md>)"
  - "[VPN_Configuration_Registry](<../../registry/configuration.md>)"
---

## Подтвержденное состояние

Актуализация 2026-10-23: выполнено обслуживание Ubuntu 24.04 LTS,
Docker `29.9.2`, containerd `2.4.2`; после reboot kernel
`6.8.0-147-generic`. Все семь прежних контейнеров работают, DNS healthy,
выбранные конфигурации и container/image identities не изменились.
Подробности и ограничения: [обслуживание Fornex](<../../history/2026-10-23-fornex-maintenance.md>).
Параметры ниже, явно относящиеся к снимку 13 сентября, сохранены как история.

Снимок: live.json (source reference not migrated),
`hosts.fornex`, 2026-09-13 14:45 UTC. Это серверный инвентарь, не приемка
всего клиентского трафика. Подробности: [Fornex_Configuration](<Fornex_Configuration.md>).

Fornex обслуживает WireGuard-egress TimeWeb и отдельные прямые Amnezia-транспорты.
`fornex-awg31` уже развернут: 11 настроенных peers. Старый `amnezia-awg2`
удален, listener `46055/udp` отсутствует. `wg-exit` при миграции AWG не менялся.

## Хост и доступ

- Адрес: `103.75.126.143`; hostname: `278098.fornex.cloud`.
- Kernel: `6.8.0-138-generic`; uptime около 18 суток; failed units: 0.
- RAM: 1967 MiB; swap отсутствует; корневой раздел 20 GiB, занят на 43%.
- `eth0`: `103.75.126.143/24`, global IPv6 `2a00:7c80:0:a1:669::1/48`.
- Доступ: `root@103.75.126.143:22`; локальная ссылка на ключ:
  `.local/ssh/codex_fornex_audit_20260628`. Правила trust store: [Host_Access_Guide](<../../operations/access.md>).
- VPS ID `34-278098` и Netherlands сохранены из прежней карточки;
  панель провайдера в этом аудите не проверялась.

## Listeners и роли

- `51821/udp`: Docker `wg-exit`, интерфейс `wg0`, адрес `10.20.0.2/24`.
  Два peer TimeWeb: legacy `10.20.0.1/32` с `10.10.10.0/24`
  и отдельный REALITY `10.20.0.3/32`.
- `103.75.126.143:46056/udp`: Docker `fornex-awg31`, `awg0`,
  `10.83.1.254/24`, 11 peers сети `10.83.1.0/24`.
- `443/tcp`: `amnezia-xray` на Fornex. Это не
  `xray-timeweb-reality.service`, который работает на TimeWeb.
- `53/udp`: `amnezia-wireguard`, не публичный DNS-сервис.
- `34174/udp`: `amnezia-openvpn`; `500/udp` и `4500/udp`: `amnezia-ipsec`.
- `amnezia-dns`: внутренний `172.29.172.254`, без публикации host-порта.
- Управление: `22/tcp`. Дополнительные listeners:
  `8080`, `4330`, `44321`, `44322`, `44323/tcp`;
  `8189/tcp` только на `127.0.0.1`. Свежий снимок не содержит владельцев процессов.
  Ранее `8080` был BeAdmin; актуальность назначения и внешние ACL отдельно не проверены.

## Namespace и файлы

- `wg-exit`: собственный Docker namespace, `172.18.0.2`,
  сеть `wg_wg-network`; конфиг хоста `/opt/wg/config/wg_confs/wg0.conf`
  доступен в контейнере как `/config/wg_confs/wg0.conf`.
- Compose legacy-контура: `/opt/wg/docker-compose.yml`.
- `fornex-awg31`: отдельный namespace, `172.17.0.7`;
  `/opt/fornex-awg31` смонтирован read-only в тот же путь.
  Рабочие файлы: `awg0.conf` и `start.sh`.
- Остальные Amnezia-контейнеры имеют отдельные namespace и сети Docker.
  `wg show` только на хосте не заменяет проверку контейнеров.

## Сертификаты и ключевые файлы

Полные конфиги, ключи, PSK, UUID, QR и параметры обфускации здесь не публикуются.
Исторические пути BeAdmin: `/etc/ssl/beadmin/`, `/etc/beadmin/data.key`;
наличие и сроки сертификатов свежим снимком не проверены.
SSH-доступ использует ключи OpenSSH, не сертификаты BeAdmin.

## Мастер-копии и история

Пути `System/...` отсчитываются от общего Dropbox, рядом с `Obsidian/`.

- AWG31: `services/transport/fornex-awg31/`; состав выдачи в `fleet.json`,
  серверный комплект в `release/`, импортируемые профили в `.local/clients/`.
- REALITY peer Fornex: `services/transport/timeweb-reality/stage4-fornex/`.
  Архитектура и распределение владельцев файлов: [VPN_HLD](<../../architecture/overview.md>), [VPN_Configuration_Registry](<../../registry/configuration.md>).
- Список клиентских профилей не дублируется: [TimeWeb_VPN_Registry](<../../registry/tunnels.md>).
- Исходная версия этой страницы: `services/transport/documentation-audit-20260913/before/Obsidian/Personal/RESOURCE/IT/MIKROTIK/docs/Fornex_Parameters.md`.
- Существующий исторический аудит:
  [Аудит Fornex 2026-06-28](<../../history/fornex/2026-06-28T1410Z-live-audit/README.md>);
  файлы в `.local/backups/fornex/2026-06-28T1410Z-live-audit/`.
- Проверенные существующие файлы истории 2026-06-28:
  post-reboot verification (source reference not migrated),
  post-upgrade verification (source reference not migrated).
- Архив вывода AWG2: `services/transport/fornex-awg31/retirement-backup/`.
  Это история, не автоматический rollback и не актуальная копия всей системы.
  Старые AWG2-профили больше не являются рабочим способом возврата.

## Ограничения

Наличие listener, контейнера, handshake или 11 peers не доказывает работу всех
11 устройств. Физические клиенты, Amnezia/TUN, DNS, IPv6, fail-closed,
перезапуск и длительная стабильность требуют отдельной приемки.
Глобальный IPv6 на VPS сам по себе не подтверждает IPv6-egress VPN.
Пакеты, reboot-required, эффективные SSH-настройки и полная модель firewall
этим снимком не проверены. SSH и runtime в ходе правки документа не менялись.
